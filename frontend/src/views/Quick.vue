<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, CheckCircle2, Copy } from 'lucide-vue-next'
import { api } from '../api'
import { devicePayload, emptyQuick } from '../domain'
import { useSession } from '../state'
import QuickFields from '../components/QuickFields.vue'
import DeliveryFields from '../components/DeliveryFields.vue'
import ThemeToggle from '../components/ThemeToggle.vue'

const session = useSession(),
  router = useRouter()
const contact = reactive({ full_name: '', phone: '', website: '' })
const form = ref(emptyQuick())
const delivery = ref({ method: 'pickup', city: '', branch: '' })
const error = ref(''),
  busy = ref(false),
  done = ref(null)
const link = computed(() => (done.value?.claim_token ? `${location.origin}/claim/${done.value.claim_token}` : ''))
async function submit() {
  error.value = ''
  busy.value = true
  try {
    const result = await api('/quick-request', {
      method: 'POST',
      data: {
        ...contact,
        device: devicePayload(form.value),
        problem_description: form.value.problem_description,
        delivery: delivery.value,
      },
    })
    done.value = result
    if (result.claim_token) await session.authenticate('claim', { token: result.claim_token })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(link.value)
    session.notify('Посилання скопійовано.')
  } catch {
    session.notify('Скопіюйте посилання вручну.', 'error')
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
    <main class="auth-main" style="width: min(calc(100% - 32px), 560px)">
      <section v-if="!done" class="card auth-card">
        <h1>Швидка заявка на ремонт</h1>
        <p class="muted">Без реєстрації: залиште телефон і опишіть проблему. Кабінет для відстеження створимо автоматично.</p>
        <form class="form-stack" @submit.prevent="submit">
          <div class="form-grid">
            <label>
              Ім’я
              <input v-model.trim="contact.full_name" required minlength="2" maxlength="150" autocomplete="name" />
            </label>
            <label>
              Телефон
              <input v-model.trim="contact.phone" required type="tel" autocomplete="tel" inputmode="tel" placeholder="050 123 45 67" />
            </label>
          </div>
          <input v-model="contact.website" class="honeypot" tabindex="-1" autocomplete="off" aria-hidden="true" />
          <QuickFields v-model="form" show-serial />
          <DeliveryFields v-model="delivery" />
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="button primary wide" :disabled="busy">
            {{ busy ? 'Надсилаємо…' : 'Надіслати заявку' }}
            <ArrowRight :size="17" />
          </button>
        </form>
        <p class="auth-switch"><RouterLink to="/login">Уже маєте кабінет? Увійти</RouterLink></p>
      </section>
      <section v-else class="card auth-card success-card">
        <CheckCircle2 :size="44" style="color: var(--ok)" />
        <h1>Заявку прийнято</h1>
        <div class="big-number mono">{{ done.order_number }}</div>
        <template v-if="link">
          <p>
            Ми відкрили для вас кабінет, де видно статус ремонту. Збережіть це посилання — за ним можна повернутися з будь-якого пристрою ({{
              done.claim_days
            }}
            днів).
          </p>
          <div class="claim-link">
            <input :value="link" readonly aria-label="Посилання на кабінет" />
            <button class="button" type="button" @click="copy">
              <Copy :size="16" />
              Копіювати
            </button>
          </div>
          <button class="button primary wide" @click="router.push('/my-cabinet')">
            Відкрити кабінет
            <ArrowRight :size="17" />
          </button>
        </template>
        <template v-else>
          <p>Для цього номера телефону вже є кабінет. Увійдіть, щоб побачити нову заявку, або дочекайтеся дзвінка майстра.</p>
          <RouterLink to="/login" class="button primary wide">Увійти</RouterLink>
        </template>
        <p class="muted">Принесіть пристрій у сервісний центр або надішліть його Новою Поштою і назвіть номер заявки.</p>
      </section>
    </main>
  </div>
</template>
