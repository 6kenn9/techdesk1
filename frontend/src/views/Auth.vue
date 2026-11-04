<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Cpu, Laptop, ShieldCheck, Smartphone, UserRound } from 'lucide-vue-next'
import { useSession } from '../state'
import { api } from '../api'

const session = useSession()
const route = useRoute()
const router = useRouter()
const register = computed(() => route.path === '/register')
const form = reactive({ email: '', password: '', full_name: '', phone: '' })
const error = ref('')
const busy = ref(false)
const demo = ref(false)
const roles = [
  ['Адміністратор', 'Аналітика й керування', 'admin', 'admin123', ShieldCheck],
  ['Майстер ноутбуків і ПК', 'Діагностика та модернізація', 'master1', 'master123', Laptop],
  ['Майстер мобільної техніки', 'Ремонт смартфонів і планшетів', 'master2', 'master123', Smartphone],
  ['Клієнт', 'Замовлення й погодження', 'client1', 'client123', UserRound],
]
onMounted(async () => { try { demo.value = (await api('/auth/options')).demo_mode } catch {} })
async function submit(account) {
  error.value = ''; busy.value = true
  try {
    const data = account ? { email: account[2] + '@techdesk.ua', password: account[3] } : register.value ? { ...form } : { email: form.email, password: form.password }
    await session.authenticate(register.value ? 'register' : 'login', data)
    const next = route.query.next
    await router.push(typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : session.home)
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <main class="auth-shell">
    <section class="auth-aside">
      <RouterLink to="/" class="brand"><img src="/mark.svg" alt="" width="42" height="42"><div>TechDesk<small>СЕРВІСНИЙ ЦЕНТР</small></div></RouterLink>
      <div class="auth-aside-inner"><div class="tile-icon"><Cpu :size="28"/></div><p class="eyebrow">ОБЛІК СЕРВІСНОГО ЦЕНТРУ</p><h1>Єдиний простір для ремонту техніки</h1><p>Пристрої, заявки, склад і документи пов’язані в одній системі.</p></div>
      <RouterLink to="/" class="back"><ArrowLeft :size="16"/> На головну</RouterLink>
    </section>
    <section class="auth-main">
      <div class="auth-card"><div class="eyebrow">ОСОБИСТИЙ ДОСТУП</div><h2>{{ register ? 'Створення облікового запису' : 'Вхід до TechDesk' }}</h2>
        <p>{{ register ? 'Зареєструйтеся, щоб відстежувати стан ремонту.' : 'Введіть дані вашого облікового запису.' }}</p>
        <form class="form-stack" @submit.prevent="submit()">
          <label v-if="register">Ім’я та прізвище<input v-model.trim="form.full_name" autocomplete="name" required maxlength="150"></label>
          <label v-if="register">Телефон<input v-model.trim="form.phone" autocomplete="tel" type="tel" placeholder="+380…" required></label>
          <label>Електронна пошта<input v-model.trim="form.email" autocomplete="email" type="email" placeholder="name@example.com" required></label>
          <label>Пароль<input v-model="form.password" :autocomplete="register ? 'new-password' : 'current-password'" type="password" :minlength="register ? 8 : 1" required></label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="button primary wide" :disabled="busy">{{ register ? 'Зареєструватися' : 'Увійти' }} <ArrowRight :size="17"/></button>
        </form>
        <p class="auth-switch"><RouterLink :to="register ? '/login' : '/register'">{{ register ? 'Уже маєте обліковий запис? Увійти' : 'Створити обліковий запис' }}</RouterLink></p>
        <template v-if="demo && !register"><div class="divider-label">ДЕМОНСТРАЦІЙНИЙ ДОСТУП</div>
          <div class="demo-grid"><button v-for="account in roles" :key="account[2]" class="demo-card" :disabled="busy" @click="submit(account)">
            <component :is="account[4]" :size="20"/><span><strong>{{ account[0] }}</strong><small>{{ account[1] }}</small></span>
          </button></div>
        </template>
      </div>
    </section>
  </main>
</template>
