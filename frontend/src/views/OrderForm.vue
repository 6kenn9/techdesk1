<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Plus } from 'lucide-vue-next'
import { api } from '../api'
import { devicePayload, emptyQuick, icons } from '../domain'
import { useSession } from '../state'
import QuickFields from '../components/QuickFields.vue'
import DeliveryFields from '../components/DeliveryFields.vue'

const session = useSession(), router = useRouter()
if (session.staff) router.replace('/orders/intake')
const devices = ref([]), pick = ref(null), form = ref(emptyQuick()), error = ref(''), busy = ref(false), loaded = ref(false)
const delivery = ref({ method: 'pickup', city: '', branch: '' })
const known = computed(() => devices.value.length > 0 && pick.value !== 'new')
const device = computed(() => devices.value.find(item => item.id === pick.value))
onMounted(async () => {
  try {
    devices.value = await api('/passports')
    if (devices.value.length === 1) pick.value = devices.value[0].id
  } catch (e) { error.value = e.message } finally { loaded.value = true }
})
async function save() {
  error.value = ''; busy.value = true
  try {
    const data = { problem_description: form.value.problem_description, delivery: delivery.value }
    if (device.value) data.device_id = device.value.id
    else data.new_device = devicePayload(form.value)
    const result = await api('/orders', { method: 'POST', data })
    session.notify('Заявку зареєстровано.')
    await router.push('/orders/' + result.id)
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <RouterLink to="/my-cabinet" class="back"><ArrowLeft :size="16"/> Повернутися до кабінету</RouterLink>
  <div class="page-head"><h1>Нова заявка</h1></div>
  <section class="card form-card">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <form class="form-stack" @submit.prevent="save">
      <template v-if="loaded && devices.length">
        <div><strong>Який пристрій принесли?</strong>
          <div class="device-picks" style="margin-top:8px">
            <button v-for="item in devices" :key="item.id" type="button" class="device-pick" :class="{ active: pick === item.id }" @click="pick = item.id">
              <component :is="icons[item.device_category]" :size="22"/><span><strong>{{ item.brand }} {{ item.model }}</strong><small>{{ item.serial_number || 'без серійного номера' }}</small></span>
            </button>
            <button type="button" class="device-pick" :class="{ active: pick === 'new' }" @click="pick = 'new'"><Plus :size="22"/><span><strong>Інший пристрій</strong><small>Додати новий</small></span></button>
          </div>
        </div>
        <label v-if="device">Що сталося?<textarea v-model.trim="form.problem_description" required minlength="3" maxlength="4000" rows="3" placeholder="Коротко опишіть несправність"></textarea></label>
      </template>
      <QuickFields v-if="loaded && !device && (pick === 'new' || !devices.length)" v-model="form" show-serial/>
      <DeliveryFields v-if="loaded && (device || pick === 'new' || !devices.length)" v-model="delivery"/>
      <div class="actions"><button class="button primary" :disabled="busy || (!device && pick !== 'new' && devices.length > 0)">{{ busy ? 'Зберігаємо…' : 'Подати заявку' }}</button></div>
    </form>
  </section>
</template>
