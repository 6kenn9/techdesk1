<script setup>
import { computed, onMounted, ref } from 'vue'
import { ClipboardList } from 'lucide-vue-next'
import { api } from '../api'
import { daysSince, STALE_DAYS } from '../domain'
import { useSession } from '../state'
import OrderCard from '../components/OrderCard.vue'

const session = useSession(), items = ref([]), error = ref(''), busy = ref(false), loaded = ref(false)
const isActive = order => !['completed', 'cancelled'].includes(order.status)
// Термінові вгорі, далі ті, що найдовше стоять на етапі.
const byUrgency = (a, b) => (b.priority === 'urgent') - (a.priority === 'urgent') || new Date(a.stage_since) - new Date(b.stage_since)
const mine = computed(() => items.value.filter(order => order.master_id === session.user.id && isActive(order)).sort(byUrgency))
const free = computed(() => items.value.filter(order => !order.master_id && order.status === 'registered').sort(byUrgency))
const awaitingClient = order => order.status === 'waiting_approval' && order.client_approval_status !== 'rejected'

// Колонки з тим, що майстер робить сам, у порядку етапів ремонту.
const todo = computed(() => [
  ['Почати діагностику', 'Пристрої чекають на огляд.', order => order.status === 'registered'],
  ['Скласти кошторис', 'Внесіть висновок, роботи й запчастини.', order => order.status === 'diagnostics' || (order.status === 'waiting_approval' && order.client_approval_status === 'rejected')],
  ['Ремонтувати', 'Кошторис погоджено, можна працювати.', order => order.status === 'in_repair'],
  ['Видати клієнту', 'Прийміть оплату й завершіть заявку.', order => order.status === 'ready_for_pickup'],
].map(([title, hint, test]) => ({ title, hint, list: mine.value.filter(test) })).filter(group => group.list.length))
const waiting = computed(() => mine.value.filter(awaitingClient))
const urgent = computed(() => mine.value.filter(order => order.priority === 'urgent').length)
const late = computed(() => mine.value.filter(order => daysSince(order.stage_since) >= STALE_DAYS).length)
const greeting = computed(() => { const hour = new Date().getHours(); return hour < 12 ? 'Доброго ранку' : hour < 18 ? 'Добрий день' : 'Добрий вечір' })

async function load() {
  try { items.value = await api('/orders'); error.value = '' }
  catch (e) { error.value = e.message } finally { loaded.value = true }
}
async function take(order) {
  busy.value = true
  try {
    await api('/orders/' + order.id, { method: 'PUT', data: { master_id: session.user.id } })
    session.notify(`Заявку ${order.order_number} закріплено за вами.`)
    await load()
  } catch (e) { session.notify(e.message, 'error') } finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-head">
    <div class="page-title"><h1>{{ greeting }}, {{ session.user.full_name.split(' ')[1] || session.user.full_name }}</h1></div>
    <RouterLink class="button" to="/orders"><ClipboardList :size="16"/> Увесь журнал</RouterLink>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>

  <div v-if="loaded" class="stack">
    <p class="day-summary">
      У роботі <strong>{{ mine.length }}</strong>
      <template v-if="urgent"> · термінових <strong>{{ urgent }}</strong></template>
      <template v-if="late"> · <span class="late">{{ late }} на етапі {{ STALE_DAYS }} дні й довше</span></template>
      <template v-if="free.length"> · вільних заявок <strong>{{ free.length }}</strong></template>
    </p>

    <!-- Що робити зараз -->
    <h2 v-if="todo.length" class="day-heading">Зробити зараз</h2>
    <div v-if="todo.length" class="day-groups">
      <section v-for="group in todo" :key="group.title" class="card day-group">
        <div class="section-head">
          <div><h2>{{ group.title }} <span class="count">{{ group.list.length }}</span></h2><p>{{ group.hint }}</p></div>
        </div>
        <div class="day-list"><OrderCard v-for="order in group.list" :key="order.id" :item="order" show-client/></div>
      </section>
    </div>
    <div v-else class="empty">{{ mine.length ? 'Усі ваші заявки чекають на рішення клієнтів.' : free.length ? 'Заявок у роботі немає. Візьміть вільну заявку нижче.' : 'Заявок у роботі немає, вільних теж.' }}</div>

    <!-- Заявки без майстра -->
    <template v-if="free.length">
      <h2 class="day-heading">Вільні заявки</h2>
      <section class="card">
        <div class="day-list">
          <div v-for="order in free" :key="order.id" class="free-row">
            <OrderCard :item="order" show-client/>
            <button class="button" :disabled="busy" @click="take(order)">Взяти</button>
          </div>
        </div>
      </section>
    </template>

    <!-- Від майстра нічого не потрібно -->
    <template v-if="waiting.length">
      <h2 class="day-heading">Чекають рішення клієнта</h2>
      <section class="card">
        <div class="day-groups"><OrderCard v-for="order in waiting" :key="order.id" :item="order" show-client/></div>
      </section>
    </template>
  </div>
</template>
