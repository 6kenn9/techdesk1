<script setup>
import { computed, onMounted, ref } from 'vue'
import { ClipboardList } from 'lucide-vue-next'
import { api } from '../api'
import { byClosed, byUrgency, daysSince, isLate, PICKUP_DAYS, STALE_DAYS, todoStep, todoSteps, workState } from '../domain'
import { useSession } from '../state'
import OrderCard from '../components/OrderCard.vue'

const session = useSession(), items = ref([]), error = ref(''), busy = ref(false), loaded = ref(false)
const FREE_SHOWN = 5
const mineAll = computed(() => items.value.filter(order => order.master_id === session.user.id))
const inState = state => mineAll.value.filter(order => workState(order) === state).sort(byUrgency)

const todoList = computed(() => inState('todo'))
const todo = computed(() => todoSteps.map(([key, title, hint]) => ({ key, title, hint, list: todoList.value.filter(order => todoStep(order) === key) })).filter(group => group.list.length))
const approval = computed(() => inState('client'))
const pickup = computed(() => inState('pickup').sort((a, b) => new Date(a.stage_since) - new Date(b.stage_since)))
const pickupLate = computed(() => pickup.value.filter(isLate))
const free = computed(() => items.value.filter(order => workState(order) === 'free').sort(byUrgency))
const freeShown = computed(() => free.value.slice(0, FREE_SHOWN))
const recent = computed(() => mineAll.value.filter(order => order.status === 'completed' && daysSince(order.completed_at) <= 7).sort(byClosed))

const urgent = computed(() => todoList.value.filter(order => order.priority === 'urgent').length)
const late = computed(() => todoList.value.filter(isLate).length)
const nothing = computed(() => !todoList.value.length && !approval.value.length && !pickup.value.length)
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
    <RouterLink class="button" to="/orders"><ClipboardList :size="16"/> Журнал заявок</RouterLink>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>

  <div v-if="loaded" class="stack">
    <p class="day-summary">
      Зробити <strong>{{ todoList.length }}</strong>
      <template v-if="urgent"> · термінових <strong>{{ urgent }}</strong></template>
      <template v-if="late"> · <span class="late">затримано {{ late }}</span></template>
      <template v-if="approval.length"> · чекають рішення клієнта <strong>{{ approval.length }}</strong></template>
      <template v-if="pickup.length"> · чекають видачі <strong>{{ pickup.length }}</strong></template>
      <template v-if="free.length"> · вільних <strong>{{ free.length }}</strong></template>
    </p>

    <!-- 1. Що робити зараз -->
    <template v-if="todo.length">
      <h2 class="day-heading">Зробити зараз</h2>
      <div class="day-groups">
        <section v-for="group in todo" :key="group.key" class="card day-group">
          <div class="section-head">
            <div><h2>{{ group.title }} <span class="count">{{ group.list.length }}</span></h2><p>{{ group.hint }}</p></div>
          </div>
          <div class="day-list"><OrderCard v-for="order in group.list" :key="order.id" :item="order" show-client/></div>
        </section>
      </div>
    </template>
    <div v-else class="empty">
      {{ nothing ? (free.length ? 'У черзі нічого немає. Візьміть заявку з вільних нижче.' : 'У черзі нічого немає, вільних заявок теж.') : 'Нічого робити не потрібно: усе чекає на клієнтів.' }}
    </div>

    <!-- 2. Вільні заявки: показуємо кілька найстарших, решта в журналі -->
    <template v-if="free.length">
      <h2 class="day-heading">Вільні заявки <span class="count">{{ free.length }}</span></h2>
      <section class="card">
        <div class="day-list">
          <div v-for="order in freeShown" :key="order.id" class="free-row">
            <OrderCard :item="order" show-client/>
            <button class="button" :disabled="busy" @click="take(order)">Взяти</button>
          </div>
        </div>
        <p v-if="free.length > FREE_SHOWN" class="day-more"><RouterLink to="/orders?tab=free">Усі вільні заявки ({{ free.length }})</RouterLink></p>
      </section>
    </template>

    <!-- 3. М’яч на боці клієнта: тут нічого робити, лише стежити за строками -->
    <template v-if="approval.length || pickup.length">
      <h2 class="day-heading">Чекаємо на клієнтів</h2>
      <div class="day-groups">
        <section v-if="pickup.length" class="card day-group">
          <div class="section-head">
            <div>
              <h2>Готові до видачі <span class="count">{{ pickup.length }}</span></h2>
              <p v-if="pickupLate.length" class="late-hint">{{ pickupLate.length }} не забирають {{ PICKUP_DAYS }} дні й довше: зателефонуйте клієнту.</p>
              <p v-else>Пристрій готовий, клієнт має забрати його й оплатити.</p>
            </div>
          </div>
          <div class="day-list"><OrderCard v-for="order in pickup" :key="order.id" :item="order" show-client/></div>
        </section>
        <section v-if="approval.length" class="card day-group">
          <div class="section-head">
            <div><h2>Кошторис на погодженні <span class="count">{{ approval.length }}</span></h2><p>Без згоди клієнта роботи не почнуться. Затримка від {{ STALE_DAYS }} днів підсвічується.</p></div>
          </div>
          <div class="day-list"><OrderCard v-for="order in approval" :key="order.id" :item="order" show-client/></div>
        </section>
      </div>
    </template>

    <p v-if="recent.length" class="day-recent">
      За останні 7 днів ви завершили <strong>{{ recent.length }}</strong>.
      <RouterLink to="/orders?tab=archive">Архів заявок</RouterLink>
    </p>
  </div>
</template>
