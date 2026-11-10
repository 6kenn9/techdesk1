<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from 'lucide-vue-next'
import { useSession } from '../state'
import { api } from '../api'
import ThemeToggle from '../components/ThemeToggle.vue'

const session = useSession()
const route = useRoute()
const router = useRouter()
const register = computed(() => route.path === '/register')
const form = reactive({ email: '', password: '', full_name: '', phone: '' })
const error = ref('')
const busy = ref(false)
const demo = ref(false)
const roles = [
  { label: 'Адміністратор', email: 'admin@techdesk.ua', password: 'admin123', role: 'admin' },
  { label: 'Інженер ПК', email: 'master1@techdesk.ua', password: 'master123', role: 'master' },
  { label: 'Інженер мобільних пристроїв', email: 'master2@techdesk.ua', password: 'master123', role: 'master' },
  { label: 'Клієнт', email: 'client1@techdesk.ua', password: 'client123', role: 'client' },
]
onMounted(async () => {
  try {
    demo.value = (await api('/auth/options')).demo_mode
  } catch {}
})
async function submit(account) {
  error.value = ''
  busy.value = true
  try {
    const data = account
      ? { email: account.email, password: account.password }
      : register.value
        ? { ...form }
        : { email: form.email, password: form.password }
    await session.authenticate(register.value ? 'register' : 'login', data)
    const next = route.query.next
    await router.push(typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : session.home)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="auth-shell">
    <header class="public-topbar">
      <div class="wrap public-nav">
        <RouterLink to="/" class="brand">
          <img src="/mark.svg" alt="" width="30" height="30" />
          TechDesk
        </RouterLink>
        <span class="actions">
          <ThemeToggle />
          <RouterLink to="/" class="button">
            <ArrowLeft :size="16" />
            На головну
          </RouterLink>
        </span>
      </div>
    </header>
    <main class="auth-main">
      <section class="card auth-card">
        <h1>{{ register ? 'Створення облікового запису' : 'Вхід до TechDesk' }}</h1>
        <form class="form-stack" @submit.prevent="submit()">
          <label v-if="register">
            Ім’я та прізвище
            <input v-model.trim="form.full_name" autocomplete="name" required maxlength="150" />
          </label>
          <label v-if="register">
            Телефон
            <input v-model.trim="form.phone" autocomplete="tel" type="tel" placeholder="+380…" required />
          </label>
          <label>
            Електронна пошта
            <input v-model.trim="form.email" autocomplete="email" type="email" required />
          </label>
          <label>
            Пароль
            <input
              v-model="form.password"
              :autocomplete="register ? 'new-password' : 'current-password'"
              type="password"
              :minlength="register ? 8 : 1"
              required
            />
          </label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="button primary wide" :disabled="busy">
            {{ register ? 'Зареєструватися' : 'Увійти' }}
            <ArrowRight :size="17" />
          </button>
        </form>
        <p class="auth-switch">
          <RouterLink :to="register ? '/login' : '/register'">
            {{ register ? 'Уже маєте обліковий запис? Увійти' : 'Створити обліковий запис' }}
          </RouterLink>
        </p>
      </section>
      <section v-if="demo && !register" class="demo-panel" aria-labelledby="demo-title">
        <div class="preview-bar">
          <h2 id="demo-title">Демонстраційні облікові записи</h2>
          <span class="count">4</span>
        </div>
        <ul class="demo-list">
          <li v-for="account in roles" :key="account.email">
            <div>
              <span class="chip" :class="'demo-' + account.role">{{ account.label }}</span>
              <span class="mono demo-email">{{ account.email }}</span>
            </div>
            <button class="button small" :disabled="busy" :aria-label="'Увійти: ' + account.label" @click="submit(account)">
              Увійти
              <ArrowRight :size="14" />
            </button>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>
