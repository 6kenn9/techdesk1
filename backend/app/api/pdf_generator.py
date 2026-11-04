from datetime import timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import qrcode
from fastapi import APIRouter, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from ..core.config import PUBLIC_URL
from ..core.security import Current, Db, fail
from ..models.models import Device, User
from ..services.domain import SPEC_LABELS, access_device, access_order, local_date, parts, works

router = APIRouter(prefix="/api")

def qr_image(url):
    stream = BytesIO()
    qrcode.make(url).save(stream, format="PNG")
    stream.seek(0)
    return stream

def format_money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " грн"

def date_label(value):
    return local_date(value).strftime("%d.%m.%Y")

def font_name():
    if "TechDesk" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("TechDesk", str(Path(__file__).resolve().parents[1] / "assets" / "DejaVuSans.ttf")))
    return "TechDesk"

def generate_pdf(db, order, certificate):
    device = db.get(Device, order.device_id)
    client = db.get(User, order.client_id)
    output = BytesIO()
    font = font_name()
    body = ParagraphStyle("Body", fontName=font, fontSize=10, leading=15, spaceAfter=5)
    heading = ParagraphStyle("Heading", parent=body, fontSize=17, leading=23, textColor=colors.HexColor("#173da3"))
    small = ParagraphStyle("Small", parent=body, fontSize=9, leading=13)
    def p(value, style=body):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)
    title = "Гарантійний талон та акт виконаних робіт" if certificate else "Квитанція про приймання техніки"
    story = [p("TechDesk · Сервісний центр"), p(title, heading), p(f"Заявка {order.order_number}"),
             p(f"Прийнято: {date_label(order.created_at)}"),
             p(f"Клієнт: {client.full_name} · {client.phone} · {client.email}"),
             p(f"Пристрій: {device.device_category} · {device.brand} {device.model}"),
             p(f"Серійний номер: {device.serial_number}")]
    if certificate:
        story.append(p("Роботи та встановлені запчастини", heading))
        data = [[p("Позиція", small), p("Кількість", small), p("Ціна", small), p("Сума", small)]]
        data.extend([p(item.work_name, small), p(1, small), p(format_money(item.price), small), p(format_money(item.price), small)] for item in works(db, order))
        data.extend([p(item.part_name, small), p(item.quantity, small), p(format_money(item.unit_sale_price), small),
                     p(format_money(item.total_sale_price), small)] for item in parts(db, order))
        table = Table(data, colWidths=[236, 60, 106, 106], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eaf0ff")),
                                   ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#d5dfef")),
                                   ("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.extend([table, Spacer(1, 10), p(f"Погоджена сума: {format_money(order.approved_total or order.total_cost)}"),
                      p(f"Облікована оплата: {format_money(order.paid_amount)}")])
        if order.completed_at:
            story.append(p(f"Дата завершення: {date_label(order.completed_at)}"))
        else:
            story.append(p("Ремонт виконано. Дату видачі буде зафіксовано при завершенні заявки."))
        story.append(p(f"Гарантійний строк: {order.warranty_days} дн. від завершення заявки."))
        if order.warranty_expires_at:
            story.append(p(f"Гарантія до: {date_label(order.warranty_expires_at)}"))
        story.append(p("Для перевірки гарантійного випадку надайте цей талон і пристрій. Гарантія поширюється на перелічені роботи й встановлені деталі.", small))
        link = f"{PUBLIC_URL}/orders/{order.id}#warranty"
    else:
        story.append(p("Характеристики пристрою", heading))
        story.extend(p(f"{SPEC_LABELS.get(key, key)}: {value}", small) for key, value in device.specifications.items())
        story.extend([p(f"Стан корпусу: {order.cosmetic_notes or device.cosmetic_condition or 'Не зазначено'}"),
                      p(f"Комплектація: {order.completeness or 'Не зазначено'}"),
                      p(f"Опис несправності: {order.problem_description}"),
                      p("Роботи виконуються після діагностики та погодження кошторису. Збережіть квитанцію для отримання пристрою.", small)])
        link = f"{PUBLIC_URL}/track/{order.order_number}"
    qr = Image(qr_image(link), width=76, height=76)
    qr.hAlign = "LEFT"
    story.extend([Spacer(1, 10), p("Працівник __________________    Клієнт __________________"), qr,
                  p("Відскануйте код для перегляду інформації.", small)])
    SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, title=title).build(story)
    return output.getvalue()

@router.get("/passports/{device_id}/qr")
def passport_qr(device_id: int, db: Db, user: Current):
    access_device(db, device_id, user)
    return Response(qr_image(f"{PUBLIC_URL}/passports/{device_id}").getvalue(), media_type="image/png")

@router.get("/orders/{order_id}/pdf/{kind}")
def pdf(order_id: int, kind: str, db: Db, user: Current):
    order = access_order(db, order_id, user)
    if kind not in ("receipt", "warranty"):
        fail(404, "Документ не знайдено.")
    certificate = kind == "warranty"
    if certificate and order.status not in ("ready_for_pickup", "completed"):
        fail(409, "Гарантійний талон стане доступним після ремонту.")
    return Response(generate_pdf(db, order, certificate), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{order.order_number}-{kind}.pdf"',
                             "Cache-Control": "private, no-store"})
