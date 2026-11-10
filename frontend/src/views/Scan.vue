<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Camera, Search } from 'lucide-vue-next'
import jsQR from 'jsqr'
import { api } from '../api'
import { useSession } from '../state'
const router = useRouter(), session = useSession()
const video = ref(null), active = ref(false), message = ref(''), manual = ref(''), busy = ref(false)
const secure = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia
let stream, frame, detector
const canvas = document.createElement('canvas')
async function start() {
  message.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
    video.value.srcObject = stream
    await video.value.play()
    if ('BarcodeDetector' in window) {
      try { detector = new window.BarcodeDetector({ formats: ['qr_code'] }) } catch { detector = null }
    }
    active.value = true
    tick()
  } catch { message.value = 'Немає доступу до камери. Дозвольте доступ у браузері або введіть номер вручну.' }
}
function stop() { cancelAnimationFrame(frame); stream?.getTracks().forEach(t => t.stop()); active.value = false }
async function decode() {
  const source = video.value
  if (!source || source.readyState < 2) return null
  if (detector) {
    const [code] = await detector.detect(source).catch(() => [])
    if (code) return code.rawValue
  }
  canvas.width = source.videoWidth; canvas.height = source.videoHeight
  const context = canvas.getContext('2d', { willReadFrequently: true })
  context.drawImage(source, 0, 0)
  return jsQR(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height)?.data || null
}
let last = 0
async function tick(time = 0) {
  if (!active.value) return
  if (time - last > 250) {
    last = time
    const value = await decode()
    if (value) { stop(); return open(value) }
  }
  frame = requestAnimationFrame(tick)
}
async function open(value) {
  const text = value.trim()
  try {
    const url = new URL(text)
    const path = url.pathname.match(/^\/(passports|orders)\/\d+$|^\/track\/[^/]+$/)?.[0]
    if (path) return router.push(path + url.hash)
  } catch { /* не посилання — шукаємо як серійний номер */ }
  busy.value = true
  try {
    const device = await api('/passports/lookup-sn/' + encodeURIComponent(text))
    if (device) return router.push('/passports/' + device.id)
    session.notify('Паспорт не знайдено. Можна оформити нову заявку.')
    router.push({ path: '/orders/new', query: { serial: text } })
  } catch (e) { message.value = e.message } finally { busy.value = false }
}
onMounted(() => { if (secure) start() })
onUnmounted(stop)
</script>
<template>
  <div class="page-head"><div class="page-title"><h1>Сканер</h1></div></div>
  <div class="scanner stack">
    <section class="card stack">
      <p>Наведіть камеру на QR-наліпку пристрою, квитанцію або гарантійний талон.</p>
      <div v-if="secure" class="scanner-view"><video ref="video" muted playsinline></video><span v-if="active" class="scanner-frame"></span></div>
      <p v-else class="alert">Камера доступна лише через HTTPS або на localhost. Відкрийте TechDesk за захищеною адресою або введіть номер вручну.</p>
      <p v-if="message" class="error">{{ message }}</p>
      <button v-if="secure && !active" class="button primary" @click="start"><Camera :size="17"/> Увімкнути камеру</button>
    </section>
    <form class="card form-stack" @submit.prevent="open(manual)">
      <label>Серійний номер або посилання<input v-model.trim="manual" required maxlength="200" placeholder="TD-ASU-10482"></label>
      <button class="button" :disabled="busy"><Search :size="16"/> Знайти</button>
    </form>
  </div>
</template>
