import { ref } from 'vue'
// Тема інтерфейсу: 'light' або 'dark'. За замовчуванням світла; вибір зберігається в браузері.
const KEY = 'techdesk-theme'
function stored() {
  try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light' } catch { return 'light' }
}
export const mode = ref(stored())
// resolved збігається з mode; залишено для графіків, які перемальовуються при зміні теми.
export const resolved = mode
function apply() {
  document.documentElement.dataset.theme = mode.value
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', mode.value === 'dark' ? '#0f1115' : '#f5f6f8')
}
export function setMode(value) {
  mode.value = value === 'dark' ? 'dark' : 'light'
  try { localStorage.setItem(KEY, mode.value) } catch {}
  apply()
}
apply()
// Значення CSS-змінної поточної теми (для Chart.js, який не розуміє var()).
export function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() }
