<script setup>
import { computed, onMounted, ref } from 'vue'
import { Pencil, Plus } from 'lucide-vue-next'
import { api } from '../api'
import { categories, categorySpecs, roles, specLabels } from '../domain'
import { useSession } from '../state'
import Modal from '../components/Modal.vue'
const session = useSession(),
  tab = ref('users'),
  modal = ref(''),
  selected = ref(null),
  form = ref({}),
  busy = ref(false),
  error = ref('')
const users = ref([]),
  presets = ref([])
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
      : { full_name: '', email: '', phone: '', password: '', role: 'master', specialization: '' }
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
async function copyPassword() {
  try {
    await navigator.clipboard.writeText(issued.value.password)
    session.notify('Пароль скопійовано.')
  } catch {
    session.notify('Скопіюйте пароль вручну.', 'error')
  }
}
async function save() {
  busy.value = true
  try {
    const id = selected.value?.id
    const path = (modal.value === 'user' ? '/users' : '/passports/presets') + (id ? '/' + id : '')
    await api(path, { method: id ? (modal.value === 'user' ? 'PATCH' : 'PUT') : 'POST', data: form.value })
    modal.value = ''
    session.notify('Зміни збережено.')
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
      <h1>Команда та довідники</h1>
      <span class="count">{{ tab === 'users' ? users.length : presets.length }}</span>
    </div>
    <button class="button primary" @click="open(tab === 'users' ? 'user' : 'preset')">
      <Plus :size="16" />
      {{ tab === 'users' ? 'Новий користувач' : 'Нова модель' }}
    </button>
  </div>
  <div class="tabs">
    <button class="tab" :class="{ active: tab === 'users' }" @click="tab = 'users'">Користувачі</button>
    <button class="tab" :class="{ active: tab === 'presets' }" @click="tab = 'presets'">Довідник моделей</button>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <section class="card">
    <div class="table-scroll">
      <table v-if="tab === 'users'">
        <thead>
          <tr>
            <th>Користувач</th>
            <th>Роль</th>
            <th>Контакти</th>
            <th>Активні заявки</th>
            <th>Доступ</th>
            <th>Дія</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in users" :key="item.id">
            <td>
              <strong>{{ item.full_name }}</strong>
              <small>{{ item.specialization }}</small>
            </td>
            <td>{{ roles[item.role] }}</td>
            <td>
              {{ item.email || 'без пошти (гостьовий кабінет)' }}
              <small class="mono">{{ item.phone }}</small>
              <small v-if="item.telegram_linked" class="tg-linked">Telegram підключено</small>
            </td>
            <td>{{ item.role === 'master' ? item.active_orders : '—' }}</td>
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
  <Modal v-if="modal && modal !== 'password'" :title="modal === 'user' ? 'Обліковий запис' : 'Модель пристрою'" @close="modal = ''">
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
          <label>
            Роль
            <select v-model="form.role">
              <option v-for="(name, key) in roles" :key="key" :value="key">{{ name }}</option>
            </select>
          </label>
        </template>
        <label v-else class="check full">
          <input v-model="form.is_active" type="checkbox" />
          Активний обліковий запис
        </label>
        <label class="full">
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
    </form>
  </Modal>
  <Modal
    v-if="modal === 'password'"
    title="Тимчасовий пароль"
    @close="
      modal = '';
      issued = null
    "
  >
    <div class="form-stack">
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
