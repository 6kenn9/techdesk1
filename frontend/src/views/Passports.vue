<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search } from 'lucide-vue-next'
import { api, query } from '../api'
import { categories } from '../domain'
import { useSession } from '../state'
import DeviceCard from '../components/DeviceCard.vue'
import PassportFields from '../components/PassportFields.vue'
import Modal from '../components/Modal.vue'

const session = useSession()
const router = useRouter()
const filters = reactive({ q: '', category: '', ...session.filters.passports })
const items = ref([])
const users = ref([])
const error = ref('')
const modal = ref(false)
const saving = ref(false)
const form = ref({})
let request = 0
async function load() {
  const sequence = ++request
  try {
    const data = await api('/passports' + query(filters))
    if (request === sequence) { items.value = data; error.value = '' }
  } catch (e) { if (request === sequence) error.value = e.message }
}
watch(filters, () => { session.filters.passports = { ...filters }; load() })
onMounted(load)
async function create() {
  form.value = { owner_id: '', serial_number: '', device_category: 'Ноутбук', brand: '', model: '', specifications: {}, cosmetic_condition: '', save_preset: false }
  try { users.value = await api('/users?role=client'); modal.value = true }
  catch (e) { session.notify(e.message, 'error') }
}
async function save() {
  saving.value = true
  try {
    const existing = await api('/passports/lookup-sn/' + encodeURIComponent(form.value.serial_number))
    if (existing) { session.notify('Паспорт з таким номером уже є.'); return router.push('/passports/' + existing.id) }
    const item = await api('/passports', { method: 'POST', data: form.value })
    session.notify('Цифровий паспорт створено.')
    await router.push('/passports/' + item.id)
  } catch (e) { session.notify(e.message, 'error') }
  finally { saving.value = false }
}
</script>
<template>
  <div class="page-head"><div class="page-title"><h1>Паспорти пристроїв</h1><span class="count">{{ items.length }}</span></div>
    <button v-if="session.staff" class="button primary" @click="create"><Plus :size="16"/> Новий паспорт</button></div>
  <label class="input-icon" style="margin-bottom:14px"><Search :size="20"/><input v-model.trim="filters.q" aria-label="Пошук паспортів" placeholder="Серійний номер, модель, клієнт або телефон"></label>
  <div class="pills"><button class="pill" :class="{active:!filters.category}" @click="filters.category=''">Усі категорії</button>
    <button v-for="item in categories" :key="item" class="pill" :class="{active:filters.category===item}" @click="filters.category=item">{{ item }}</button></div>
  <p v-if="error" class="error">{{ error }}</p><div v-else-if="!items.length" class="empty">За цим запитом паспортів немає.</div>
  <div class="grid-3"><DeviceCard v-for="item in items" :key="item.id" :item="item"/></div>
  <Modal v-if="modal" title="Новий цифровий паспорт" @close="modal=false">
    <form class="form-stack" @submit.prevent="save"><label>Власник<select v-model="form.owner_id" required><option value="">Оберіть клієнта</option><option v-for="user in users.filter(u => u.is_active)" :key="user.id" :value="user.id">{{ user.full_name }} · {{ user.phone }}</option></select></label>
      <PassportFields v-model="form" allow-preset/><button class="button primary" :disabled="saving">Створити паспорт</button></form>
  </Modal>
</template>
