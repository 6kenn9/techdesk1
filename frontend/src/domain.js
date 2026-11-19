import { Laptop, Monitor, Smartphone, Tablet, Watch, Gamepad2, BatteryCharging, Cpu, Package } from 'lucide-vue-next'

export const stages = [
  ['registered', 'Зареєстрована'], ['diagnostics', 'На діагностиці'],
  ['waiting_approval', 'Очікує погодження вартості'], ['in_repair', 'У ремонті'],
  ['ready_for_pickup', 'Готова до видачі'], ['completed', 'Завершена'],
]
export const statuses = Object.fromEntries([...stages, ['cancelled', 'Скасована'], ['returned', 'Повернуто клієнту']])
// Пояснення етапів для клієнта: [короткий заголовок, що відбувається зараз і що буде далі].
export const stageNotes = {
  registered: ['Пристрій прийнято', 'Заявку зареєстровано. Майстер візьме пристрій на діагностику, зазвичай протягом робочого дня.'],
  diagnostics: ['Триває діагностика', 'Майстер шукає причину несправності. Після цього ви отримаєте кошторис на погодження.'],
  waiting_approval: ['Потрібне ваше рішення', 'Кошторис готовий. Без вашої згоди роботи не почнуться.'],
  in_repair: ['Ремонт триває', 'Майстер виконує погоджені роботи. Ми повідомимо, коли пристрій буде готовий.'],
  ready_for_pickup: ['Пристрій готовий', 'Ремонт завершено. Заберіть пристрій, назвавши номер заявки.'],
  completed: ['Ремонт завершено', 'Пристрій видано. Гарантійний талон доступний у документах заявки.'],
  cancelled: ['Заявку скасовано', 'Пристрій ще в сервісному центрі: заберіть його, назвавши номер заявки, або дочекайтеся відправки Новою Поштою.'],
  returned: ['Пристрій повернуто', 'Пристрій віддано вам, заявку закрито.'],
}
export const roles = { client: 'Клієнт', master: 'Майстер', admin: 'Адміністратор' }
export const approvals = { pending: 'Очікує рішення', approved: 'Погоджено', rejected: 'Відхилено' }
export const specLabels = {
  cpu: 'Процесор', ram: 'Оперативна пам’ять', storage: 'Накопичувач', gpu: 'Відеокарта',
  display: 'Дисплей', os: 'Операційна система', battery_health: 'Стан акумулятора',
  motherboard: 'Материнська плата', psu: 'Блок живлення', cooling: 'Корпус і охолодження',
  color: 'Колір', case_size: 'Розмір корпусу', case_material: 'Матеріал корпусу', seal: 'Стан ущільнення',
  revision: 'Ревізія плати', power: 'Потужність', ports: 'Роз’єми', condition: 'Стан компонента',
}
const computer = ['cpu', 'ram', 'storage', 'gpu']
export const categorySpecs = {
  Ноутбук: [...computer, 'display', 'os', 'battery_health'], ПК: [...computer, 'motherboard', 'psu', 'cooling'],
  Моноблок: [...computer, 'display'], 'Міні-ПК': [...computer, 'ports'],
  Смартфон: ['ram', 'storage', 'color', 'battery_health', 'display', 'os'],
  Планшет: ['ram', 'storage', 'color', 'battery_health', 'display', 'os'],
  'Смарт-годинник': ['case_size', 'case_material', 'color', 'battery_health', 'seal'],
  Консоль: ['revision', 'storage', 'ports', 'condition'], Монітор: ['display', 'ports', 'condition'],
  ДБЖ: ['power', 'ports', 'battery_health', 'condition'],
  // пристрій, якого немає в переліку (принтер, роутер тощо): що це — пишуть у полях виробника й моделі
  Інше: ['condition'],
}
export const categories = Object.keys(categorySpecs)
export const icons = {
  Ноутбук: Laptop, ПК: Cpu, Моноблок: Monitor, 'Міні-ПК': Cpu, Смартфон: Smartphone,
  Планшет: Tablet, 'Смарт-годинник': Watch, Консоль: Gamepad2, Монітор: Monitor, ДБЖ: BatteryCharging, Інше: Package,
}
export const money = value => new Intl.NumberFormat('uk-UA', { style: 'currency', currency: 'UAH', maximumFractionDigits: 2 }).format(Number(value || 0))
export const date = value => value ? new Intl.DateTimeFormat('uk-UA', { dateStyle: 'medium', timeZone: 'Europe/Kyiv' }).format(new Date(value)) : '—'
export const dateTime = value => value ? new Intl.DateTimeFormat('uk-UA', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Kyiv' }).format(new Date(value)) : '—'
const dayStart = value => { const d = new Date(value); d.setHours(0, 0, 0, 0); return d }
// Календарні дні, як і в аналітиці на сервері.
export const daysSince = value => value ? Math.max(0, Math.round((dayStart(Date.now()) - dayStart(value)) / 864e5)) : 0
export const ageLabel = value => { const days = daysSince(value); return days === 0 ? 'сьогодні' : days === 1 ? '1 день' : days < 5 ? `${days} дні` : `${days} днів` }
export const STALE_DAYS = 3
// Готовий пристрій, який не забирають, потребує нагадування клієнту.
export const PICKUP_DAYS = 5
// Скасована заявка не закрита: пристрій ще в сервісі й чекає повернення клієнту.
// скасована онлайн-заявка, пристрій якої так і не надійшов, закрита одразу
export const isClosed = order => ['completed', 'returned'].includes(order.status) || (order.status === 'cancelled' && !order.device_received_at)
// Стан роботи: у кого зараз «м’яч».
//   free — майстра ще немає; todo — наступний крок за майстром; client — чекаємо рішення клієнта щодо кошторису;
//   pickup — пристрій готовий і чекає, поки клієнт його забере; archive — заявку закрито.
export function workState(order) {
  if (isClosed(order)) return 'archive'
  if (order.status === 'cancelled') return order.master_id ? 'pickup' : 'free'
  if (!order.master_id) return 'free'
  if (order.status === 'waiting_approval') return order.client_approval_status === 'pending' ? 'client' : 'todo'
  if (order.status === 'ready_for_pickup') return order.delivery_method === 'nova_poshta' ? 'todo' : 'pickup'
  return 'todo'
}
// Що саме має зробити майстер зараз; порядок збігається з порядком етапів ремонту.
export const todoSteps = [
  ['diagnose', 'Почати діагностику', 'Пристрої чекають на огляд.'],
  ['estimate', 'Скласти кошторис', 'Внесіть висновок, роботи й запчастини, або уточніть відхилений кошторис.'],
  ['repair', 'Ремонтувати', 'Кошторис погоджено, можна працювати.'],
  ['ship', 'Відправити Новою Поштою', 'Нова Пошта: прийміть оплату, внесіть накладну, потім завершіть заявку.'],
]
export function todoStep(order) {
  if (order.status === 'registered') return 'diagnose'
  if (order.status === 'diagnostics' || (order.status === 'waiting_approval' && order.client_approval_status === 'rejected')) return 'estimate'
  if (order.status === 'in_repair' && order.client_approval_status !== 'approved') return 'estimate'
  if (order.status === 'ready_for_pickup') return 'ship'
  return 'repair'
}
// Заявка «запізнюється»: на етапі довше за норму цього стану.
export function isLate(order) {
  const state = workState(order), days = daysSince(order.stage_since)
  return state === 'pickup' ? days >= PICKUP_DAYS : state === 'free' ? days >= 1 : state === 'archive' ? false : days >= STALE_DAYS
}
// Термінові вгорі, далі ті, що найдовше стоять на етапі.
export const byUrgency = (a, b) => (b.priority === 'urgent') - (a.priority === 'urgent') || new Date(a.stage_since) - new Date(b.stage_since)
export const byClosed = (a, b) => new Date(b.completed_at || b.updated_at || b.created_at) - new Date(a.completed_at || a.updated_at || a.created_at)
// Скільки заявок вимагають дії майстра (позначка в меню): його черга плюс готові пристрої, які не забирають.
export const workload = (orders, masterId) => orders.filter(o => o.master_id === masterId && (workState(o) === 'todo' || (workState(o) === 'pickup' && isLate(o)))).length
export const problemHints = ['Не вмикається', 'Розбитий екран', 'Не заряджається', 'Повільно працює', 'Перегрівається', 'Залито рідиною', 'Не працює звук', 'Чистка та профілактика']
// «Lenovo IdeaPad 3» → виробник і модель; одне слово вважаємо і виробником, і моделлю.
export function splitModel(text) {
  const [brand, ...rest] = String(text || '').trim().split(/\s+/)
  return { brand: brand || '', model: rest.join(' ') || brand || '' }
}
export const emptyQuick = () => ({ device_category: 'Ноутбук', brand: '', model: '', title: '', serial_number: '', problem_description: '' })
export function devicePayload(form) {
  const { brand, model } = form.brand && form.model ? form : splitModel(form.title)
  return { device_category: form.device_category, brand, model, serial_number: form.serial_number.trim() || null }
}

// Номер заявки (TD-2026-0007) → id заявки, якщо користувач має до неї доступ; інакше null.
export async function orderIdByNumber(number) {
  const { api, query } = await import('./api')
  const code = String(number || '').trim().toUpperCase()
  if (!/^TD-\d{4}-\d+$/.test(code)) return null
  try {
    const found = (await api('/orders' + query({ q: code }))).find(o => o.order_number === code)
    return found ? found.id : null
  } catch {
    return null
  }
}
