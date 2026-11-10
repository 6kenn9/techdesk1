<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { ImagePlus, Trash2, X } from 'lucide-vue-next'
import { api } from '../api'
import { dateTime } from '../domain'
import { useSession } from '../state'
const props = defineProps({ deviceId: { type: Number, required: true }, orderId: Number, canUpload: Boolean, orders: { type: Array, default: () => [] }, framed: Boolean, title: String })
const session = useSession(), photos = ref([]), urls = ref({}), busy = ref(false), open = ref(null), loaded = ref(false)
const form = ref({ caption: '', order_id: props.orderId || '' })
const base = '/passports/' + props.deviceId + '/photos'
async function load() {
  try {
    photos.value = await api(base + (props.orderId ? '?order_id=' + props.orderId : ''))
    await Promise.all(photos.value.filter(p => !urls.value[p.id]).map(async p => {
      urls.value[p.id] = URL.createObjectURL(await api('/photos/' + p.id, { blob: true }))
    }))
  } catch (e) { session.notify(e.message, 'error') } finally { loaded.value = true }
}
async function upload(event) {
  const files = [...event.target.files]
  if (!files.length) return
  busy.value = true
  try {
    for (const file of files) {
      const data = new FormData()
      data.append('file', file)
      data.append('caption', form.value.caption)
      if (form.value.order_id) data.append('order_id', form.value.order_id)
      await api(base, { method: 'POST', data })
    }
    form.value.caption = ''
    session.notify(files.length > 1 ? `Додано фото: ${files.length}.` : 'Фото додано.')
    await load()
  } catch (e) { session.notify(e.message, 'error') } finally { busy.value = false; event.target.value = '' }
}
async function remove(photo) {
  if (!confirm('Видалити це фото?')) return
  try {
    await api('/photos/' + photo.id, { method: 'DELETE' })
    URL.revokeObjectURL(urls.value[photo.id]); delete urls.value[photo.id]
    photos.value = photos.value.filter(p => p.id !== photo.id); open.value = null
  } catch (e) { session.notify(e.message, 'error') }
}
onMounted(load)
onUnmounted(() => Object.values(urls.value).forEach(URL.revokeObjectURL))
</script>
<template>
  <section v-if="!(loaded && !canUpload && !photos.length)" class="stack" :class="{ card: framed }">
    <div v-if="title" class="section-head"><h2>{{ title }}</h2><span v-if="photos.length" class="chip">{{ photos.length }}</span></div>
    <div v-if="canUpload" class="photo-upload">
      <label>Підпис<input v-model.trim="form.caption" maxlength="200" placeholder="Наприклад: подряпина на кришці"></label>
      <label v-if="!orderId && orders.length">Заявка<select v-model="form.order_id"><option value="">Без прив’язки</option><option v-for="o in orders" :key="o.id" :value="o.id">{{ o.order_number }}</option></select></label>
      <label class="button" :class="{ disabled: busy }"><ImagePlus :size="17"/> {{ busy ? 'Завантаження…' : 'Додати фото' }}
        <input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden :disabled="busy" @change="upload"></label>
    </div>
    <div v-if="photos.length" class="photo-grid">
      <button v-for="photo in photos" :key="photo.id" class="photo-tile" @click="open=photo">
        <img v-if="urls[photo.id]" :src="urls[photo.id]" :alt="photo.caption || 'Фото пристрою'" loading="lazy">
        <span>{{ photo.caption || 'Без підпису' }}<small>{{ dateTime(photo.created_at) }}<template v-if="photo.order_number"> · {{ photo.order_number }}</template></small></span>
      </button>
    </div>
    <div v-else class="empty">Фото ще не додано.</div>
    <dialog v-if="open" class="photo-viewer" open @click.self="open=null">
      <div><img :src="urls[open.id]" :alt="open.caption">
        <div class="section-head"><p>{{ open.caption || 'Без підпису' }} · {{ open.uploaded_by }} · {{ dateTime(open.created_at) }}</p>
          <div class="actions"><button v-if="session.admin || open.uploaded_by_id===session.user.id" class="icon-button" aria-label="Видалити фото" @click="remove(open)"><Trash2 :size="17"/></button>
          <button class="icon-button" aria-label="Закрити" @click="open=null"><X :size="19"/></button></div></div></div>
    </dialog>
  </section>
</template>
