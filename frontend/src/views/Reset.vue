<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from 'lucide-vue-next'
import { useSession } from '../state'
import { api } from '../api'

const session = useSession(), route = useRoute(), router = useRouter()
const token = computed(() => typeof route.query.token === 'string' ? route.query.token : '')
const form = reactive({ email: '', password: '', repeat: '' })
const error = ref(''), done = ref(''), busy = ref(false)

async function requestMail() {
  error.value = ''; busy.value = true
  try { done.value = (await api('/auth/forgot', { method: 'POST', data: { email: form.email } })).message }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}

async function setPassword() {
  error.value = ''
  if (form.password !== form.repeat) { error.value = 'Паролі не збігаються.'; return }
  busy.value = true
  try {
    session.clear()
    await session.authenticate('reset', { token: token.value, new_password: form.password })
    session.notify('Пароль змінено. На інших пристроях потрібно буде увійти знову.')
    await router.replace(session.home)
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>

<template>
  <div class="auth-shell"><main class="auth-main"><section class="card auth-card">
    <template v-if="token">
      <h1>Новий пароль</h1>
      <form class="form-stack" @submit.prevent="setPassword">
        <label>Новий пароль<input v-model="form.password" type="password" autocomplete="new-password" minlength="8" required></label>
        <label>Повторіть пароль<input v-model="form.repeat" type="password" autocomplete="new-password" minlength="8" required></label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="button primary wide" :disabled="busy">Зберегти й увійти <ArrowRight :size="17"/></button>
      </form>
    </template>
    <template v-else>
      <h1>Відновлення пароля</h1>
      <p v-if="done" class="muted" role="status">{{ done }} Посилання діє 30 хвилин. Якщо листа немає, перевірте теку «Спам».</p>
      <form v-else class="form-stack" @submit.prevent="requestMail">
        <p class="muted">Вкажіть пошту, з якою входите. Ми надішлемо посилання, за яким можна задати новий пароль. Так само можна задати пароль кабінету, створеному через Google.</p>
        <label>Електронна пошта<input v-model.trim="form.email" type="email" autocomplete="email" required></label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="button primary wide" :disabled="busy">Надіслати лист <ArrowRight :size="17"/></button>
      </form>
    </template>
    <p class="auth-switch"><RouterLink to="/login"><ArrowLeft :size="15"/> Повернутися до входу</RouterLink></p>
  </section></main></div>
</template>
