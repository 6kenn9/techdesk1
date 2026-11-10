<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Columns3, FileSpreadsheet, List, Plus, Search } from 'lucide-vue-next'
import { api, download, query } from '../api'
import { ageLabel, categories, date, daysSince, money, STALE_DAYS, statuses } from '../domain'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
import OrderCard from '../components/OrderCard.vue'
const session = useSession()
const filters = reactive({ q: '', status: '', category: '', master_id: '', warranty_only: false, ...session.filters.orders })
const items = ref([]),
  masters = ref([]),
  error = ref(''),
  board = ref(false)
let request = 0
async function exportCsv() {
  try {
    await download('/orders/export.csv' + query(filters), `techdesk-заявки-${new Date().toISOString().slice(0, 10)}.csv`)
  } catch (e) {
    session.notify(e.message, 'error')
  }
}
// Швидкі фільтри рахуються з уже завантажених заявок, тож лічильники враховують пошук та інші фільтри.
const closed = ['completed', 'cancelled']
const quickFilters = [
  ['all', 'Усі', () => true],
  ['active', 'Активні', o => !closed.includes(o.status)],
  ['urgent', 'Терміново', o => o.priority === 'urgent' && !closed.includes(o.status)],
  ['unassigned', 'Без майстра', o => !o.master_id && !closed.includes(o.status)],
  ['waiting', 'Чекають клієнта', o => o.status === 'waiting_approval'],
  [
    'stale',
    `${STALE_DAYS}+ дні на етапі`,
    o => !closed.includes(o.status) && o.status !== 'ready_for_pickup' && daysSince(o.stage_since) >= STALE_DAYS,
  ],
  ['ready', 'До видачі', o => o.status === 'ready_for_pickup'],
]
const quick = ref(session.filters.ordersQuick || 'all')
watch(quick, value => {
  session.filters.ordersQuick = value
})
const counts = computed(() => Object.fromEntries(quickFilters.map(([key, , test]) => [key, items.value.filter(test).length])))
const shown = computed(() => items.value.filter(quickFilters.find(([key]) => key === quick.value)?.[2] || (() => true)))
const stale = o => !closed.includes(o.status) && daysSince(o.stage_since) >= STALE_DAYS
function resetFilters() {
  Object.assign(filters, { q: '', status: '', category: '', master_id: '', warranty_only: false })
  quick.value = 'all'
}
async function load() {
  const seq = ++request
  try {
    const result = await api('/orders' + query(filters))
    if (seq === request) {
      items.value = result
      error.value = ''
    }
  } catch (e) {
    if (seq === request) error.value = e.message
  }
}
watch(filters, () => {
  session.filters.orders = { ...filters }
  load()
})
onMounted(async () => {
  load()
  try {
    masters.value = await api('/users?role=master')
  } catch (e) {
    error.value = e.message
  }
})
</script>
<template>
  <div class="page-head">
    <div class="page-title">
      <h1>Журнал заявок</h1>
      <span class="count">{{ shown.length }}</span>
    </div>
    <div class="actions">
      <div class="segmented" aria-label="Вигляд журналу">
        <button class="button small" :aria-pressed="!board" @click="board = false">
          <List :size="16" />
          Таблиця
        </button>
        <button class="button small" :aria-pressed="board" @click="board = true">
          <Columns3 :size="16" />
          Дошка
        </button>
      </div>
      <button class="button" type="button" title="Завантажити журнал з поточними фільтрами для Excel" @click="exportCsv">
        <FileSpreadsheet :size="16" />
        Експорт
      </button>
      <RouterLink class="button primary" to="/orders/intake">
        <Plus :size="16" />
        Швидке приймання
      </RouterLink>
    </div>
  </div>
  <section>
    <div class="filters">
      <label class="input-icon">
        <Search :size="18" />
        <input v-model.trim="filters.q" aria-label="Пошук заявок" placeholder="Номер, пристрій або клієнт" />
      </label>
      <select v-model="filters.status" aria-label="Етап">
        <option value="">Усі етапи</option>
        <option v-for="(name, key) in statuses" :key="key" :value="key">{{ name }}</option>
      </select>
      <select v-model="filters.category" aria-label="Категорія пристрою">
        <option value="">Усі категорії</option>
        <option v-for="item in categories" :key="item">{{ item }}</option>
      </select>
      <select v-model="filters.master_id" aria-label="Майстер">
        <option value="">Усі майстри</option>
        <option v-for="item in masters" :key="item.id" :value="item.id">{{ item.full_name }}</option>
      </select>
      <label class="check">
        <input v-model="filters.warranty_only" type="checkbox" />
        Гарантійні
      </label>
      <button
        v-if="session.user.role === 'master'"
        class="button small"
        @click="filters.master_id = filters.master_id === session.user.id ? '' : session.user.id"
      >
        Мої заявки
      </button>
    </div>
    <div class="quick-filters" role="group" aria-label="Швидкі фільтри">
      <button
        v-for="[key, label] in quickFilters"
        :key="key"
        type="button"
        class="quick-chip"
        :class="[key, { selected: quick === key }]"
        :aria-pressed="quick === key"
        :disabled="key !== 'all' && !counts[key] && quick !== key"
        @click="quick = key"
      >
        {{ label }}
        <span>{{ counts[key] }}</span>
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-else-if="!shown.length" class="empty">
      <p>Заявок за вибраними фільтрами немає.</p>
      <button class="button" type="button" @click="resetFilters">Скинути фільтри</button>
    </div>
    <div v-else-if="board" class="kanban">
      <template v-for="(name, key) in statuses" :key="key">
        <section v-if="key !== 'cancelled' || filters.status === 'cancelled'" class="kanban-col">
          <h3>
            {{ name }}
            <span class="count">{{ shown.filter(o => o.status === key).length }}</span>
          </h3>
          <OrderCard v-for="item in shown.filter(o => o.status === key)" :key="item.id" :item="item" show-master />
        </section>
      </template>
    </div>
    <div v-else class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Заявка</th>
            <th>Пристрій</th>
            <th>Клієнт</th>
            <th>Етап</th>
            <th>На етапі</th>
            <th>Майстер</th>
            <th class="align-right">Сума</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in shown" :key="item.id">
            <td>
              <RouterLink class="mono nowrap" :to="'/orders/' + item.id">{{ item.order_number }}</RouterLink>
              <small>{{ date(item.created_at) }}</small>
            </td>
            <td>
              <strong>{{ item.device }}</strong>
              <small class="mono">{{ item.serial_number || 'S/N не вказано' }}</small>
            </td>
            <td>{{ item.client }}</td>
            <td>
              <Stage :status="item.status" />
              <small v-if="item.is_warranty_case">Гарантійний випадок</small>
            </td>
            <td class="nowrap" :class="{ 'stale-cell': stale(item) }">{{ closed.includes(item.status) ? '—' : ageLabel(item.stage_since) }}</td>
            <td>{{ item.master || 'Не призначено' }}</td>
            <td class="align-right mono nowrap">{{ money(item.total_cost) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
