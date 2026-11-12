<script setup>
import { computed, reactive, ref } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import { api, setToken } from '../api'
import { roles } from '../domain'
import { useSession } from '../state'
import TelegramConnect from '../components/TelegramConnect.vue'
const session = useSession()
const form = reactive({ current_password: '', new_password: '', repeat: '' })
const busy = ref(false),
  error = ref('')
// Розбіжність показуємо одразу під полем повтору, а не після надсилання.
const mismatch = computed(() => form.repeat !== '' && form.new_password !== form.repeat)
async function change() {
  error.value = ''
  if (mismatch.value) return
  busy.value = true
  try {
    const result = await api('/auth/password', { method: 'POST', data: { current_password: form.current_password, new_password: form.new_password } })
    setToken(result.access_token)
    session.user = result.user
    Object.assign(form, { current_password: '', new_password: '', repeat: '' })
    session.notify('Пароль змінено. На інших пристроях потрібно буде увійти знову.')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page-head"><h1>Профіль</h1></div>
  <div class="profile-grid">
    <section class="card">
      <h2>Обліковий запис</h2>
      <dl class="facts">
        <div>
          <dt>Прізвище та ім’я</dt>
          <dd>{{ session.user.full_name }}</dd>
        </div>
        <div>
          <dt>Роль</dt>
          <dd>{{ roles[session.user.role] }}</dd>
        </div>
        <div>
          <dt>Електронна пошта</dt>
          <dd>{{ session.user.email || 'не вказано' }}</dd>
        </div>
        <div>
          <dt>Телефон</dt>
          <dd class="mono">{{ session.user.phone }}</dd>
        </div>
      </dl>
    </section>
    <section class="card">
      <h2>
        <KeyRound :size="17" />
        Зміна пароля
      </h2>
      <p v-if="session.user.must_change_password" class="alert warranty">
        Ви увійшли з тимчасовим паролем, який видав адміністратор. Задайте власний пароль.
      </p>
      <p v-if="session.user.is_guest" class="muted">
        Гостьовий кабінет ще не має пароля. Вкажіть пошту й пароль у
        <RouterLink to="/my-cabinet">особистому кабінеті</RouterLink>
        .
      </p>
      <form v-else class="form-stack" @submit.prevent="change">
        <label>
          Поточний пароль
          <input v-model="form.current_password" type="password" autocomplete="current-password" required />
        </label>
        <label>
          Новий пароль
          <input v-model="form.new_password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required />
        </label>
        <label>
          Повторіть новий пароль
          <input v-model="form.repeat" type="password" autocomplete="new-password" minlength="8" maxlength="128" required :aria-invalid="mismatch" />
          <span v-if="mismatch" class="field-error" role="alert">Паролі не збігаються.</span>
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div class="actions">
          <button class="button primary" :disabled="busy">{{ busy ? 'Зберігаємо…' : 'Змінити пароль' }}</button>
        </div>
        <p class="muted">Після зміни пароля сеанси на інших пристроях завершаться.</p>
      </form>
    </section>
  </div>
  <TelegramConnect />
</template>
