<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, CheckCheck, CircleX, Inbox, ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import { api } from '../api'
import { dateTime } from '../domain'
// Сповіщення працівника: нові заявки клієнтів, рішення щодо кошторису, скасування. Оновлюється кожні 30 с.
const router = useRouter()
const open = ref(false), data = ref({ unread: 0, items: [] }), root = ref(null)
let timer
async function load() {
  if (document.hidden) return
  try { data.value = await api('/notifications') } catch { /* мережа: спробуємо пізніше */ }
}
async function markAll() {
  try { await api('/notifications/read', { method: 'POST', data: {} }); await load() } catch {}
}
async function go(item) {
  open.value = false
  if (!item.read) api('/notifications/read', { method: 'POST', data: { ids: [item.id] } }).then(load).catch(() => {})
  if (item.order_id) router.push('/orders/' + item.order_id)
}
function icon(item) {
  if (item.kind === 'cancelled') return CircleX
  if (item.kind === 'decision') return item.text.includes('відхилив') ? ThumbsDown : ThumbsUp
  return Inbox
}
function outside(event) { if (open.value && root.value && !root.value.contains(event.target)) open.value = false }
onMounted(() => { load(); timer = setInterval(load, 30000); document.addEventListener('click', outside) })
onUnmounted(() => { clearInterval(timer); document.removeEventListener('click', outside) })
</script>
<template>
  <div ref="root" class="bell">
    <button class="icon-button" type="button" :aria-label="`Сповіщення: непрочитаних ${data.unread}`" :aria-expanded="open" @click="open = !open; if (open) load()">
      <Bell :size="17"/><span v-if="data.unread" class="bell-badge">{{ data.unread > 99 ? '99+' : data.unread }}</span>
    </button>
    <div v-if="open" class="bell-panel" role="dialog" aria-label="Сповіщення">
      <div class="bell-head"><strong>Сповіщення</strong><button v-if="data.unread" class="link-button" type="button" @click="markAll"><CheckCheck :size="15"/> Прочитати всі</button></div>
      <p v-if="!data.items.length" class="muted bell-empty">Поки що сповіщень немає. Тут з’являтимуться нові заявки клієнтів і їхні рішення щодо кошторису.</p>
      <button v-for="item in data.items" :key="item.id" type="button" class="bell-item" :class="{ unread: !item.read, [item.kind]: true }" @click="go(item)">
        <component :is="icon(item)" :size="17"/><span>{{ item.text }}<small>{{ dateTime(item.created_at) }}</small></span>
      </button>
    </div>
  </div>
</template>
