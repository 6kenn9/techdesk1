<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, Copy, Cpu, Pencil, QrCode, Wrench } from 'lucide-vue-next'
import { api, download, query } from '../api'
import { dateTime, icons, specLabels } from '../domain'
import { useSession } from '../state'
import Modal from '../components/Modal.vue'
import PassportFields from '../components/PassportFields.vue'
import Stage from '../components/Stage.vue'
import Warranty from '../components/Warranty.vue'
import PhotoGallery from '../components/PhotoGallery.vue'

const id = useRoute().params.id
const historyLabels = { owner: 'Власник', serial_number: 'Серійний номер', device_category: 'Категорія', brand: 'Виробник', model: 'Модель' }
const session = useSession()
const item = ref(null),
  error = ref(''),
  tab = ref('spec'),
  modal = ref(''),
  form = ref({}),
  qr = ref('')
const busy = ref(false),
  newSerial = ref('')
async function saveSerial() {
  busy.value = true
  try {
    const result = await api('/passports/' + id + '/serial', { method: 'PATCH', data: { serial_number: newSerial.value } })
    item.value.serial_number = result.serial_number
    session.notify('Серійний номер збережено.')
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    item.value = await api('/passports/' + id)
  } catch (e) {
    error.value = e.message
  }
})
onUnmounted(() => {
  if (qr.value) URL.revokeObjectURL(qr.value)
})
function edit() {
  const { serial_number, device_category, brand, model, specifications, cosmetic_condition } = item.value
  form.value = { serial_number, device_category, brand, model, specifications: { ...specifications }, cosmetic_condition }
  modal.value = 'edit'
}
function upgrade() {
  form.value = { field_name: Object.keys(item.value.specifications)[0] || 'ram', new_value: '', change_reason: '' }
  modal.value = 'upgrade'
}
function defect() {
  form.value = { description: '' }
  modal.value = 'defect'
}
async function save() {
  busy.value = true
  try {
    const path = { edit: '', upgrade: '/upgrade-spec', defect: '/defects' }[modal.value]
    item.value = await api('/passports/' + id + path, { method: modal.value === 'edit' ? 'PUT' : 'POST', data: form.value })
    modal.value = ''
    session.notify('Паспорт оновлено.')
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
const transferForm = ref({ phone: '', reason: '' }),
  buyer = ref(null)
function openTransfer() {
  transferForm.value = { phone: '', reason: '' }
  buyer.value = null
  modal.value = 'transfer'
}
async function findBuyer() {
  busy.value = true
  try {
    buyer.value = await api('/users/lookup' + query({ phone: transferForm.value.phone }))
    if (!buyer.value) session.notify('Клієнта з таким телефоном не знайдено. Спершу зареєструйте його.', 'error')
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function transfer() {
  busy.value = true
  try {
    item.value = await api('/passports/' + id + '/transfer', { method: 'POST', data: { owner_id: buyer.value.id, reason: transferForm.value.reason } })
    modal.value = ''
    session.notify('Пристрій передано новому власнику.')
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function showQr() {
  try {
    if (!qr.value) qr.value = URL.createObjectURL(await api('/passports/' + id + '/qr', { blob: true }))
    modal.value = 'qr'
  } catch (e) {
    session.notify(e.message, 'error')
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(item.value.serial_number || '')
    session.notify('Серійний номер скопійовано.')
  } catch {
    session.notify('Не вдалося скопіювати номер.', 'error')
  }
}
</script>
<template>
  <RouterLink class="back" to="/passports">
    <ArrowLeft :size="16" />
    Паспорти пристроїв
  </RouterLink>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="item">
    <div class="page-head">
      <div class="page-title">
        <h1>{{ item.brand }} {{ item.model }}</h1>
        <span class="chip">
          <component :is="icons[item.device_category] || Cpu" :size="16" />
          {{ item.device_category }}
        </span>
      </div>
      <div class="actions">
        <button class="button" @click="showQr">
          <QrCode :size="18" />
          Код паспорта
        </button>
        <button v-if="session.staff" class="button primary" @click="edit">
          <Pencil :size="16" />
          Редагувати
        </button>
      </div>
    </div>
    <div class="card stack">
      <div class="section-head">
        <div>
          <small>Серійний номер</small>
          <div class="actions">
            <strong class="mono">{{ item.serial_number || 'не вказано' }}</strong>
            <button v-if="item.serial_number" class="icon-button" aria-label="Скопіювати серійний номер" @click="copy"><Copy :size="15" /></button>
          </div>
          <small>Власник: {{ item.owner_name }}</small>
          <button v-if="session.admin" class="button small" style="margin-top: 6px" @click="openTransfer">Змінити власника</button>
          <form v-if="session.staff && !item.serial_number" class="actions" style="margin-top: 8px" @submit.prevent="saveSerial">
            <input v-model.trim="newSerial" required minlength="2" maxlength="80" placeholder="Внесіть серійний номер" aria-label="Серійний номер" />
            <button class="button small primary" :disabled="busy">Зберегти</button>
          </form>
        </div>
        <RouterLink
          v-if="session.staff"
          class="button"
          :to="{ path: '/orders/intake', query: item.serial_number ? { serial: item.serial_number } : {} }"
        >
          Нова заявка
          <ArrowUpRight :size="16" />
        </RouterLink>
      </div>
      <Warranty :warranty="item.warranty" />
      <div class="tabs">
        <button
          v-for="[value, label] in [
            ['spec', 'Характеристики'],
            ['history', 'Історія змін'],
            ['repairs', 'Ремонти й дефекти'],
            ['photos', 'Фото'],
          ]"
          :key="value"
          class="tab"
          :class="{ active: tab === value }"
          @click="tab = value"
        >
          {{ label }}
        </button>
      </div>
      <template v-if="tab === 'spec'">
        <dl v-if="Object.keys(item.specifications).length" class="specs">
          <div v-for="(value, key) in item.specifications" :key="key">
            <dt>{{ specLabels[key] || key }}</dt>
            <dd>{{ value || '—' }}</dd>
          </div>
        </dl>
        <p v-else>Характеристики ще не внесено.</p>
        <div>
          <h3>Зовнішній стан</h3>
          <p class="wrap-text">{{ item.cosmetic_condition || 'Відомості про стан відсутні.' }}</p>
        </div>
      </template>
      <template v-if="tab === 'history'">
        <div class="section-head">
          <h2>Історія конфігурації</h2>
          <button v-if="session.staff" class="button" @click="upgrade">
            <Wrench :size="16" />
            Оновити характеристику
          </button>
        </div>
        <ul v-if="item.spec_history.length" class="log">
          <li v-for="entry in item.spec_history" :key="entry.id">
            <strong>{{ historyLabels[entry.field_name] || specLabels[entry.field_name] || entry.field_name }}</strong>
            · {{ entry.old_value || '—' }} → {{ entry.new_value || '—' }}
            <small>{{ dateTime(entry.changed_at) }} · {{ entry.technician }} {{ entry.order_number || '' }}</small>
            <p>{{ entry.change_reason }}</p>
          </li>
        </ul>
        <div v-else class="empty">Змін конфігурації ще немає.</div>
      </template>
      <template v-if="tab === 'repairs'">
        <div class="section-head">
          <h2>Дефекти й ремонти</h2>
          <button v-if="session.staff" class="button" @click="defect">Зафіксувати дефект</button>
        </div>
        <ul v-if="item.known_defects_history.length" class="log">
          <li v-for="(defect, i) in item.known_defects_history" :key="i">{{ defect }}</li>
        </ul>
        <div v-if="item.orders.length" class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Заявка</th>
                <th>Несправність</th>
                <th>Етап</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in item.orders" :key="order.id">
                <td>
                  <RouterLink :to="'/orders/' + order.id" class="mono">{{ order.order_number }}</RouterLink>
                </td>
                <td>{{ order.problem_description }}</td>
                <td><Stage :status="order.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">Ремонтів ще немає.</div>
      </template>
      <PhotoGallery v-if="tab === 'photos'" :device-id="item.id" :can-upload="session.staff" :orders="item.orders" />
    </div>
    <Modal v-if="modal === 'transfer'" title="Зміна власника пристрою" @close="modal = ''">
      <form v-if="!buyer" class="form-stack" @submit.prevent="findBuyer">
        <p>Паспорт з усією історією перейде до нового власника. Попередні заявки лишаться за старим власником.</p>
        <label>
          Телефон нового власника
          <input v-model.trim="transferForm.phone" type="tel" required minlength="5" maxlength="24" placeholder="050 123 45 67" />
        </label>
        <button class="button primary" :disabled="busy">Знайти клієнта</button>
      </form>
      <form v-else class="form-stack" @submit.prevent="transfer">
        <p>Новий власник: <strong>{{ buyer.full_name }}</strong> · {{ buyer.phone }}</p>
        <label>
          Підстава (необов’язково)
          <input v-model.trim="transferForm.reason" maxlength="4000" placeholder="Наприклад: продаж пристрою" />
        </label>
        <div class="actions">
          <button class="button primary" :disabled="busy">Передати пристрій</button>
          <button type="button" class="button" @click="buyer = null">Інший телефон</button>
        </div>
      </form>
    </Modal>
    <Modal
      v-if="modal && modal !== 'transfer'"
      :title="{ edit: 'Редагування паспорта', upgrade: 'Оновлення конфігурації', defect: 'Запис про дефект', qr: 'Код цифрового паспорта' }[modal]"
      @close="modal = ''"
    >
      <img v-if="modal === 'qr'" :src="qr" class="qr-preview" alt="Код для відкриття паспорта" />
      <form v-else class="form-stack" @submit.prevent="save">
        <PassportFields v-if="modal === 'edit'" v-model="form" />
        <label v-else-if="modal === 'defect'">
          Опис виявленого дефекту
          <textarea v-model.trim="form.description" minlength="3" maxlength="4000" required></textarea>
        </label>
        <template v-else>
          <label>
            Характеристика
            <select v-model="form.field_name" required>
              <option v-for="(label, key) in specLabels" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
          <label>
            Нове значення
            <input v-model.trim="form.new_value" required maxlength="160" />
          </label>
          <label>
            Причина
            <textarea v-model.trim="form.change_reason"></textarea>
          </label>
        </template>
        <button class="button primary" :disabled="busy">Зберегти зміни</button>
      </form>
    </Modal>
  </template>
</template>
