import { Laptop, Monitor, Smartphone, Tablet, Watch, Gamepad2, BatteryCharging, Cpu } from 'lucide-vue-next'

export const stages = [
  ['registered', 'Зареєстрована'], ['diagnostics', 'На діагностиці'],
  ['waiting_approval', 'Очікує погодження вартості'], ['in_repair', 'У ремонті'],
  ['ready_for_pickup', 'Готова до видачі'], ['completed', 'Завершена'],
]
export const statuses = Object.fromEntries([...stages, ['cancelled', 'Скасована']])
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
