<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ArrowUpRight, Download, Plus, RefreshCw, Star } from 'lucide-vue-next'
import { api, download } from '../api'
import { ageLabel, date, money, stageNotes } from '../domain'
import { useSession } from '../state'
import DeviceCard from '../components/DeviceCard.vue'
import TelegramConnect from '../components/TelegramConnect.vue'
import Stage from '../components/Stage.vue'

const session = useSession(), devices = ref([]), orders = ref([]), error = ref(''), busy = ref(true)
const guest = reactive({ email: '', password: '' }), saving = ref(false)

const finished = order => ['completed', 'cancelled'].includes(order.status)
const needsDecision = order => order.status === 'waiting_approval' && order.client_approval_status === 'pending'
// Три групи заявок: потрібне рішення клієнта, ремонт триває, архів.
const waiting = computed(() => orders.value.filter(needsDecision))
const active = computed(() => orders.value.filter(order => !finished(order) && !needsDecision(order)))
const archive = computed(() => orders.value.filter(finished))

// Одне речення про те, що відбувається із заявкою зараз.
function note(order) {
  if (order.status === 'waiting_approval') return 'Кошторис відхилено. Майстер уточнить перелік робіт і зв’яжеться з вами.'
  if (order.status === 'ready_for_pickup') {
    const due = Number(order.total_cost) - Number(order.paid_amount)
    const pay = due > 0 ? `До сплати ${money(due)}. ` : 'Оплату отримано. '
    if (order.delivery_method !== 'nova_poshta') return pay + 'Заберіть пристрій, назвавши номер заявки.'
    return order.delivery_ttn ? `Відправлено Новою Поштою, накладна ${order.delivery_ttn}.` : pay + 'Готуємо відправку Новою Поштою.'
  }
  return stageNotes[order.status][1]
}

async function load() {
  busy.value = true
  try {
    [devices.value, orders.value] = await Promise.all([api('/passports'), api('/orders')])
    error.value = ''
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
let refresh
onMounted(() => {
  load()
  refresh = setInterval(() => { if (!document.hidden && !busy.value) load() }, 15000)
})
onUnmounted(() => clearInterval(refresh))

async function completeRegistration() {
  saving.value = true
  try {
    session.user = await api('/auth/complete-registration', { method: 'POST', data: guest })
    session.notify('Обліковий запис завершено: тепер можна входити за поштою.')
  } catch (e) { session.notify(e.message, 'error') } finally { saving.value = false }
}
async function pdf(order, kind) {
  try { await download('/orders/' + order.id + '/pdf/' + kind, order.order_number + (kind === 'receipt' ? '-квитанція.pdf' : '-гарантія.pdf')) }
  catch (e) { session.notify(e.message, 'error') }
}
</script>

<template>
  <div class="page-head">
    <div class="page-title"><h1>Особистий кабінет</h1></div>
    <div class="actions">
      <button class="button" :disabled="busy" @click="load"><RefreshCw :size="16"/> Оновити</button>
      <RouterLink class="button primary" to="/orders/new"><Plus :size="16"/> Заявка на ремонт</RouterLink>
    </div>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>

  <div class="stack">
    <!-- Гість за посиланням: спершу зберегти доступ -->
    <section v-if="session.user.is_guest" class="card guest-banner">
      <div>
        <h2>Збережіть доступ до кабінету</h2>
        <p class="muted">Зараз ви увійшли за особистим посиланням. Вкажіть пошту й пароль, щоб заходити будь-коли.</p>
      </div>
      <form class="form-grid" @submit.prevent="completeRegistration">
        <label>Електронна пошта<input v-model.trim="guest.email" type="email" autocomplete="email" required></label>
        <label>Пароль<input v-model="guest.password" type="password" minlength="8" autocomplete="new-password" required></label>
        <div class="actions full"><button class="button" :disabled="saving">Завершити реєстрацію</button></div>
      </form>
    </section>

    <!-- 1. Потрібна дія клієнта -->
    <section v-if="waiting.length">
      <div class="section-head"><h2>Потрібна ваша дія</h2></div>
      <div v-for="item in waiting" :key="item.id" class="alert warranty section-head">
        <div>
          <strong>Погодьте кошторис на {{ money(item.total_cost) }}</strong>
          <p><span class="mono">{{ item.order_number }}</span> · {{ item.device }}. Без вашої згоди роботи не почнуться.</p>
        </div>
        <RouterLink class="button primary" :to="'/orders/' + item.id + '#estimate'">Переглянути кошторис <ArrowUpRight :size="16"/></RouterLink>
      </div>
    </section>

    <!-- 2. Ремонти, що тривають -->
    <section>
      <div class="section-head"><h2>У ремонті <span class="count">{{ active.length }}</span></h2></div>
      <div v-if="active.length" class="order-list">
        <article v-for="item in active" :key="item.id" class="order-list-row repair-row">
          <div>
            <h3><RouterLink :to="'/orders/' + item.id" class="mono">{{ item.order_number }}</RouterLink> · {{ item.device }}</h3>
            <p>{{ note(item) }}</p>
            <small>Прийнято {{ date(item.created_at) }} · на цьому етапі {{ ageLabel(item.stage_since) }}<template v-if="item.master"> · майстер {{ item.master }}</template></small>
          </div>
          <div class="repair-side">
            <Stage :status="item.status"/>
            <RouterLink :to="'/orders/' + item.id" class="button small">Деталі <ArrowUpRight :size="15"/></RouterLink>
          </div>
        </article>
      </div>
      <div v-else-if="!busy && !waiting.length" class="empty">
        <p>{{ orders.length ? 'Зараз у ремонті нічого немає.' : 'Ви ще не подавали заявок на ремонт.' }}</p>
        <RouterLink class="button" to="/orders/new"><Plus :size="16"/> Подати заявку</RouterLink>
      </div>
    </section>

    <!-- 3. Пристрої -->
    <section>
      <div class="section-head">
        <h2>Мої пристрої <span class="count">{{ devices.length }}</span></h2>
        <RouterLink v-if="devices.length" to="/passports" class="button small">Усі паспорти</RouterLink>
      </div>
      <div v-if="devices.length" class="grid-3"><DeviceCard v-for="item in devices" :key="item.id" :item="item"/></div>
      <div v-else-if="!busy" class="empty">Паспорт пристрою з’явиться після першої заявки.</div>
    </section>

    <!-- 4. Архів: згорнутий, компактними рядками -->
    <details v-if="archive.length" class="card fold">
      <summary>Завершені заявки <span class="chip">{{ archive.length }}</span></summary>
      <div class="table-scroll">
        <table class="compact">
          <thead><tr><th>Заявка</th><th>Пристрій</th><th>Результат</th><th>Документи</th></tr></thead>
          <tbody>
            <tr v-for="item in archive" :key="item.id">
              <td><RouterLink :to="'/orders/' + item.id" class="mono">{{ item.order_number }}</RouterLink><small>{{ date(item.completed_at || item.created_at) }}</small></td>
              <td>{{ item.device }}</td>
              <td>
                <Stage :status="item.status"/>
                <RouterLink v-if="item.status === 'completed' && !item.rating" :to="'/orders/' + item.id" class="rate-link"><Star :size="14"/> Оцінити ремонт</RouterLink>
              </td>
              <td>
                <div class="actions">
                  <button class="button small" @click="pdf(item, 'receipt')"><Download :size="15"/> Квитанція</button>
                  <button v-if="item.status === 'completed'" class="button small" @click="pdf(item, 'warranty')"><Download :size="15"/> Гарантія</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <TelegramConnect/>
  </div>
</template>
