<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { BellRing, Send } from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../state'
defineProps({ compact: Boolean })
const session = useSession(), available = ref(false), busy = ref(false), waiting = ref(false)
let timer
onMounted(async () => { try { available.value = (await api('/auth/options')).telegram } catch { available.value = false } })
onUnmounted(() => clearInterval(timer))
async function connect() {
  busy.value = true
  const tab = window.open('', '_blank')
  try {
    const { url } = await api('/auth/telegram-link', { method: 'POST' })
    if (tab) tab.location.href = url; else window.location.href = url
    waiting.value = true
    let attempts = 0
    clearInterval(timer)
    timer = setInterval(async () => {
      attempts += 1
      try { session.user = await api('/auth/me') } catch { /* повторимо */ }
      if (session.user?.telegram_linked || attempts > 60) {
        clearInterval(timer); waiting.value = false
        if (session.user?.telegram_linked) session.notify('Telegram підключено. Сповіщення надходитимуть у чат з ботом.')
      }
    }, 3000)
  } catch (e) { tab?.close(); session.notify(e.message, 'error') } finally { busy.value = false }
}
async function test() {
  busy.value = true
  try { await api('/auth/telegram-test', { method: 'POST' }); session.notify('Тестове повідомлення надіслано в Telegram.') }
  catch (e) { session.notify(e.message, 'error') } finally { busy.value = false }
}
async function disconnect() {
  busy.value = true
  try { session.user = await api('/auth/telegram-link', { method: 'DELETE' }); session.notify('Сповіщення в Telegram вимкнено.') }
  catch (e) { session.notify(e.message, 'error') } finally { busy.value = false }
}
</script>
<template>
  <template v-if="available">
    <div v-if="compact" class="telegram-compact">
      <BellRing :size="15"/>
      <span v-if="session.user.telegram_linked">Telegram підключено</span>
      <span v-else-if="waiting">Очікуємо підтвердження…</span>
      <button v-if="session.user.telegram_linked" class="link-button" :disabled="busy" @click="test">Перевірити</button>
      <button v-if="session.user.telegram_linked" class="link-button" :disabled="busy" @click="disconnect">Вимкнути</button>
      <button v-else class="link-button" :disabled="busy" @click="connect">Підключити Telegram</button>
    </div>
    <section v-else class="card telegram-card">
      <div><strong><Send :size="17"/> Сповіщення в Telegram</strong>
        <p v-if="session.user.telegram_linked">Підключено. Бот повідомить про зміну етапу ремонту, а кошторис можна погодити кнопкою прямо в чаті.</p>
        <p v-else-if="waiting">Натисніть «Start» у боті, що відкрився. Ця сторінка оновиться автоматично.</p>
        <p v-else>Отримуйте статус ремонту й погоджуйте кошторис без входу на сайт.</p></div>
      <span v-if="session.user.telegram_linked" class="actions">
        <button class="button" :disabled="busy" @click="test"><BellRing :size="16"/> Тестове повідомлення</button>
        <button class="button" :disabled="busy" @click="disconnect">Вимкнути</button>
      </span>
      <button v-else class="button" :disabled="busy" @click="connect"><Send :size="16"/> Підключити Telegram</button>
    </section>
  </template>
</template>
