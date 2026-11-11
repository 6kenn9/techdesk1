<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Copy, FileText, Plus, Printer, ScanLine, UserPlus } from 'lucide-vue-next'
import { api, download, query } from '../api'
import { categorySpecs, devicePayload, emptyQuick, icons, problemHints, specLabels } from '../domain'
import { useSession } from '../state'
import QuickFields from '../components/QuickFields.vue'
import DeliveryFields from '../components/DeliveryFields.vue'
import Warranty from '../components/Warranty.vue'

const session = useSession(), route = useRoute(), router = useRouter()
const contact = reactive({ phone: '', full_name: '' })
const client = ref(null), searched = ref(false), pick = ref(null), passport = ref(null)
const form = ref(emptyQuick()), extra = reactive({ completeness: '', cosmetic_notes: '', priority: 'normal', master_id: null, is_warranty_case: false, delivery: { method: 'pickup', city: '', branch: '' } })
const masters = ref([]), error = ref(''), busy = ref(false), done = ref(null)
const device = computed(() => client.value?.devices.find(item => item.id === pick.value) || null)
const claimLink = computed(() => done.value?.claim_token ? `${location.origin}/claim/${done.value.claim_token}` : '')
let timer, sequence = 0
// Приймання починається із серійного номера: за ним знаходимо паспорт, власника й гарантію.
const serial = ref(''), serialState = ref(''), moreOpen = ref(false)
let serialTimer, serialSeq = 0
async function findBySerial(value) {
  const seq = ++serialSeq
  try {
    const found = await api('/passports/lookup-sn/' + encodeURIComponent(value))
    if (seq !== serialSeq) return
    if (found) {
      client.value = { full_name: found.owner_name, phone: '', is_guest: false, devices: [found], bySerial: true }
      pick.value = found.id; searched.value = true; serialState.value = 'found'
    } else {
      if (client.value?.bySerial) { client.value = null; pick.value = null }
      form.value.serial_number = value; serialState.value = 'new'
    }
  } catch (e) { error.value = e.message }
}
watch(serial, value => {
  clearTimeout(serialTimer); serialState.value = ''
  if (client.value?.bySerial) { client.value = null; pick.value = null }
  form.value.serial_number = value
  if (value.length >= 3) serialTimer = setTimeout(() => findBySerial(value), 400)
})
// Характеристики нового пристрою: підказка з довідника або з такого ж пристрою в базі, майстер може виправити.
const specs = ref({}), specSource = ref(null), specsTouched = ref(false), savePreset = ref(false)
const specFields = computed(() => categorySpecs[form.value.device_category] || [])
const modelKey = computed(() => { const d = devicePayload(form.value); return d.brand && d.model ? [form.value.device_category, d.brand, d.model].join('|') : '' })
let specTimer, specSeq = 0
watch(modelKey, key => {
  clearTimeout(specTimer)
  if (!key) { specSource.value = null; if (!specsTouched.value) specs.value = {}; return }
  specTimer = setTimeout(async () => {
    const seq = ++specSeq, [category, brand, model] = key.split('|')
    try {
      const found = await api('/passports/spec-suggestion' + query({ category, brand, model }))
      if (seq !== specSeq) return
      specSource.value = found.source
      if (!specsTouched.value) specs.value = { ...found.specifications }
      else for (const [k, v] of Object.entries(found.specifications)) if (!specs.value[k]) specs.value[k] = v
      savePreset.value = false
    } catch { specSource.value = null }
  }, 400)
})

onMounted(async () => {
  try {
    const workers = await api('/users?role=master')
    masters.value = workers.filter(item => item.is_active && (session.admin || item.id === session.user.id))
    if (!session.admin) extra.master_id = session.user.id
    // Перехід зі сканера: серійний номер уже відомий.
    if (typeof route.query.serial === 'string' && route.query.serial) serial.value = route.query.serial
  } catch (e) { error.value = e.message }
})
watch(() => contact.phone, value => {
  clearTimeout(timer); client.value = null; pick.value = null; searched.value = false
  if (value.replace(/\D/g, '').length < 9) return
  timer = setTimeout(async () => {
    const seq = ++sequence
    try {
      const found = await api('/users/lookup' + query({ phone: value }))
      if (seq !== sequence) return
      client.value = found; searched.value = true
      if (found) { contact.full_name = found.full_name; if (found.devices.length === 1) pick.value = found.devices[0].id }
    } catch (e) { error.value = e.message }
  }, 350)
})
watch(pick, async id => {
  passport.value = null; extra.is_warranty_case = false
  if (id) try { passport.value = await api('/passports/' + id) } catch {}
})
async function submit() {
  error.value = ''; busy.value = true
  try {
    const data = { ...extra, problem_description: form.value.problem_description }
    if (device.value) data.device_id = device.value.id
    else {
      const filled = Object.fromEntries(Object.entries(specs.value).map(([k, v]) => [k, String(v || '').trim()]).filter(([, v]) => v))
      Object.assign(data, { phone: contact.phone, full_name: contact.full_name, device: { ...devicePayload(form.value), specifications: filled },
                            save_preset: savePreset.value && specSource.value !== 'preset' && Object.keys(filled).length > 0 })
    }
    done.value = await api('/orders/intake', { method: 'POST', data })
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
function hint(text) { const c = form.value.problem_description.trim(); if (!c.toLowerCase().includes(text.toLowerCase())) form.value.problem_description = c ? `${c}. ${text}` : text }
async function file(path, name) { try { await download(path, name) } catch (e) { session.notify(e.message, 'error') } }
async function copy() { try { await navigator.clipboard.writeText(claimLink.value); session.notify('Посилання скопійовано.') } catch { session.notify('Скопіюйте посилання вручну.', 'error') } }
function again() { serial.value = ''; moreOpen.value = false; done.value = null; client.value = null; pick.value = null; searched.value = false; Object.assign(contact, { phone: '', full_name: '' }); form.value = emptyQuick(); specs.value = {}; specSource.value = null; specsTouched.value = false; savePreset.value = false; Object.assign(extra, { completeness: '', cosmetic_notes: '', priority: 'normal', is_warranty_case: false, delivery: { method: 'pickup', city: '', branch: '' } }) }
</script>
<template>
  <RouterLink to="/orders" class="back"><ArrowLeft :size="16"/> Журнал заявок</RouterLink>
  <div class="page-head"><h1>Швидке приймання</h1></div>

  <!-- Після збереження: документи й наступна заявка -->
  <section v-if="done" class="card form-card success-card">
    <h2>Заявку {{ done.order_number }} створено</h2>
    <p class="muted">{{ done.client }} · {{ done.device }}</p>
    <p v-if="!done.serial_number" class="alert warranty">Серійний номер не внесено. Додайте його в паспорті до початку діагностики.</p>
    <template v-if="claimLink">
      <p>Для клієнта створено кабінет без пароля. Передайте посилання або продиктуйте його:</p>
      <div class="claim-link">
        <input :value="claimLink" readonly aria-label="Посилання для клієнта">
        <button class="button" @click="copy"><Copy :size="16"/> Копіювати</button>
      </div>
    </template>
    <div class="actions">
      <button class="button" @click="file('/orders/' + done.id + '/pdf/receipt', done.order_number + '-квитанція.pdf')"><FileText :size="16"/> Квитанція</button>
      <button class="button" @click="file('/passports/' + done.device_id + '/label', done.order_number + '-наліпка.pdf')"><Printer :size="16"/> Наліпка</button>
      <RouterLink class="button" :to="'/orders/' + done.id">Відкрити заявку</RouterLink>
      <button class="button primary" @click="again"><Plus :size="16"/> Наступна заявка</button>
    </div>
  </section>

  <section v-else class="card form-card">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <form class="form-stack" @submit.prevent="submit">

      <!-- 1. Серійний номер: якщо пристрій уже був у сервісі, паспорт і гарантія підставляться самі -->
      <label>Серійний номер
        <span class="input-icon"><ScanLine :size="18"/><input v-model.trim="serial" maxlength="80" placeholder="З наліпки на корпусі або з налаштувань" autofocus></span>
        <small v-if="serialState === 'found'">Пристрій є в базі: {{ device?.brand }} {{ device?.model }}, власник {{ client?.full_name }}.</small>
        <small v-else-if="serialState === 'new'">Пристрою з таким номером ще немає. Його буде зареєстровано разом із заявкою.</small>
        <small v-else>Якщо номера не видно, залиште поле порожнім і внесіть його пізніше в паспорті.</small>
      </label>
      <Warranty :warranty="passport?.warranty"/>
      <label v-if="passport?.warranty" class="check"><input v-model="extra.is_warranty_case" type="checkbox"> Це гарантійний випадок (безкоштовно для клієнта)</label>

      <!-- 2. Клієнт -->
      <div v-if="!client?.bySerial" class="form-grid">
        <label>Телефон клієнта<input v-model.trim="contact.phone" type="tel" inputmode="tel" placeholder="050 123 45 67" :required="!device"></label>
        <label>Прізвище та ім’я клієнта<input v-model.trim="contact.full_name" :disabled="!!client" :required="!client" maxlength="150" :placeholder="client ? '' : 'Для нового клієнта'"></label>
      </div>
      <p v-if="client && !client.bySerial" class="alert"><UserPlus :size="18"/> Клієнт знайдений: <strong>{{ client.full_name }}</strong><span v-if="client.is_guest"> · кабінет без пошти</span></p>

      <div v-if="client?.devices.length && !client.bySerial">
        <strong>Пристрій клієнта</strong>
        <div class="device-picks" style="margin-top:8px">
          <button v-for="item in client.devices" :key="item.id" type="button" class="device-pick" :class="{ active: pick === item.id }" @click="pick = item.id">
            <component :is="icons[item.device_category]" :size="22"/>
            <span><strong>{{ item.brand }} {{ item.model }}</strong><small>{{ item.serial_number || 'без серійного номера' }}</small></span>
          </button>
          <button type="button" class="device-pick" :class="{ active: pick === null }" @click="pick = null">
            <Plus :size="22"/><span><strong>Інший пристрій</strong><small>Новий у реєстрі</small></span>
          </button>
        </div>
      </div>

      <!-- 3. Несправність; для нового пристрою ще категорія й модель -->
      <template v-if="device">
        <label>Що сталося?<textarea v-model.trim="form.problem_description" required minlength="3" maxlength="4000" rows="3"></textarea></label>
        <div class="hint-chips"><button v-for="text in problemHints" :key="text" type="button" class="chip-button" @click="hint(text)">{{ text }}</button></div>
      </template>
      <QuickFields v-else v-model="form"/>

      <fieldset v-if="!device && modelKey" class="spec-panel">
        <legend>Характеристики</legend>
        <p class="spec-source" :class="specSource || 'none'">
          <template v-if="specSource === 'preset'">Заповнено з довідника моделей. Змініть, якщо конфігурація клієнта інша.</template>
          <template v-else-if="specSource === 'device'">Узято з такого ж пристрою, що вже був у сервісі. Перевірте, бо конфігурація може відрізнятися.</template>
          <template v-else>Цієї моделі ще немає в базі. Заповніть, що відомо, або додайте пізніше в паспорті.</template>
        </p>
        <div class="form-grid">
          <label v-for="key in specFields" :key="key">{{ specLabels[key] }}<input v-model.trim="specs[key]" maxlength="160" @input="specsTouched = true"></label>
        </div>
        <label v-if="specSource !== 'preset'" class="check"><input v-model="savePreset" type="checkbox"> Зберегти модель із цими характеристиками в довідник</label>
      </fieldset>

      <!-- 4. Що передав клієнт і в якому стані -->
      <div class="form-grid">
        <label>Комплектація<input v-model.trim="extra.completeness" placeholder="Зарядка, сумка"></label>
        <label>Зовнішній стан<input v-model.trim="extra.cosmetic_notes" placeholder="Подряпини, потертості"></label>
      </div>

      <!-- 5. Те, що зазвичай не змінюють -->
      <details class="fold more-fields" :open="moreOpen || extra.delivery.method === 'nova_poshta'" @toggle="moreOpen = $event.target.open">
        <summary>Додатково: пріоритет, майстер, спосіб отримання</summary>
        <div class="form-grid">
          <label>Пріоритет
            <select v-model="extra.priority"><option value="normal">Звичайний</option><option value="urgent">Терміновий</option></select>
          </label>
          <label>Майстер
            <select v-model="extra.master_id">
              <option :value="null">Не призначати</option>
              <option v-for="worker in masters" :key="worker.id" :value="worker.id">{{ worker.full_name }}{{ worker.active_orders != null ? ' · активних: ' + worker.active_orders : '' }}</option>
            </select>
          </label>
          <DeliveryFields v-model="extra.delivery" class="full"/>
        </div>
      </details>

      <div class="actions"><button class="button primary large" :disabled="busy">{{ busy ? 'Зберігаємо…' : 'Прийняти пристрій' }}</button></div>
    </form>
  </section>
</template>
