<script setup>
import { computed, onMounted, ref } from 'vue'
import { Pencil, Plus } from 'lucide-vue-next'
import { api } from '../api'
import { categories, categorySpecs, roles, specLabels } from '../domain'
import { useSession } from '../state'
import Modal from '../components/Modal.vue'
const session = useSession(),
  tab = ref('team'),
  modal = ref(''),
  selected = ref(null),
  form = ref({}),
  busy = ref(false),
  error = ref('')
const users = ref([]),
  presets = ref([])
const team = computed(() => users.value.filter((u) => u.role !== 'client'))
const clients = computed(() => users.value.filter((u) => u.role === 'client'))
const staffRoles = { master: roles.master, admin: roles.admin }
const tabs = { team: 'Команда', clients: 'Клієнти', presets: 'Довідник моделей' }
const counts = computed(() => ({ team: team.value.length, clients: clients.value.length, presets: presets.value.length }))
const newLabel = computed(() => ({ team: 'Новий працівник', clients: 'Новий клієнт', presets: 'Нова модель' })[tab.value])
const fields = computed(() => [...new Set([...(categorySpecs[form.value.device_category] || []), ...Object.keys(form.value.default_specs || {})])])
async function load() {
  try {
    ;[users.value, presets.value] = await Promise.all([api('/users'), api('/passports/presets')])
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)
function open(kind, item = null) {
  modal.value = kind
  selected.value = item
  if (kind === 'user') {
    form.value = item
      ? { is_active: item.is_active, specialization: item.specialization }
      : { full_name: '', email: '', phone: '', password: '', role: tab.value === 'clients' ? 'client' : 'master', specialization: '' }
  } else {
    form.value = {
      device_category: item?.device_category || 'Ноутбук',
      brand: item?.brand || '',
      model_name: item?.model_name || '',
      default_specs: { ...item?.default_specs },
      typical_defects: item?.typical_defects || '',
    }
  }
}
const issued = ref(null)
async function resetPassword() {
  if (!confirm(`Скинути пароль для ${selected.value.full_name}? Усі його сеанси буде завершено.`)) return
  busy.value = true
  try {
    const r = await api(`/users/${selected.value.id}/reset-password`, { method: 'POST' })
    issued.value = { name: selected.value.full_name, email: selected.value.email, password: r.temporary_password }
    modal.value = 'password'
    await load()
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function reissueLink() {
  if (!confirm(`Видати нове посилання для ${selected.value.full_name}? Попереднє посилання перестане діяти.`)) return
  busy.value = true
  try {
    const r = await api(`/users/${selected.value.id}/claim-link`, { method: 'POST' })
    issued.value = { name: selected.value.full_name, phone: selected.value.phone, link: `${location.origin}/claim/${r.claim_token}`, days: r.claim_days }
    modal.value = 'password'
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function copyPassword() {
  try {
    await navigator.clipboard.writeText(issued.value.link || issued.value.password)
    session.notify(issued.value.link ? 'Посилання скопійовано.' : 'Пароль скопійовано.')
  } catch {
    session.notify('Скопіюйте пароль вручну.', 'error')
  }
}
async function save() {
  busy.value = true
  try {
    const id = selected.value?.id
    const path = (modal.value === 'user' ? '/users' : '/passports/presets') + (id ? '/' + id : '')
    const saved = await api(path, { method: id ? (modal.value === 'user' ? 'PATCH' : 'PUT') : 'POST', data: form.value })
    modal.value = ''
    const released = saved?.released_orders || []
    session.notify(released.length
      ? `Зміни збережено. Заявки майстра стали вільними й чекають на інших майстрів: ${released.join(', ')}.`
      : 'Зміни збережено.')
    await load()
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page-head">
    <div class="page-title">
      <h1>{{ tabs[tab] }}</h1>
      <span class="count">{{ counts[tab] }}</span>
    </div>
    <button class="button primary" @click="open(tab === 'presets' ? 'preset' : 'user')">
      <Plus :size="16" />
      {{ newLabel }}
    </button>
  </div>
  <div class="tabs">
    <button v-for="(name, key) in tabs" :key="key" class="tab" :class="{ active: tab === key }" @click="tab = key">
      {{ name }}
    </button>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <section class="card">
    <div class="table-scroll">
      <table v-if="tab !== 'presets'">
        <thead>
          <tr>
            <th>{{ tab === 'team' ? 'Працівник' : 'Клієнт' }}</th>
            <th v-if="tab === 'team'">Роль</th>
            <th>Контакти</th>
            <th>{{ tab === 'team' ? 'Активні заявки' : 'Заявки в роботі' }}</th>
            <th>Доступ</th>
            <th>Дія</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!(tab === 'team' ? team : clients).length">
            <td colspan="6" class="muted">{{ tab === 'team' ? 'Працівників ще немає.' : 'Клієнтів ще немає.' }}</td>
          </tr>
          <tr v-for="item in tab === 'team' ? team : clients" :key="item.id">
            <td>
              <strong>{{ item.full_name }}</strong>
              <small>{{ item.specialization }}</small>
            </td>
            <td v-if="tab === 'team'">{{ roles[item.role] }}</td>
            <td>
              {{ item.email || 'без пошти (гостьовий кабінет)' }}
              <small class="mono">{{ item.phone }}</small>
              <small v-if="item.telegram_linked" class="tg-linked">Telegram підключено</small>
            </td>
            <td>{{ item.role === 'admin' || (item.role === 'client' && !item.active_orders) ? '—' : item.active_orders }}</td>
            <td>
              <span class="status" :class="item.is_active ? 'completed' : 'cancelled'">{{ item.is_active ? 'Активний' : 'Вимкнено' }}</span>
            </td>
            <td>
              <button class="icon-button" aria-label="Редагувати користувача" @click="open('user', item)"><Pencil :size="16" /></button>
            </td>
          </tr>
        </tbody>
      </table>
      <table v-else>
        <thead>
          <tr>
            <th>Виробник і модель</th>
            <th>Категорія</th>
            <th>Характеристики</th>
            <th>Дія</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in presets" :key="item.id">
            <td>
              <strong>{{ item.brand }} {{ item.model_name }}</strong>
            </td>
            <td>{{ item.device_category }}</td>
            <td>
              <small>
                {{
                  Object.entries(item.default_specs)
                    .map(([key, value]) => (specLabels[key] || key) + ': ' + value)
                    .join(' · ')
                }}
              </small>
            </td>
            <td>
              <button class="icon-button" aria-label="Редагувати модель" @click="open('preset', item)"><Pencil :size="16" /></button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
  <Modal v-if="modal && modal !== 'password'" :title="modal === 'user' ? (form.role === 'client' || selected?.role === 'client' ? 'Обліковий запис клієнта' : 'Обліковий запис працівника') : 'Модель пристрою'" @close="modal = ''">
    <form class="form-grid" @submit.prevent="save">
      <template v-if="modal === 'user'">
        <template v-if="!selected">
          <label class="full">
            Прізвище та ім’я
            <input v-model.trim="form.full_name" maxlength="150" required />
          </label>
          <label>
            Електронна пошта
            <input v-model.trim="form.email" type="email" required />
          </label>
          <label>
            Телефон
            <input v-model.trim="form.phone" type="tel" required />
          </label>
          <label>
            Тимчасовий пароль
            <input v-model="form.password" type="password" minlength="8" required />
          </label>
          <label v-if="form.role !== 'client'">
            Роль
            <select v-model="form.role">
              <option v-for="(name, key) in staffRoles" :key="key" :value="key">{{ name }}</option>
            </select>
          </label>
        </template>
        <label v-else class="check full">
          <input v-model="form.is_active" type="checkbox" />
          Активний обліковий запис
        </label>
        <label v-if="selected ? selected.role !== 'client' : form.role !== 'client'" class="full">
          Спеціалізація
          <input v-model.trim="form.specialization" maxlength="180" />
        </label>
      </template>
      <template v-else>
        <label>
          Категорія
          <select v-model="form.device_category" @change="form.default_specs = {}">
            <option v-for="c in categories" :key="c">{{ c }}</option>
          </select>
        </label>
        <label>
          Виробник
          <input v-model.trim="form.brand" maxlength="80" required />
        </label>
        <label class="full">
          Модель
          <input v-model.trim="form.model_name" maxlength="120" required />
        </label>
        <label v-for="field in fields" :key="field">
          {{ specLabels[field] || field }}
          <input v-model.trim="form.default_specs[field]" maxlength="160" />
        </label>
        <label class="full">
          Типові несправності
          <textarea v-model.trim="form.typical_defects"></textarea>
        </label>
      </template>
      <button class="button primary full" :disabled="busy">Зберегти</button>
      <button
        v-if="modal === 'user' && selected && selected.email && selected.id !== session.user.id"
        type="button"
        class="button full"
        :disabled="busy"
        @click="resetPassword"
      >
        Скинути пароль
      </button>
      <button
        v-if="modal === 'user' && selected && !selected.email && selected.is_active"
        type="button"
        class="button full"
        :disabled="busy"
        @click="reissueLink"
      >
        Нове посилання входу
      </button>
    </form>
  </Modal>
  <Modal
    v-if="modal === 'password'"
    :title="issued.link ? 'Посилання до кабінету' : 'Тимчасовий пароль'"
    @close="
      modal = '';
      issued = null
    "
  >
    <div v-if="issued.link" class="form-stack">
      <p>
        Передайте клієнту
        <strong>{{ issued.name }}</strong>
        ({{ issued.phone }}) це посилання. Воно відкриває кабінет без пароля й діє {{ issued.days }} днів.
      </p>
      <div class="claim-link">
        <input :value="issued.link" readonly class="mono" aria-label="Посилання до кабінету" />
        <button class="button" type="button" @click="copyPassword">Копіювати</button>
      </div>
      <p class="muted">Посилання показується лише один раз. Попереднє посилання цього клієнта більше не діє.</p>
    </div>
    <div v-else class="form-stack">
      <p>
        Передайте користувачу
        <strong>{{ issued.name }}</strong>
        ({{ issued.email }}) цей пароль. Після входу система попросить задати власний.
      </p>
      <div class="claim-link">
        <input :value="issued.password" readonly class="mono" aria-label="Тимчасовий пароль" />
        <button class="button" type="button" @click="copyPassword">Копіювати</button>
      </div>
      <p class="muted">Пароль показується лише один раз. Попередні сеанси цього користувача завершено.</p>
    </div>
  </Modal>
</template>
