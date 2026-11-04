<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Activity, ArrowRight, ArrowUpRight, ClipboardCheck, Cpu, Fingerprint, ScanLine, Search, ShieldCheck, Wrench } from 'lucide-vue-next'
import { api, query } from '../api'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
import Timeline from '../components/Timeline.vue'

const session = useSession()
const route = useRoute()
const code = ref(route.params.code || '')
const result = ref(null)
const error = ref('')
const loading = ref(false)
async function lookup() {
  loading.value = true; error.value = ''; result.value = null
  try { result.value = await api('/track' + query({ code: code.value })) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
onMounted(() => { if (code.value) lookup() })
</script>

<template>
  <div class="landing">
    <header class="landing-nav wrap">
      <RouterLink class="brand" to="/"><img src="/mark.svg" alt="" width="39" height="39"><div>TechDesk<small>СЕРВІСНИЙ ЦЕНТР</small></div></RouterLink>
      <nav aria-label="Навігація"><a href="#tracking">Перевірити статус</a><RouterLink :to="session.user ? session.home : '/login'" class="button primary">{{ session.user ? 'Робочий простір' : 'Увійти' }} <ArrowUpRight :size="17"/></RouterLink></nav>
    </header>
    <main>
      <div class="hero wrap">
        <div>
          <div class="eyebrow"><Activity :size="15"/> СЕРВІС ІЗ ПРОЗОРОЮ ІСТОРІЄЮ</div>
          <h1>Ремонт техніки <em>під контролем</em></h1>
          <p>Від першої діагностики до видачі. Перевіряйте стан замовлення, погоджуйте вартість і зберігайте історію пристрою в одному кабінеті.</p>
          <div class="actions"><a href="#tracking" class="button primary">Відстежити ремонт <ArrowRight :size="18"/></a><RouterLink class="button" :to="session.user ? session.home : '/register'">{{ session.user ? 'До робочого простору' : 'Створити кабінет' }}</RouterLink></div>
        </div>
        <div class="blueprint" aria-hidden="true">
          <span class="blueprint-label"><Cpu :size="16"/> ПАСПОРТ ПРИСТРОЮ</span>
          <div class="chip-visual"><div class="chip-core"><Cpu :size="74" :stroke-width="1.1"/></div><span class="chip-line one"></span><span class="chip-line two"></span><span class="chip-line three"></span></div>
          <div class="blueprint-footer"><span><i></i> Історія обслуговування</span><span class="mono">СЕРІЙНИЙ НОМЕР</span></div>
        </div>
      </div>
      <section id="tracking" class="track-section wrap">
        <div class="card tracker">
          <div class="section-head"><div class="track-title"><span class="tile-icon"><ScanLine :size="23"/></span><div><h2>Де зараз ваш пристрій?</h2><p>Введіть номер заявки з квитанції або серійний номер техніки.</p></div></div></div>
          <form class="search-form" @submit.prevent="lookup"><label class="input-icon"><Search :size="20"/><input v-model.trim="code" aria-label="Номер заявки або серійний номер" placeholder="Наприклад, TD-2026-0001" required maxlength="80"></label><button class="button primary" :disabled="loading">{{ loading ? 'Перевіряємо…' : 'Знайти заявку' }}</button></form>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div v-if="result" class="tracking-result"><div class="section-head"><h3>Поточний етап</h3><Stage :status="result.status"/></div><Timeline :status="result.status"/></div>
        </div>
      </section>
      <section class="features wrap" aria-label="Можливості">
        <article><Fingerprint :size="25"/><h3>Цифровий паспорт</h3><p>Характеристики, дефекти та всі зміни конфігурації за серійним номером.</p></article>
        <article><ClipboardCheck :size="25"/><h3>Погодження кошторису</h3><p>Перелік робіт і запчастин доступний до початку ремонту.</p></article>
        <article><ShieldCheck :size="25"/><h3>Документи й гарантія</h3><p>Квитанція та гарантійний талон доступні в особистому кабінеті.</p></article>
      </section>
    </main>
    <footer class="wrap landing-footer"><span>TechDesk · Сервісний центр</span><span><Wrench :size="15"/> Облік і ремонт техніки</span></footer>
  </div>
</template>
