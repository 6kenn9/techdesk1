<script setup>
import { computed, onMounted, ref } from 'vue'
import { ClipboardList, Flame, Hand, Hourglass, Inbox, PackageCheck, Search, Wrench } from 'lucide-vue-next'
import { api } from '../api'
import { daysSince, STALE_DAYS } from '../domain'
import { useSession } from '../state'
import OrderCard from '../components/OrderCard.vue'
const session = useSession(), items = ref([]), error = ref(''), busy = ref(false), loaded = ref(false)
const active = o => !['completed', 'cancelled'].includes(o.status)
const order = (a, b) => (b.priority === 'urgent') - (a.priority === 'urgent') || new Date(a.stage_since) - new Date(b.stage_since)
const mine = computed(() => items.value.filter(o => o.master_id === session.user.id && active(o)).sort(order))
const free = computed(() => items.value.filter(o => !o.master_id && o.status === 'registered').sort(order))
const groups = computed(() => [
  ['Почати діагностику', 'Пристрої чекають на огляд.', Inbox, o => o.status === 'registered'],
  ['Скласти кошторис', 'Внесіть висновок, роботи й запчастини.', Search, o => o.status === 'diagnostics' || (o.status === 'waiting_approval' && o.client_approval_status === 'rejected')],
  ['Ремонтувати', 'Кошторис погоджено — можна працювати.', Wrench, o => o.status === 'in_repair'],
  ['Видати клієнту', 'Прийміть оплату й завершіть заявку.', PackageCheck, o => o.status === 'ready_for_pickup'],
  ['Чекають рішення клієнта', 'Від вас нічого не потрібно, поки клієнт думає.', Hourglass, o => o.status === 'waiting_approval' && o.client_approval_status === 'pending'],
].map(([title, hint, icon, test]) => ({ title, hint, icon, list: mine.value.filter(test) })))
const stats = computed(() => [
  ['Мої активні', mine.value.length, ClipboardList, ''],
  ['Термінові', mine.value.filter(o => o.priority === 'urgent').length, Flame, 'danger'],
  [`${STALE_DAYS}+ дні на етапі`, mine.value.filter(o => daysSince(o.stage_since) >= STALE_DAYS).length, Hourglass, 'warn'],
  ['Вільні заявки', free.value.length, Hand, ''],
])
const greeting = computed(() => { const h = new Date().getHours(); return h < 12 ? 'Доброго ранку' : h < 18 ? 'Добрий день' : 'Добрий вечір' })
async function load() {
  try { items.value = await api('/orders'); error.value = '' } catch (e) { error.value = e.message } finally { loaded.value = true }
}
async function take(o) {
  busy.value = true
  try { await api('/orders/' + o.id, { method: 'PUT', data: { master_id: session.user.id } }); session.notify(`Заявку ${o.order_number} закріплено за вами.`); await load() }
  catch (e) { session.notify(e.message, 'error') } finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <div class="page-head"><div class="page-title"><h1>{{ greeting }}, {{ session.user.full_name.split(' ')[1] || session.user.full_name }}</h1></div>
    <RouterLink class="button" to="/orders"><ClipboardList :size="16"/> Увесь журнал</RouterLink></div>
  <p v-if="error" class="error">{{ error }}</p>
  <div class="stack">
    <div class="day-stats"><article v-for="[label, value, Icon, tone] in stats" :key="label" class="card day-stat" :class="value ? tone : ''"><component :is="Icon" :size="18"/><strong>{{ value }}</strong><span>{{ label }}</span></article></div>
    <div class="day-groups">
      <template v-for="group in groups" :key="group.title">
        <section v-if="group.list.length" class="card day-group">
          <div class="section-head"><div><h2><component :is="group.icon" :size="18"/> {{ group.title }} <span class="count">{{ group.list.length }}</span></h2><p>{{ group.hint }}</p></div></div>
          <div class="day-list"><OrderCard v-for="o in group.list" :key="o.id" :item="o" show-client/></div>
        </section>
      </template>
    </div>
    <div v-if="loaded && !mine.length" class="empty">Активних заявок немає. Візьміть вільну заявку нижче.</div>
    <section v-if="free.length" class="card">
      <div class="section-head"><div><h2><Hand :size="18"/> Вільні заявки <span class="count">{{ free.length }}</span></h2><p>Ще без відповідального майстра.</p></div></div>
      <div class="day-list"><div v-for="o in free" :key="o.id" class="free-row"><OrderCard :item="o" show-client/><button class="button primary" :disabled="busy" @click="take(o)">Взяти</button></div></div>
    </section>
  </div>
</template>
