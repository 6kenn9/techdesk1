import { Laptop, Monitor, Smartphone, Tablet, Watch, Gamepad2, BatteryCharging, Cpu } from 'lucide-vue-next'

export const stages = [
  ['registered', 'Зареєстрована'], ['diagnostics', 'На діагностиці'],
  ['waiting_approval', 'Очікує погодження вартості'], ['in_repair', 'У ремонті'],
  ['ready_for_pickup', 'Готова до видачі'], ['completed', 'Завершена'],
]
export const statuses = Object.fromEntries([...stages, ['cancelled', 'Скасована']])
// Пояснення етапів для клієнта: [короткий заголовок, що відбувається зараз і що буде далі].
export const stageNotes = {
  registered: ['Пристрій прийнято', 'Заявку зареєстровано. Майстер візьме пристрій на діагностику, зазвичай протягом робочого дня.'],
  diagnostics: ['Триває діагностика', 'Майстер шукає причину несправності. Після цього ви отримаєте кошторис на погодження.'],
  waiting_approval: ['Потрібне ваше рішення', 'Кошторис готовий. Без вашої згоди роботи не почнуться.'],
  in_repair: ['Ремонт триває', 'Майстер виконує погоджені роботи. Ми повідомимо, коли пристрій буде готовий.'],
  ready_for_pickup: ['Пристрій готовий', 'Ремонт завершено. Заберіть пристрій, назвавши номер заявки.'],
  completed: ['Ремонт завершено', 'Пристрій видано. Гарантійний талон доступний у документах заявки.'],
  cancelled: ['Заявку скасовано', 'Ремонт не виконувався. Якщо маєте питання, зверніться до сервісного центру.'],
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
}
export const categories = Object.keys(categorySpecs)
export const icons = {
  Ноутбук: Laptop, ПК: Cpu, Моноблок: Monitor, 'Міні-ПК': Cpu, Смартфон: Smartphone,
  Планшет: Tablet, 'Смарт-годинник': Watch, Консоль: Gamepad2, Монітор: Monitor, ДБЖ: BatteryCharging,
}
export const money = value => new Intl.NumberFormat('uk-UA', { style: 'currency', currency: 'UAH', maximumFractionDigits: 2 }).format(Number(value || 0))
export const date = value => value ? new Intl.DateTimeFormat('uk-UA', { dateStyle: 'medium', timeZone: 'Europe/Kyiv' }).format(new Date(value)) : '—'
export const dateTime = value => value ? new Intl.DateTimeFormat('uk-UA', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Kyiv' }).format(new Date(value)) : '—'
const dayStart = value => { const d = new Date(value); d.setHours(0, 0, 0, 0); return d }
// Календарні дні, як і в аналітиці на сервері.
export const daysSince = value => value ? Math.max(0, Math.round((dayStart(Date.now()) - dayStart(value)) / 864e5)) : 0
export const ageLabel = value => { const days = daysSince(value); return days === 0 ? 'сьогодні' : days === 1 ? '1 день' : days < 5 ? `${days} дні` : `${days} днів` }
export const STALE_DAYS = 3
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
