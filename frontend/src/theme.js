import { ref } from 'vue'
// Тема інтерфейсу: 'light', 'dark' або 'system' (як в операційній системі). Вибір зберігається в браузері.
const KEY = 'techdesk-theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')
function stored() { try { return localStorage.getItem(KEY) || 'system' } catch { return 'system' } }
export const mode = ref(stored())
export const resolved = ref('light')
function apply() {
  resolved.value = mode.value === 'system' ? (media.matches ? 'dark' : 'light') : mode.value
  document.documentElement.dataset.theme = resolved.value
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', resolved.value === 'dark' ? '#0f1115' : '#f5f6f8')
}
export function setMode(value) {
  mode.value = value
  try { localStorage.setItem(KEY, value) } catch {}
  apply()
}
media.addEventListener('change', apply)
apply()
// Значення CSS-змінної поточної теми (для Chart.js, який не розуміє var()).
export function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() }
