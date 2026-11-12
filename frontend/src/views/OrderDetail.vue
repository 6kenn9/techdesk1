<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, BadgeCheck, Check, CircleDollarSign, CircleX, Download, Inbox, PackageCheck, Plus, Search, ShieldCheck, Store, Trash2, Truck, Wrench } from 'lucide-vue-next'
import { api, download } from '../api'
import { ageLabel, approvals, date, dateTime, money, specLabels, stageNotes, statuses } from '../domain'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
import Timeline from '../components/Timeline.vue'
import Modal from '../components/Modal.vue'
import PhotoGallery from '../components/PhotoGallery.vue'
import DeliveryFields from '../components/DeliveryFields.vue'
import StarRating from '../components/StarRating.vue'
import Warranty from '../components/Warranty.vue'

const id = useRoute().params.id, session = useSession(), base = '/orders/' + id
const item = ref(null), error = ref(''), busy = ref(false), modal = ref('')
const catalog = ref([]), inventory = ref([]), workers = ref([]), deviceWarranty = ref(null)

// Форми
const edit = reactive({ diagnostics: '', internal_notes: '' })
const work = reactive({ service_id: null, work_name: '', price: '', field: '', value: '' })
const spare = reactive({ part_id: null, quantity: 1 })
const addMode = ref('work')
const approval = reactive({ approved: true, comment: '' })
const control = reactive({ master_id: null, warranty_days: 90 })
const cancelReason = ref(''), returnReason = ref('')
const payment = reactive({ amount: 0, method: 'cash', note: '' })
const methods = { cash: 'Готівка', card: 'Картка', transfer: 'Переказ' }
const deliveryForm = ref({ method: 'pickup', city: '', branch: '' }), ttn = ref('')
const review = reactive({ rating: 0, comment: '' })

// Що дозволено на поточному етапі
const staffWrite = computed(() => session.admin || (session.staff && (!item.value?.master_id || item.value.master_id === session.user.id)))
const draft = computed(() => staffWrite.value && ['registered', 'diagnostics'].includes(item.value?.status))
// Кошторис складають під час діагностики й доповнюють під час ремонту (доплату погоджує клієнт).
const diagnosing = computed(() => staffWrite.value && ['diagnostics', 'in_repair'].includes(item.value?.status))
// Клієнт хоч раз погодив кошторис: ремонт розпочато, встановлені деталі не повертаються на склад.
const started = computed(() => item.value?.approved_total != null)
const repaired = computed(() => ['ready_for_pickup', 'completed'].includes(item.value?.status))
const active = computed(() => !['completed', 'cancelled', 'returned'].includes(item.value?.status))
const pending = computed(() => item.value?.status === 'waiting_approval' && item.value?.client_approval_status === 'pending')
const due = computed(() => Number(item.value?.total_cost || 0) - Number(item.value?.paid_amount || 0))
const shipping = computed(() => item.value?.delivery_method === 'nova_poshta')
// Для скасованої заявки спосіб ще можна змінити: пристрій повертають самовивозом або Новою Поштою.
const canChangeDelivery = computed(() => (active.value || item.value?.status === 'cancelled') && !item.value?.delivery_ttn && (!session.staff || staffWrite.value))
const clientCanCancel = computed(() => item.value?.status === 'registered' ||
  (item.value?.status === 'waiting_approval' && item.value?.client_approval_status === 'rejected' && !started.value))
const tracking = computed(() => 'https://novaposhta.ua/tracking/?cargo_number=' + item.value?.delivery_ttn)
const selectedPart = computed(() => inventory.value.find(part => part.id === spare.part_id))
// Гарантія за попереднім ремонтом цього пристрою: майстер має побачити її до складання кошторису.
const earlierWarranty = computed(() => active.value && !item.value?.is_warranty_case && deviceWarranty.value?.order_number !== item.value?.order_number ? deviceWarranty.value : null)

// Роботи й запчастини одним списком для таблиці кошторису
const estimateRows = computed(() => item.value ? [
  ...item.value.works.map(line => ({ key: 'w' + line.id, kind: 'work', id: line.id, name: line.work_name, quantity: 1, sum: line.price })),
  ...item.value.parts.map(line => ({ key: 'p' + line.id, kind: 'part', id: line.id, name: line.part_name, quantity: line.quantity, sum: line.total_sale_price, part: line })),
] : [])

function assign(data, sync = true) {
  item.value = data
  if (sync) {
    edit.diagnostics = data.diagnostics
    edit.internal_notes = data.internal_notes || ''
    control.master_id = data.master_id
    control.warranty_days = data.warranty_days
  }
}
async function loadStock() { inventory.value = await api('/warehouse/parts') }

let refresh
onMounted(async () => {
  try {
    assign(await api(base))
    // Посилання з кабінету й QR-коду ведуть одразу до кошторису або документів.
    // getElementById, а не querySelector: хеш на кшталт «#1abc» не є коректним CSS-селектором і кинув би помилку.
    if (location.hash) nextTick(() => {
      try { document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView() } catch { /* некоректний хеш — лишаємося вгорі */ }
    })
    if (session.staff) {
      const [services, people, passport] = await Promise.all([api('/warehouse/services'), api('/users?role=master'), api('/passports/' + item.value.device_id), loadStock()])
      catalog.value = services
      workers.value = people.filter(person => person.is_active)
      deviceWarranty.value = passport.warranty
    } else {
      // Клієнт бачить зміни етапу без перезавантаження сторінки.
      refresh = setInterval(async () => {
        if (busy.value || modal.value || document.hidden) return
        try {
          const current = await api(base)
          if (!busy.value && !modal.value) assign(current)
        } catch (e) { error.value = e.message }
      }, 15000)
    }
  } catch (e) { error.value = e.message }
})
onUnmounted(() => clearInterval(refresh))

async function action(path, method, data, message, refreshStock = false) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    assign(await api(base + path, { method, data }), path === '' || path === '/status')
    modal.value = ''
    if (refreshStock) await loadStock()
    if (message) session.notify(message)
    return true
  } catch (e) {
    error.value = e.message
    session.notify(e.message, 'error')
    return false
  } finally { busy.value = false }
}
function transition(status, comment = '') { return action('/status', 'PATCH', { status, comment }, 'Етап заявки оновлено.', status === 'cancelled') }
function since(value) { const age = ageLabel(value); return age === 'сьогодні' ? 'сьогодні' : age + ' тому' }

function openPayment() { payment.amount = Number(due.value.toFixed(2)); payment.method = 'cash'; payment.note = ''; modal.value = 'payment' }
function openDelivery() { deliveryForm.value = { method: item.value.delivery_method, city: item.value.delivery_city, branch: item.value.delivery_branch }; modal.value = 'delivery' }
function openShip() { ttn.value = ''; modal.value = 'ship' }
function openReturn() { returnReason.value = ''; modal.value = 'return' }
function openCancel() { cancelReason.value = ''; modal.value = session.staff ? 'cancel' : 'client-cancel' }
function approve(value) { approval.approved = value; approval.comment = ''; modal.value = 'approval' }
function submitApproval() {
  return action('/approve-cost', 'POST', { ...approval, expected_total: item.value.total_cost, estimate_version: item.value.estimate_version },
    approval.approved ? 'Кошторис погоджено.' : 'Кошторис відхилено.')
}
async function clientCancel() { if (await action('/cancel', 'POST', { comment: cancelReason.value }, 'Заявку скасовано.')) cancelReason.value = '' }
async function rate() { if (await action('/rating', 'POST', { rating: review.rating, comment: review.comment }, 'Дякуємо за оцінку.')) Object.assign(review, { rating: 0, comment: '' }) }

async function addWork() {
  const data = { service_id: work.service_id, work_name: work.work_name || null, price: work.price === '' ? null : work.price,
    updates_passport_spec: work.field && work.value ? { [work.field]: work.value } : {} }
  if (await action('/works', 'POST', data, 'Роботу додано.')) Object.assign(work, { service_id: null, work_name: '', price: '', field: '', value: '' })
}
async function addPart() {
  if (await action('/parts', 'POST', { ...spare }, 'Деталь зарезервовано зі складу.', true)) Object.assign(spare, { part_id: null, quantity: 1 })
}
function removeRow(row) {
  return row.kind === 'work'
    ? action('/works/' + row.id, 'DELETE', undefined, 'Роботу видалено.')
    : action('/parts/' + row.id, 'DELETE', undefined, 'Деталь повернено на склад.', true)
}
function saveControl() {
  const data = { warranty_days: control.warranty_days }
  if (session.admin) data.master_id = control.master_id
  return action('', 'PUT', data, 'Зміни збережено.')
}
async function toggleWarranty(event) {
  if (!await action('', 'PUT', { is_warranty_case: event.target.checked }, 'Ознаку гарантійного випадку оновлено.')) event.target.checked = item.value.is_warranty_case
}
async function pdf(kind) {
  try { await download(base + '/pdf/' + kind, item.value.order_number + (kind === 'receipt' ? '-квитанція.pdf' : '-гарантія.pdf')) }
  catch (e) { session.notify(e.message, 'error') }
}
async function upgrade(line) {
  try {
    await api('/passports/' + item.value.device_id + '/upgrade-spec', { method: 'POST', data: {
      order_id: item.value.id, field_name: line.spec_upgrade_target, new_value: line.spec_upgrade_value, change_reason: line.part_name } })
    session.notify('Характеристику оновлено в паспорті.')
  } catch (e) { session.notify(e.message, 'error') }
}

// Підказка працівнику: одна головна дія для поточного етапу.
const guide = computed(() => {
  const o = item.value
  if (!o || !session.staff) return null
  const cancel = { label: 'Скасувати заявку', kind: 'danger', run: openCancel }
  const only = list => staffWrite.value ? list : []
  switch (o.status) {
    case 'registered':
      if (!o.master_id) return session.admin
        ? { title: 'Призначте майстра', text: 'Без відповідального майстра діагностику не почати. Оберіть його в блоці «Заявка» праворуч.', tone: 'warn', actions: [cancel] }
        : { title: 'Заявка вільна', text: 'Візьміть її, щоб почати діагностику.', actions: [{ label: 'Взяти заявку', kind: 'primary', run: () => action('', 'PUT', { master_id: session.user.id }, 'Заявку закріплено за вами.') }] }
      return { title: 'Почніть діагностику', text: 'Огляньте пристрій і сфотографуйте зовнішній стан.',
        actions: only([{ label: 'Почати діагностику', kind: 'primary', run: () => transition('diagnostics') }, cancel]) }
    case 'diagnostics':
      return { title: 'Складіть кошторис',
        text: o.diagnostics ? `У кошторисі ${estimateRows.value.length} поз. на ${money(o.total_cost)}. Коли все готово, надішліть клієнту.` : 'Внесіть висновок діагностики, додайте роботи й запчастини.',
        actions: only([{ label: 'Надіслати кошторис клієнту', kind: 'primary', run: () => transition('waiting_approval'), disabled: !o.diagnostics || !estimateRows.value.length }, cancel]) }
    case 'waiting_approval':
      if (o.client_approval_status === 'rejected' && started.value) return { title: 'Клієнт відмовився від доплати', tone: 'danger',
        text: `${o.approval_comment ? o.approval_comment + '. ' : ''}Продовжте ремонт у погодженому обсязі (${money(o.approved_total)}) і приберіть додаткові позиції, або скасуйте ремонт.`,
        actions: only([{ label: 'Продовжити ремонт', kind: 'primary', run: () => transition('in_repair') }, cancel]) }
      if (o.client_approval_status === 'rejected') return { title: 'Клієнт відхилив кошторис', text: o.approval_comment || 'Зв’яжіться з клієнтом і уточніть перелік робіт.', tone: 'danger',
        actions: only([{ label: 'Уточнити кошторис', kind: 'primary', run: () => transition('diagnostics') }, cancel]) }
      if (o.client_approval_status === 'approved') return { title: 'Кошторис погоджено', text: `Клієнт погодив ${money(o.total_cost)}. Можна починати роботи.`, tone: 'ok',
        actions: only([{ label: 'Почати ремонт', kind: 'primary', run: () => transition('in_repair') }, cancel]) }
      return { title: 'Очікуємо рішення клієнта', text: `Кошторис на ${money(o.total_cost)} надіслано ${since(o.stage_since)}.`, tone: 'wait',
        actions: [...(session.admin ? [{ label: 'Записати згоду', kind: 'primary', run: () => approve(true) }, { label: 'Записати відмову', run: () => approve(false) }] : []),
          ...only([...(started.value ? [] : [{ label: 'Уточнити кошторис', run: () => transition('diagnostics') }]), cancel])] }
    case 'in_repair':
      if (o.client_approval_status === 'pending') return { title: 'Потрібна згода на доплату', tone: 'warn',
        text: `Кошторис зріс до ${money(o.total_cost)}, клієнт погодив ${money(o.approved_total)}. Надішліть клієнту на погодження або приберіть додаткові позиції.`,
        actions: only([{ label: 'Надіслати на погодження', kind: 'primary', run: () => transition('waiting_approval') }, cancel]) }
      if (o.client_approval_status === 'rejected') return { title: 'Приберіть додаткові позиції', tone: 'warn',
        text: `Клієнт погодив лише ${money(o.approved_total)}. Видаліть позиції понад цю суму, щоб завершити ремонт.`, actions: only([cancel]) }
      return { title: 'Виконайте ремонт', text: 'Після перевірки позначте пристрій готовим. Знайшли ще несправність? Додайте її в кошторис: доплату погодить клієнт.',
        actions: only([{ label: 'Готова до видачі', kind: 'primary', run: () => transition('ready_for_pickup') }, cancel]) }
    case 'ready_for_pickup': {
      const giveBack = { label: 'Повернути без видачі', run: openReturn }
      if (due.value > 0) return { title: 'Прийміть оплату', text: `До сплати ${money(due.value)}. Після оплати заявку можна ${shipping.value ? 'відправити Новою Поштою' : 'завершити'}.`, tone: 'warn',
        actions: only([{ label: `Прийняти оплату ${money(due.value)}`, kind: 'primary', run: openPayment }, giveBack]) }
      if (shipping.value && !o.delivery_ttn) return { title: 'Відправте Новою Поштою', text: `${o.delivery_city}, ${o.delivery_branch}. Оформіть накладну й внесіть її номер.`, tone: 'warn',
        actions: only([{ label: 'Внести номер накладної', kind: 'primary', run: openShip }, giveBack]) }
      if (shipping.value) return { title: 'Пристрій відправлено', text: `Накладна ${o.delivery_ttn}. Завершіть заявку, щоб почався гарантійний строк.`, tone: 'ok',
        actions: only([{ label: 'Завершити заявку', kind: 'primary', run: () => transition('completed') }]) }
      return { title: 'Видайте пристрій', text: 'Оплату отримано. Завершіть заявку, щоб почався гарантійний строк.', tone: 'ok',
        actions: only([{ label: 'Завершити й видати', kind: 'primary', run: () => transition('completed') }, giveBack]) }
    }
    case 'cancelled':
      if (shipping.value && !o.delivery_ttn) return { title: 'Поверніть пристрій Новою Поштою', text: `${o.delivery_city}, ${o.delivery_branch}. Оформіть накладну й внесіть її номер, потім закрийте заявку.`, tone: 'warn',
        actions: only([{ label: 'Внести номер накладної', kind: 'primary', run: openShip }]) }
      return { title: 'Поверніть пристрій клієнту', tone: 'warn',
        text: shipping.value ? `Накладна ${o.delivery_ttn}. Закрийте заявку.` : 'Ремонт не виконується, пристрій ще в сервісі. Коли клієнт його забере, позначте це.',
        actions: only([{ label: 'Пристрій повернуто', kind: 'primary', run: openReturn }]) }
  }
  return null
})

// Стан ремонту для клієнта: базові тексти з domain.js, уточнені сумою, доставкою й гарантією.
const heroIcons = { registered: Inbox, diagnostics: Search, waiting_approval: CircleDollarSign, in_repair: Wrench, ready_for_pickup: PackageCheck, completed: BadgeCheck, cancelled: CircleX, returned: PackageCheck }
const heroTones = { waiting_approval: 'warn', ready_for_pickup: 'ok', completed: 'ok', cancelled: 'muted', returned: 'muted' }
const hero = computed(() => {
  const o = item.value
  if (!o) return null
  let [title, text] = stageNotes[o.status]
  let icon = heroIcons[o.status], tone = heroTones[o.status] || ''
  if (o.status === 'waiting_approval') {
    if (o.client_approval_status === 'rejected' && started.value) { title = 'Доплату відхилено'; text = `Майстер завершить ремонт у погодженому раніше обсязі (${money(o.approved_total)}).`; icon = CircleX; tone = 'danger' }
    else if (o.client_approval_status === 'rejected') { title = 'Кошторис відхилено'; text = 'Майстер уточнить перелік робіт і зв’яжеться з вами. Якщо ремонт не потрібен, заявку можна скасувати.'; icon = CircleX; tone = 'danger' }
    else if (started.value) { title = 'Потрібна згода на доплату'; text = `Під час ремонту виявлено ще несправність. Нова сума ${money(o.total_cost)}, раніше погоджено ${money(o.approved_total)}. Без вашої згоди додаткові роботи не виконуватимуться.` }
    else text = `Ремонт коштуватиме ${money(o.total_cost)}. Перегляньте кошторис нижче: без вашої згоди роботи не почнуться.`
  }
  if (o.status === 'in_repair' && o.client_approval_status === 'pending') {
    title = 'Ремонт призупинено'; icon = CircleDollarSign; tone = 'warn'
    text = 'Під час ремонту знайдено ще несправність. Майстер надішле кошторис доплати на погодження; без вашої згоди додаткові роботи не виконуються.'
  }
  if (o.status === 'in_repair' && o.client_approval_status === 'rejected') text = `Ремонт триває в погодженому раніше обсязі (${money(o.approved_total)}).`
  if (o.status === 'ready_for_pickup') {
    const pay = due.value > 0 ? `До сплати ${money(due.value)}. ` : 'Оплату отримано. '
    if (!shipping.value) text = pay + 'Заберіть пристрій, назвавши номер заявки.'
    else if (o.delivery_ttn) { title = 'Пристрій у дорозі'; text = `Відправлено Новою Поштою, накладна ${o.delivery_ttn}.`; icon = Truck }
    else { title = 'Готуємо відправку'; text = pay + `Відправимо пристрій у ${o.delivery_city}, ${o.delivery_branch}.`; icon = Truck }
  }
  if (o.status === 'completed' && o.warranty_expires_at) text = `Гарантія діє до ${date(o.warranty_expires_at).replace(/\.$/, '')}.`
  return { icon, title, text, tone }
})
</script>

<template>
  <RouterLink :to="session.staff ? '/orders' : '/my-cabinet'" class="back"><ArrowLeft :size="16"/> До переліку заявок</RouterLink>
  <p v-if="error" class="error" role="alert">{{ error }}</p>

  <template v-if="item">
    <div class="page-head">
      <div class="page-title">
        <h1 class="mono">{{ item.order_number }}</h1>
        <span class="record-meta">{{ item.device }} · <span class="mono">{{ item.serial_number || 'S/N не вказано' }}</span></span>
      </div>
      <Stage :status="item.status"/>
    </div>

    <div class="stack">
      <!-- Працівник: наступний крок і єдина головна кнопка -->
      <section v-if="guide" class="next-step" :class="guide.tone">
        <div>
          <small>Наступний крок</small>
          <strong>{{ guide.title }}</strong>
          <p>{{ guide.text }}</p>
        </div>
        <div v-if="guide.actions.length" class="actions">
          <button v-for="button in guide.actions" :key="button.label" class="button" :class="button.kind" :disabled="busy || button.disabled" @click="button.run()">{{ button.label }}</button>
        </div>
      </section>

      <!-- Клієнт: що зараз відбувається з пристроєм -->
      <section v-if="!session.staff" class="status-hero" :class="hero.tone">
        <span class="status-hero-icon"><component :is="hero.icon" :size="26"/></span>
        <div class="status-hero-body">
          <h2>{{ hero.title }}</h2>
          <p>{{ hero.text }}</p>
          <dl class="hero-meta">
            <div><dt>Майстер</dt><dd>{{ item.master || 'буде призначено' }}</dd></div>
            <div><dt>На цьому етапі</dt><dd>{{ ageLabel(item.stage_since) }}</dd></div>
            <div><dt>Прийнято</dt><dd>{{ date(item.created_at) }}</dd></div>
          </dl>
          <div v-if="clientCanCancel" class="actions">
            <button class="button" @click="openCancel"><CircleX :size="17"/> Скасувати заявку</button>
          </div>
        </div>
      </section>

      <!-- Гарантія: помітно і вгорі -->
      <div v-if="item.is_warranty_case" class="alert warranty">
        <ShieldCheck :size="22"/>
        <div><strong>Гарантійний випадок</strong><p>Роботи й запчастини за цією заявкою безкоштовні для клієнта.</p></div>
      </div>
      <Warranty v-else-if="earlierWarranty" :warranty="earlierWarranty"/>
      <div v-if="item.warranty_claim && !item.is_warranty_case && active" class="alert warranty">
        <ShieldCheck :size="22"/>
        <div v-if="session.staff"><strong>Клієнт просить гарантійний ремонт</strong><p>Перевірте, чи несправність пов’язана з попереднім ремонтом. Якщо так, позначте «Гарантійний випадок» у блоці «Заявка».</p></div>
        <div v-else><strong>Гарантійне звернення</strong><p>Майстер перевірить, чи випадок гарантійний. Якщо так, ремонт буде безкоштовним.</p></div>
      </div>

      <section class="card">
        <div class="section-head"><h2>Хід ремонту</h2></div>
        <Timeline :status="item.status"/>
      </section>

      <div class="cols">
        <div class="stack">
          <!-- Несправність і діагностика -->
          <section class="card">
            <div class="section-head"><h2>Несправність і діагностика</h2></div>
            <h3>Зі слів клієнта</h3>
            <p class="wrap-text">{{ item.problem_description }}</p>
            <p v-if="item.cosmetic_notes" class="wrap-text">Зовнішній стан: {{ item.cosmetic_notes }}</p>

            <form v-if="diagnosing" class="form-stack" @submit.prevent="action('', 'PUT', { ...edit }, 'Дані діагностики збережено.')">
              <label>Висновок діагностики
                <textarea v-model.trim="edit.diagnostics" maxlength="4000" placeholder="Що виявлено і що потрібно зробити"></textarea>
              </label>
              <label>Внутрішні примітки (клієнт їх не бачить)
                <textarea v-model.trim="edit.internal_notes" maxlength="4000"></textarea>
              </label>
              <div><button class="button" :disabled="busy">Зберегти діагностику</button></div>
            </form>
            <template v-else>
              <h3>Висновок діагностики</h3>
              <p class="wrap-text">{{ item.diagnostics || 'З’явиться після діагностики.' }}</p>
              <p v-if="item.internal_notes" class="wrap-text">Внутрішні примітки: {{ item.internal_notes }}</p>
            </template>
          </section>

          <!-- Кошторис: роботи, запчастини, підсумок і оплати в одному місці -->
          <section id="estimate" class="card">
            <div class="section-head">
              <h2>Кошторис</h2>
              <span v-if="!['registered', 'diagnostics'].includes(item.status)" class="chip">{{ approvals[item.client_approval_status] }}<template v-if="item.approved_at"> · {{ dateTime(item.approved_at) }}</template></span>
            </div>

            <div v-if="estimateRows.length" class="table-scroll">
              <table class="compact estimate-table">
                <thead>
                  <tr><th>Позиція</th><th>Кількість</th><th v-if="staffWrite" class="row-action"><span class="sr-only">Дії</span></th><th>Сума</th></tr>
                </thead>
                <tbody>
                  <tr v-for="row in estimateRows" :key="row.key">
                    <td><strong>{{ row.name }}</strong><small>{{ row.kind === 'work' ? 'Робота' : 'Запчастина' }}</small></td>
                    <td>{{ row.quantity }}</td>
                    <td v-if="staffWrite" class="row-action">
                      <button v-if="row.kind === 'part' && item.status === 'in_repair' && row.part.spec_upgrade_target" class="button small" @click="upgrade(row.part)"><Wrench :size="15"/> Оновити паспорт</button>
                      <button v-if="draft || diagnosing" class="icon-button" :aria-label="row.kind === 'work' ? 'Видалити роботу' : 'Повернути запчастину на склад'" :disabled="busy" @click="removeRow(row)"><Trash2 :size="16"/></button>
                    </td>
                    <td class="num">{{ money(row.sum) }}</td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr v-if="item.is_warranty_case"><td :colspan="staffWrite ? 3 : 2">Покривається гарантією</td><td class="num">−{{ money(Number(item.works_total) + Number(item.parts_total)) }}</td></tr>
                  <tr class="total"><td :colspan="staffWrite ? 3 : 2">Разом</td><td class="num">{{ money(item.total_cost) }}</td></tr>
                  <tr v-if="started && Number(item.approved_total) !== Number(item.total_cost)"><td :colspan="staffWrite ? 3 : 2">Раніше погоджено клієнтом</td><td class="num">{{ money(item.approved_total) }}</td></tr>
                  <tr v-if="repaired"><td :colspan="staffWrite ? 3 : 2">Оплачено</td><td class="num">{{ money(item.paid_amount) }}</td></tr>
                  <tr v-if="repaired && due > 0" class="due"><td :colspan="staffWrite ? 3 : 2">Залишок до сплати</td><td class="num">{{ money(due) }}</td></tr>
                </tfoot>
              </table>
            </div>
            <div v-else class="empty">{{ diagnosing ? 'Кошторис порожній. Додайте першу роботу або запчастину нижче.' : 'Кошторис з’явиться після діагностики.' }}</div>

            <p v-if="item.approval_comment && (session.staff || item.client_approval_status === 'rejected')" class="wrap-text">Коментар до рішення: {{ item.approval_comment }}</p>

            <ul v-if="item.payments?.length" class="payments">
              <li v-for="pay in item.payments" :key="pay.id">
                <span>{{ methods[pay.method] }}<small>{{ dateTime(pay.created_at) }}{{ pay.note ? ' · ' + pay.note : '' }}</small></span>
                <strong>{{ money(pay.amount) }}</strong>
              </li>
            </ul>

            <!-- Рішення клієнта одразу під переліком і сумою -->
            <div v-if="pending && !session.staff" class="approve-box">
              <p>Погоджуючи кошторис, ви дозволяєте майстру виконати перелічені роботи на суму <strong>{{ money(item.total_cost) }}</strong>.</p>
              <div class="actions">
                <button class="button primary large" @click="approve(true)"><Check :size="18"/> Погодити {{ money(item.total_cost) }}</button>
                <button class="button danger large" @click="approve(false)">Відхилити</button>
              </div>
            </div>

            <!-- Позиції додають під час діагностики; під час ремонту — додаткові (доплату погоджує клієнт) -->
            <p v-if="diagnosing && item.status === 'in_repair'" class="muted">Додаткові позиції понад погоджену суму потребуватимуть згоди клієнта.</p>
            <div v-if="diagnosing" class="estimate-add">
              <div class="segmented">
                <button type="button" class="button small" :aria-pressed="addMode === 'work'" @click="addMode = 'work'">Додати роботу</button>
                <button type="button" class="button small" :aria-pressed="addMode === 'part'" @click="addMode = 'part'">Додати запчастину</button>
              </div>
              <form v-if="addMode === 'work'" class="form-grid" @submit.prevent="addWork">
                <label class="full">Робота з прейскуранта
                  <select v-model="work.service_id">
                    <option :value="null">Ввести роботу вручну</option>
                    <option v-for="service in catalog" :key="service.id" :value="service.id">{{ service.name }} · {{ money(service.default_price) }}</option>
                  </select>
                </label>
                <label>Назва роботи<input v-model.trim="work.work_name" :required="!work.service_id" maxlength="160"></label>
                <label>Власна ціна, грн<input v-model="work.price" type="number" min="0" step=".01" :required="!work.service_id"></label>
                <label>Зміна в паспорті пристрою
                  <select v-model="work.field">
                    <option value="">Без зміни</option>
                    <option v-for="(label, key) in specLabels" :key="key" :value="key">{{ label }}</option>
                  </select>
                </label>
                <label v-if="work.field">Нове значення<input v-model.trim="work.value" required maxlength="160"></label>
                <div class="full"><button class="button" :disabled="busy"><Plus :size="17"/> Додати роботу</button></div>
              </form>
              <form v-else class="form-grid" @submit.prevent="addPart">
                <label>Запчастина зі складу
                  <select v-model="spare.part_id" required>
                    <option :value="null">Оберіть позицію</option>
                    <option v-for="part in inventory" :key="part.id" :value="part.id" :disabled="!part.quantity_in_stock">{{ part.name }} · {{ part.quantity_in_stock }} шт.</option>
                  </select>
                </label>
                <label>Кількість<input v-model.number="spare.quantity" type="number" min="1" :max="selectedPart?.quantity_in_stock" required></label>
                <div class="full"><button class="button" :disabled="busy"><Plus :size="17"/> Додати зі складу</button></div>
              </form>
            </div>

            <div v-if="staffWrite && item.status === 'ready_for_pickup' && due > 0" class="actions" style="margin-top:12px">
              <button class="button" :disabled="busy" @click="openPayment"><CircleDollarSign :size="17"/> Прийняти оплату</button>
            </div>
          </section>

          <PhotoGallery framed title="Фото пристрою" :device-id="item.device_id" :order-id="item.id" :can-upload="staffWrite && active"/>

          <!-- Оцінка ремонту -->
          <section v-if="item.status === 'completed' && (item.rating || !session.staff)" class="card rating-card">
            <template v-if="item.rating">
              <div class="section-head"><h2>{{ session.staff ? 'Оцінка клієнта' : 'Ваша оцінка' }}</h2><small class="muted">{{ dateTime(item.rated_at) }}</small></div>
              <StarRating :model-value="item.rating" readonly/>
              <p v-if="item.rating_comment" class="quote wrap-text">{{ item.rating_comment }}</p>
            </template>
            <form v-else class="form-stack" @submit.prevent="rate">
              <div class="section-head"><h2>Як вам ремонт?</h2></div>
              <p class="muted">Оцінку бачать адміністратор і ваш майстер.</p>
              <StarRating v-model="review.rating"/>
              <label v-if="review.rating">Коментар (необов’язково)
                <textarea v-model.trim="review.comment" maxlength="1000" rows="2" :placeholder="review.rating < 4 ? 'Що нам варто покращити?' : 'Що сподобалось?'"></textarea>
              </label>
              <div><button class="button primary" :disabled="busy || !review.rating">Надіслати оцінку</button></div>
            </form>
          </section>

          <!-- Історія етапів: згорнута, бо потрібна рідко -->
          <details class="card fold">
            <summary>Історія етапів <span class="chip">{{ item.history.length }}</span></summary>
            <ul class="log">
              <li v-for="line in item.history" :key="line.id">
                <strong>{{ statuses[line.new_status] }}</strong>
                <small>{{ dateTime(line.changed_at) }}</small>
                <p v-if="line.comment">{{ line.comment }}</p>
              </li>
            </ul>
          </details>
        </div>

        <!-- Праворуч: дані заявки, отримання, документи -->
        <aside class="stack">
          <section class="card">
            <div class="section-head">
              <h2>Заявка</h2>
              <RouterLink class="button small" :to="'/passports/' + item.device_id">Паспорт <ArrowUpRight :size="15"/></RouterLink>
            </div>
            <dl class="meta-list">
              <div><dt>Клієнт</dt><dd>{{ item.client }}</dd></div>
              <div><dt>Майстер</dt><dd>{{ item.master || 'Не призначено' }}</dd></div>
              <div><dt>Прийнято</dt><dd>{{ date(item.created_at) }}</dd></div>
              <div><dt>Пріоритет</dt><dd>{{ item.priority === 'urgent' ? 'Терміновий' : 'Звичайний' }}</dd></div>
              <div><dt>Комплектація</dt><dd>{{ item.completeness || 'Не зазначено' }}</dd></div>
              <div><dt>Гарантія на ремонт</dt><dd>{{ item.warranty_expires_at ? 'до ' + date(item.warranty_expires_at) : item.warranty_days + ' дн. після видачі' }}</dd></div>
            </dl>

            <template v-if="staffWrite && active">
              <hr class="card-divider">
              <form class="form-stack" @submit.prevent="saveControl">
                <label v-if="session.admin">Відповідальний майстер
                  <select v-model="control.master_id">
                    <option :value="null">Не призначено</option>
                    <option v-for="worker in workers" :key="worker.id" :value="worker.id">{{ worker.full_name }} · активних: {{ worker.active_orders }}</option>
                  </select>
                </label>
                <label>Гарантійний строк, днів
                  <input v-model.number="control.warranty_days" type="number" min="0" max="3650" required>
                </label>
                <label v-if="draft" class="check">
                  <input type="checkbox" :checked="item.is_warranty_case" :disabled="busy" @change="toggleWarranty"> Гарантійний випадок (безкоштовно для клієнта)
                </label>
                <div><button class="button" :disabled="busy">Зберегти</button></div>
              </form>
            </template>
          </section>

          <section class="card">
            <div class="section-head">
              <h2>Отримання пристрою</h2>
              <button v-if="canChangeDelivery" class="button small" @click="openDelivery">Змінити</button>
            </div>
            <p v-if="!shipping" class="icon-line"><Store :size="18"/> Самовивіз із сервісного центру</p>
            <template v-else>
              <p class="icon-line"><Truck :size="18"/> Нова Пошта</p>
              <dl class="meta-list">
                <div><dt>Місто</dt><dd>{{ item.delivery_city }}</dd></div>
                <div><dt>Відділення</dt><dd>{{ item.delivery_branch }}</dd></div>
                <div v-if="item.delivery_ttn"><dt>Накладна</dt><dd><a class="ttn" :href="tracking" target="_blank" rel="noopener">{{ item.delivery_ttn }}</a></dd></div>
              </dl>
              <button v-if="staffWrite && !item.delivery_ttn && ((item.status === 'ready_for_pickup' && due <= 0) || item.status === 'cancelled')" class="button" style="margin-top:10px" :disabled="busy" @click="openShip"><Truck :size="17"/> Внести номер накладної</button>
            </template>
          </section>

          <section id="warranty" class="card">
            <div class="section-head"><h2>Документи</h2></div>
            <div class="form-stack">
              <button class="button" @click="pdf('receipt')"><Download :size="17"/> Квитанція про приймання</button>
              <button v-if="repaired" class="button" @click="pdf('warranty')"><Download :size="17"/> Гарантійний талон та акт</button>
              <small v-else>Гарантійний талон стане доступним після ремонту.</small>
            </div>
          </section>
        </aside>
      </div>
    </div>

    <!-- Модальні вікна -->
    <Modal v-if="modal === 'payment'" title="Прийняти оплату" @close="modal = ''">
      <form class="form-stack" @submit.prevent="action('/payments', 'POST', { amount: payment.amount, method: payment.method, note: payment.note }, 'Оплату обліковано.')">
        <p>До сплати: <strong>{{ money(due) }}</strong>. Можна прийняти частину, а решту іншим способом.</p>
        <fieldset class="tile-group">
          <legend>Спосіб оплати</legend>
          <div class="segmented pay-methods">
            <button v-for="(label, key) in methods" :key="key" type="button" class="button small" :aria-pressed="payment.method === key" @click="payment.method = key">{{ label }}</button>
          </div>
        </fieldset>
        <label>Сума, грн<input v-model.number="payment.amount" type="number" min="0.01" :max="due" step=".01" required></label>
        <label>Примітка<input v-model.trim="payment.note" maxlength="200" placeholder="Необов’язково: номер чека, термінал"></label>
        <button class="button primary" :disabled="busy">Зберегти оплату</button>
      </form>
    </Modal>

    <Modal v-if="modal === 'delivery'" title="Спосіб отримання" @close="modal = ''">
      <form class="form-stack" @submit.prevent="action('/delivery', 'PUT', deliveryForm, 'Спосіб отримання оновлено.')">
        <DeliveryFields v-model="deliveryForm"/>
        <button class="button primary" :disabled="busy">Зберегти</button>
      </form>
    </Modal>

    <Modal v-if="modal === 'ship'" title="Відправка Новою Поштою" @close="modal = ''">
      <form class="form-stack" @submit.prevent="action('/shipment', 'POST', { ttn }, 'Накладну збережено, клієнта сповіщено.')">
        <p>Отримувач: <strong>{{ item.client }}</strong><br>{{ item.delivery_city }}, {{ item.delivery_branch }}</p>
        <label>Номер експрес-накладної (ТТН)
          <input v-model.trim="ttn" class="ttn" required inputmode="numeric" pattern="[0-9 ]{14,17}" maxlength="17" placeholder="20 4500 0000 0001">
        </label>
        <button class="button primary" :disabled="busy">Зберегти та сповістити клієнта</button>
      </form>
    </Modal>

    <Modal v-if="modal === 'client-cancel'" title="Скасувати заявку?" @close="modal = ''">
      <form class="form-stack" @submit.prevent="clientCancel">
        <p v-if="item.status === 'registered'">Пристрій ще не взяли в роботу, тож заявку можна скасувати. Якщо ви вже передали пристрій у центр, заберіть його за номером заявки.</p>
        <p v-else>Ви відмовилися від кошторису. Після скасування заберіть пристрій у сервісному центрі або дочекайтеся відправки Новою Поштою.</p>
        <label>Причина (необов’язково)
          <textarea v-model.trim="cancelReason" maxlength="1000" placeholder="Наприклад: проблема зникла"></textarea>
        </label>
        <button class="button danger" :disabled="busy">Скасувати заявку</button>
      </form>
    </Modal>

    <Modal v-if="modal === 'cancel'" title="Скасувати заявку?" @close="modal = ''">
      <form class="form-stack" @submit.prevent="transition('cancelled', cancelReason)">
        <p v-if="started">Ремонт уже розпочато: встановлені запчастини не повертаються на склад. Невикористані приберіть з кошторису до скасування.</p>
        <p v-else>Зарезервовані запчастини буде повернено на склад.</p>
        <label>Причина скасування
          <textarea v-model.trim="cancelReason" :required="started" maxlength="4000"></textarea>
        </label>
        <button class="button danger" :disabled="busy">Підтвердити скасування</button>
      </form>
    </Modal>

    <Modal v-if="modal === 'return'" title="Повернути пристрій клієнту" @close="modal = ''">
      <form class="form-stack" @submit.prevent="transition('returned', returnReason)">
        <p v-if="item.status === 'ready_for_pickup'">Пристрій віддають без звичайної видачі: клієнт його не забирає або відмовився платити. Гарантія за цією заявкою не діє.</p>
        <p v-else>Заявку буде закрито: пристрій повернуто клієнту без ремонту.</p>
        <label>{{ item.status === 'ready_for_pickup' ? 'Причина' : 'Коментар (необов’язково)' }}
          <textarea v-model.trim="returnReason" :required="item.status === 'ready_for_pickup'" maxlength="4000"></textarea>
        </label>
        <button class="button primary" :disabled="busy">Закрити заявку</button>
      </form>
    </Modal>

    <Modal v-if="modal === 'approval'" :title="approval.approved ? 'Погодження кошторису' : 'Відхилення кошторису'" @close="modal = ''">
      <form class="form-stack" @submit.prevent="submitApproval">
        <p>Підсумкова вартість: <strong class="mono">{{ money(item.total_cost) }}</strong></p>
        <label v-if="session.admin || !approval.approved">{{ session.admin ? 'Як отримано рішення клієнта' : 'Коментар до відмови' }}
          <textarea v-model.trim="approval.comment" :required="session.admin" maxlength="4000"></textarea>
        </label>
        <button class="button" :class="approval.approved ? 'primary' : 'danger'" :disabled="busy">Підтвердити рішення</button>
      </form>
    </Modal>
  </template>
</template>
