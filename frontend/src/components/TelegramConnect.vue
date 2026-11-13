<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { BellRing, Send } from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../state'
defineProps({ compact: Boolean })
const session = useSession(),
  available = ref(false),
  busy = ref(false),
  waiting = ref(false)
let timer
onMounted(async () => {
  try {
    available.value = (await api('/auth/options')).telegram
  } catch {
    available.value = false
  }
})
onUnmounted(() => clearInterval(timer))
async function connect() {
  busy.value = true
  const tab = window.open('', '_blank')
  try {
    const { url } = await api('/auth/telegram-link', { method: 'POST' })
    if (tab) tab.location.href = url
    else window.location.href = url
    waiting.value = true
    let attempts = 0
    clearInterval(timer)
    timer = setInterval(async () => {
      attempts += 1
      try {
        session.user = await api('/auth/me')
      } catch {
        /* повторимо */
      }
      if (session.user?.telegram_linked || attempts > 60) {
        clearInterval(timer)
        waiting.value = false
        if (session.user?.telegram_linked) session.notify('Telegram підключено. Сповіщення надходитимуть у чат з ботом.')
      }
    }, 3000)
  } catch (e) {
    tab?.close()
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
// Пауза лише зупиняє повідомлення; чат лишається прив'язаним, тож увімкнути можна одним натиском.
async function setNotifications(enabled) {
  busy.value = true
  try {
    session.user = await api('/auth/telegram-notifications', { method: 'PUT', data: { enabled } })
    session.notify(enabled ? 'Сповіщення в Telegram увімкнено.' : 'Сповіщення в Telegram призупинено.')
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function disconnect() {
  busy.value = true
  try {
    session.user = await api('/auth/telegram-link', { method: 'DELETE' })
    session.notify('Telegram відключено від облікового запису.')
  } catch (e) {
    session.notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <template v-if="available">
    <div v-if="compact" class="telegram-compact">
      <BellRing :size="15" />
      <span v-if="session.user.telegram_linked">{{ session.user.telegram_muted ? 'Telegram: сповіщення на паузі' : 'Telegram підключено' }}</span>
      <span v-else-if="waiting">Очікуємо підтвердження…</span>
      <button v-if="session.user.telegram_muted" class="link-button" :disabled="busy" @click="setNotifications(true)">Увімкнути</button>
      <button v-else-if="!session.user.telegram_linked" class="link-button" :disabled="busy" @click="connect">Підключити Telegram</button>
    </div>
    <section v-else class="card telegram-card">
      <div>
        <strong>
          <Send :size="17" />
          Сповіщення в Telegram
        </strong>
        <p v-if="session.user.telegram_muted">Сповіщення призупинено. Бот і далі відповідає на команди меню, але не надсилає повідомлень про заявки.</p>
        <p v-else-if="session.user.telegram_linked">Підключено. Бот повідомить про зміну етапу ремонту, а кошторис можна погодити кнопкою прямо в чаті.</p>
        <p v-else-if="waiting">Натисніть «Start» у боті, що відкрився. Ця сторінка оновиться автоматично.</p>
        <p v-else>Отримуйте статус ремонту й погоджуйте кошторис без входу на сайт.</p>
      </div>
      <span v-if="session.user.telegram_muted" class="actions">
        <button class="button primary" :disabled="busy" @click="setNotifications(true)">
          <BellRing :size="16" />
          Увімкнути сповіщення
        </button>
        <button class="button" :disabled="busy" @click="disconnect">Відключити Telegram</button>
      </span>
      <span v-else-if="session.user.telegram_linked" class="actions">
        <button class="button" :disabled="busy" @click="setNotifications(false)">Призупинити</button>
        <button class="button" :disabled="busy" @click="disconnect">Відключити</button>
      </span>
      <button v-else class="button" :disabled="busy" @click="connect">
        <Send :size="16" />
        Підключити Telegram
      </button>
    </section>
  </template>
</template>
