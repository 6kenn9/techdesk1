"""Telegram-бот TechDesk: прив'язка чату, сповіщення про етапи ремонту й погодження кошторису."""
import logging
import queue
import threading
from datetime import timedelta
import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from ..core.config import PUBLIC_URL
from ..core.database import SessionLocal
from ..models.models import Device, Order, Service, User, Work, now
from . import domain

log = logging.getLogger("techdesk.telegram")
bot = None  # екземпляр Bot, якщо задано TELEGRAM_BOT_TOKEN
HELP = ("Кнопки меню внизу:\n📋 Мої заявки — стан ремонтів і кошториси, що чекають рішення\n"
        "🛡 Гарантія — до якої дати діє гарантія на ремонти\n➕ Нова заявка — подати заявку на ремонт\n"
        "/stop — вимкнути сповіщення\n\n"
        "Щоб підключити сповіщення, відкрийте TechDesk і натисніть «Підключити Telegram».")

# Меню внизу чату: кнопка надсилає свій текст, а бот розуміє його як команду.
MENU = {"📋 Мої заявки": "/orders", "🛡 Гарантія": "/warranty", "➕ Нова заявка": "/new", "❓ Допомога": "/help"}
COMMANDS = [("orders", "Мої заявки"), ("warranty", "Гарантія на ремонти"), ("new", "Нова заявка"),
            ("help", "Допомога"), ("stop", "Вимкнути сповіщення")]
WARRANTY_NOTICE_DAYS = 7     # за скільки днів попереджати про кінець гарантії
MAINTENANCE_AFTER_DAYS = 180  # через скільки днів після ремонту радити профілактику
MAINTENANCE_CATEGORIES = ("Ноутбук", "ПК", "Моноблок", "Міні-ПК", "Консоль")

def menu(role):
    """Клавіатура внизу чату; працівникам гарантія й нова заявка не потрібні."""
    rows = [["📋 Мої заявки", "🛡 Гарантія"], ["➕ Нова заявка", "❓ Допомога"]] if role == "client" else [["📋 Мої заявки", "❓ Допомога"]]
    return {"keyboard": [[{"text": text} for text in row] for row in rows], "resize_keyboard": True, "is_persistent": True}

def date_text(value):
    return domain.local_date(value).strftime("%d.%m.%Y")

def repair_hours(db, order):
    """Орієнтовна тривалість робіт за прейскурантом; None, якщо роботи додано вручну."""
    hours = db.scalar(select(func.sum(Service.estimated_hours)).join(Work, Work.service_id == Service.id).where(Work.order_id == order.id))
    return float(hours) if hours else None

def money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " грн"

class TelegramApi:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.http = httpx.Client(timeout=40)

    def __call__(self, method, **params):
        data = self.http.post(self.base + method, json=params).json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data["result"]

def recipient(db, user_id, text, buttons=None):
    user = db.get(User, user_id) if user_id else None
    if user and user.is_active and user.telegram_chat_id:
        return [(user.telegram_chat_id, text, buttons)]
    return []

def status_text(db, order, title):
    status = order.status
    buttons = None
    if status == "waiting_approval":
        lines = ["💰 Кошторис готовий", title, ""]
        if order.diagnostics:
            lines.append(f"Діагностика: {order.diagnostics}")
        lines += [f"Роботи: {money(order.works_total)}", f"Запчастини: {money(order.parts_total)}",
                  f"До сплати: {money(order.total_cost)}"]
        hours = repair_hours(db, order)
        if hours:
            days = max(1, round(hours / 6 + 0.49))  # приблизно 6 годин роботи майстра на день
            lines.append(f"Орієнтовний строк після погодження: {days} {'робочий день' if days == 1 else 'робочі дні' if days < 5 else 'робочих днів'}")
        if order.is_warranty_case:
            lines.append("Гарантійний випадок — ремонт для вас безкоштовний.")
        text = "\n".join(lines)
        if order.client_approval_status == "pending":
            version = domain.estimate_version(db, order)[:20]
            buttons = [[{"text": "✅ Погодити", "callback_data": f"ap:{order.id}:{version}"},
                        {"text": "❌ Відхилити", "callback_data": f"rj:{order.id}:{version}"}]]
    elif status == "ready_for_pickup":
        if order.delivery_method == "nova_poshta":
            text = (f"✅ Ремонт завершено, готуємо відправку Новою Поштою\n{title}\n"
                    f"Куди: {order.delivery_city}, {order.delivery_branch}\nДо сплати перед відправкою: {money(order.total_cost - order.paid_amount)}")
        else:
            text = f"✅ Пристрій готовий до видачі\n{title}\nДо сплати: {money(order.total_cost - order.paid_amount)}"
    elif status == "completed":
        text = f"🎉 Заявку завершено\n{title}"
        if order.warranty_expires_at:
            text += f"\nГарантія до {date_text(order.warranty_expires_at)}. Нагадаємо за тиждень до її завершення."
        if order.rating is None:
            text += "\n\n⭐ Будемо вдячні за оцінку ремонту — це займе пів хвилини."
    else:
        heads = {"registered": "📥 Заявку прийнято", "diagnostics": "🔍 Пристрій на діагностиці",
                 "in_repair": "🔧 Ремонт розпочато", "cancelled": "Заявку скасовано"}
        text = f"{heads[status]}\n{title}"
    return text, buttons

def build_messages(db, kind, order_id):
    order = db.get(Order, order_id)
    if not order:
        return []
    device = db.get(Device, order.device_id)
    title = f"{order.order_number} · {device.brand} {device.model}"
    link = f"\n\nДеталі: {PUBLIC_URL}/orders/{order.id}"
    if kind == "status":
        text, buttons = status_text(db, order, title)
        return recipient(db, order.client_id, text + link, buttons)
    if kind == "shipped":
        text = (f"📦 Пристрій відправлено Новою Поштою\n{title}\nТТН: {order.delivery_ttn}\n"
                f"Відстежити: https://novaposhta.ua/tracking/?cargo_number={order.delivery_ttn}")
        return recipient(db, order.client_id, text + link)
    if kind == "assigned":
        return recipient(db, order.master_id, f"🛠 Вам призначено заявку\n{title}\nНесправність: {order.problem_description}{link}")
    if kind == "decision":
        approved = order.client_approval_status == "approved"
        text = f"{'✅ Клієнт погодив' if approved else '❌ Клієнт відхилив'} кошторис\n{title}\nСума: {money(order.total_cost)}"
        if not approved and order.approval_comment:
            text += f"\nКоментар: {order.approval_comment}"
        return recipient(db, order.master_id, text + link)
    return []

def due_reminders(db, moment=None):
    """Нагадування, які час надіслати: кінець гарантії та планова профілактика.

    Повертає [(order, kind, chat_id, text, buttons)]. Позначку про надсилання ставить викликач.
    """
    moment = moment or now()
    result = []
    linked = select(User.id).where(User.telegram_chat_id.is_not(None), User.is_active)
    soon = select(Order).where(Order.status == "completed", Order.warranty_reminded_at.is_(None), Order.client_id.in_(linked),
                               Order.warranty_expires_at > moment,
                               Order.warranty_expires_at <= moment + timedelta(days=WARRANTY_NOTICE_DAYS))
    for order in db.scalars(soon):
        device, client = db.get(Device, order.device_id), db.get(User, order.client_id)
        left = max(1, (order.warranty_expires_at - moment).days)
        text = (f"🛡 Гарантія на ремонт закінчується {date_text(order.warranty_expires_at)}\n{order.order_number} · {device.brand} {device.model}\n\n"
                f"Залишилось днів: {left}. Якщо помітили проблему, пов'язану з цим ремонтом, зверніться до цієї дати: гарантійний ремонт безкоштовний.")
        result.append((order, "warranty", client.telegram_chat_id, text, [[{"text": "Подати гарантійну заявку", "url": f"{PUBLIC_URL}/orders/new"}]]))
    # Профілактика: лише останній ремонт пристрою, щоб не радити чистку, якщо пристрій уже знову був у сервісі.
    old = (select(Order).join(Device, Device.id == Order.device_id)
           .where(Order.status == "completed", Order.maintenance_reminded_at.is_(None), Order.client_id.in_(linked),
                  Order.completed_at <= moment - timedelta(days=MAINTENANCE_AFTER_DAYS), Device.device_category.in_(MAINTENANCE_CATEGORIES)))
    for order in db.scalars(old):
        later = db.scalar(select(func.count(Order.id)).where(Order.device_id == order.device_id, Order.created_at > order.completed_at))
        if later:
            order.maintenance_reminded_at = moment  # пристрій уже повертався, нагадування не потрібне
            continue
        device, client = db.get(Device, order.device_id), db.get(User, order.client_id)
        text = (f"🧹 Час на планову профілактику\n{device.brand} {device.model}\n\n"
                f"Минуло пів року після ремонту {order.order_number}. Радимо почистити пристрій від пилу й замінити термопасту: "
                "так він менше грітиметься і прослужить довше.")
        result.append((order, "maintenance", client.telegram_chat_id, text, [[{"text": "Записатися на профілактику", "url": f"{PUBLIC_URL}/orders/new"}]]))
    return result

class Bot:
    def __init__(self, api, username="", background=True):
        self.api, self.username, self.background = api, username, background
        self.outbox = queue.Queue()
        self.stopping = threading.Event()

    def start(self):
        if not self.username:
            self.username = self.api("getMe")["username"]
        try:  # список команд для кнопки «Меню» поруч із полем введення
            self.api("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
        except Exception as error:
            log.warning("Не вдалося задати команди бота: %s", error)
        for target in (self._deliver_loop, self._poll_loop, self._reminder_loop):
            threading.Thread(target=target, daemon=True, name=f"telegram-{target.__name__}").start()

    def stop(self):
        self.stopping.set()
        self.outbox.put(None)

    def submit(self, events):
        for item in events:
            self.outbox.put(item) if self.background else self.process(item)

    def process(self, item):
        try:
            with SessionLocal() as db:
                messages = build_messages(db, *item)
            for chat_id, text, buttons in messages:
                self.send(chat_id, text, buttons)
        except Exception:
            log.exception("Не вдалося надіслати сповіщення %s", item)

    def send(self, chat_id, text, buttons=None, keyboard=None):
        """buttons — кнопки під повідомленням; keyboard — меню внизу чату."""
        params = {"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}}
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        elif keyboard:
            params["reply_markup"] = keyboard
        self.api("sendMessage", **params)

    def send_reminders(self, moment=None):
        """Надсилає нагадування й позначає їх, щоб не повторювати. Повертає кількість надісланих."""
        sent = 0
        with SessionLocal() as db:
            for order, kind, chat_id, text, buttons in due_reminders(db, moment):
                try:
                    self.send(chat_id, text, buttons)
                except Exception:
                    log.exception("Не вдалося надіслати нагадування %s", order.order_number)
                    continue
                setattr(order, f"{kind}_reminded_at", moment or now())
                sent += 1
            db.commit()
        return sent

    def _reminder_loop(self):
        while not self.stopping.wait(60):  # перша перевірка через хвилину після запуску, далі щогодини
            try:
                self.send_reminders()
            except Exception:
                log.exception("Помилка перевірки нагадувань")
            self.stopping.wait(3600 - 60)

    def _deliver_loop(self):
        while (item := self.outbox.get()) is not None:
            self.process(item)

    def _poll_loop(self):
        offset = None
        while not self.stopping.is_set():
            try:
                updates = self.api("getUpdates", offset=offset, timeout=25, allowed_updates=["message", "callback_query"])
                for update in updates:
                    offset = update["update_id"] + 1
                    self.handle_update(update)
            except Exception as error:
                log.warning("Telegram недоступний: %s", error)
                self.stopping.wait(5)

    def handle_update(self, update):
        try:
            if "callback_query" in update:
                self._callback(update["callback_query"])
            elif "message" in update:
                self._message(update["message"])
        except Exception:
            log.exception("Помилка обробки оновлення Telegram")

    def _message(self, message):
        chat = message.get("chat", {})
        if chat.get("type") != "private":
            return
        chat_id, text = chat["id"], (message.get("text") or "").strip()
        text = MENU.get(text, text)
        command, _, argument = text.partition(" ")
        command = command.split("@")[0]
        role = self._role(chat_id)
        if command == "/start" and argument.strip():
            reply, role = self._link(chat_id, argument.strip())
            self.send(chat_id, reply, keyboard=menu(role) if role else None)
        elif command == "/orders":
            self._orders(chat_id)
        elif command == "/warranty":
            self.send(chat_id, self._warranty(chat_id), keyboard=menu(role) if role else None)
        elif command == "/new":
            self.send(chat_id, "Опишіть несправність на сайті, і ми зареєструємо заявку. Пристрій можна принести або надіслати Новою Поштою.",
                      [[{"text": "Подати заявку", "url": f"{PUBLIC_URL}/orders/new" if role else f"{PUBLIC_URL}/quick"}]])
        elif command == "/stop":
            with SessionLocal() as db:
                user = db.scalar(select(User).where(User.telegram_chat_id == chat_id))
                if user:
                    user.telegram_chat_id = None
                    db.commit()
            self.send(chat_id, "Сповіщення вимкнено. Підключити знову можна в кабінеті TechDesk.", keyboard={"remove_keyboard": True})
        else:
            self.send(chat_id, "Вітаємо в TechDesk!\n\n" + HELP, keyboard=menu(role) if role else None)

    def _role(self, chat_id):
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_chat_id == chat_id, User.is_active))
            return user.role if user else None

    def _link(self, chat_id, code):
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_link_code == code).with_for_update())
            if not user or not user.is_active or not user.telegram_link_expires_at or user.telegram_link_expires_at < now():
                return "Посилання недійсне або застаріло. Створіть нове в кабінеті TechDesk.", None
            previous = db.scalar(select(User).where(User.telegram_chat_id == chat_id, User.id != user.id))
            if previous:
                previous.telegram_chat_id = None
                db.flush()
            user.telegram_chat_id = chat_id
            user.telegram_link_code = user.telegram_link_expires_at = None
            db.commit()
            return (f"Готово, {user.full_name}! Сюди надходитимуть сповіщення про ваші заявки.\n\n"
                    "Користуйтеся кнопками меню внизу, щоб не вводити команди вручну."), user.role

    def _orders(self, chat_id):
        """Список активних заявок; кошториси, що чекають рішення, надсилаються окремо з кнопками."""
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_chat_id == chat_id))
            if not user:
                return self.send(chat_id, "Обліковий запис не підключено. " + HELP.split("\n\n")[1])
            query = select(Order).where(Order.status.in_(domain.ACTIVE)).order_by(Order.created_at.desc()).limit(10)
            if user.role == "client":
                query = query.where(Order.client_id == user.id)
            elif user.role == "master":
                query = query.where(Order.master_id == user.id)
            lines, pending = [], []
            for order in db.scalars(query):
                device = db.get(Device, order.device_id)
                lines.append(f"• {order.order_number} · {device.brand} {device.model} — {domain.LABELS[order.status]}")
                if user.role == "client" and order.status == "waiting_approval" and order.client_approval_status == "pending":
                    pending.append(status_text(db, order, f"{order.order_number} · {device.brand} {device.model}"))
            self.send(chat_id, "Активні заявки:\n" + "\n".join(lines) if lines else "Активних заявок немає.",
                      [[{"text": "Відкрити кабінет", "url": f"{PUBLIC_URL}/{'my-cabinet' if user.role == 'client' else 'orders'}"}]])
        for text, buttons in pending:
            self.send(chat_id, text, buttons)

    def _warranty(self, chat_id):
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_chat_id == chat_id))
            if not user:
                return "Обліковий запис не підключено. " + HELP.split("\n\n")[1]
            query = (select(Order).where(Order.client_id == user.id, Order.status == "completed", Order.warranty_expires_at > now())
                     .order_by(Order.warranty_expires_at))
            lines = []
            for order in db.scalars(query):
                device = db.get(Device, order.device_id)
                lines.append(f"• {device.brand} {device.model} ({order.order_number}) — до {date_text(order.warranty_expires_at)}")
            if not lines:
                return "Чинних гарантій на ремонти немає."
            return "Гарантія діє:\n" + "\n".join(lines) + f"\n\nЗа {WARRANTY_NOTICE_DAYS} днів до кінця гарантії бот нагадає про неї."

    def _callback(self, callback):
        def answer(text):
            self.api("answerCallbackQuery", callback_query_id=callback["id"], text=text)
        message = callback.get("message") or {}
        chat_id = message.get("chat", {}).get("id") or callback["from"]["id"]
        try:
            action, order_id, version = callback.get("data", "").split(":")
            order_id = int(order_id)
            assert action in ("ap", "rj")
        except (ValueError, AssertionError):
            return answer("Невідома дія.")
        approved = action == "ap"
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.telegram_chat_id == chat_id))
            if not user or not user.is_active or user.role != "client":
                return answer("Обліковий запис клієнта не підключено.")
            try:
                order = domain.access_order(db, order_id, user, write=True)
                if order.status != "waiting_approval" or order.client_approval_status != "pending":
                    raise HTTPException(409, "Заявка не очікує нового рішення.")
                if not domain.estimate_version(db, order).startswith(version):
                    raise HTTPException(409, "Кошторис змінився. Відкрийте заявку, щоб переглянути актуальну суму.")
                domain.decide_estimate(db, order, user, approved, "" if approved else "Відхилено через Telegram")
                db.commit()
            except HTTPException as error:
                db.rollback()
                return answer(error.detail)
        answer("Кошторис погоджено. Майстер розпочне ремонт." if approved else "Кошторис відхилено. Майстер зв'яжеться з вами.")
        if message.get("message_id"):
            try:
                self.api("editMessageReplyMarkup", chat_id=chat_id, message_id=message["message_id"],
                         reply_markup={"inline_keyboard": []})
            except Exception:
                pass
