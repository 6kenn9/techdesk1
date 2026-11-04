<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, Copy, Cpu, Pencil, QrCode, Wrench } from 'lucide-vue-next'
import { api } from '../api'
import { dateTime, icons, specLabels } from '../domain'
import { useSession } from '../state'
import Modal from '../components/Modal.vue'
import PassportFields from '../components/PassportFields.vue'
import Stage from '../components/Stage.vue'
import Warranty from '../components/Warranty.vue'

const id = useRoute().params.id
const session = useSession()
const item = ref(null), error = ref(''), tab = ref('spec'), modal = ref(''), form = ref({}), qr = ref('')
const busy = ref(false)
onMounted(async () => { try { item.value = await api('/passports/' + id) } catch(e) { error.value=e.message } })
onUnmounted(() => { if (qr.value) URL.revokeObjectURL(qr.value) })
function edit() {
  const { serial_number, device_category, brand, model, specifications, cosmetic_condition } = item.value
  form.value = { serial_number, device_category, brand, model, specifications: { ...specifications }, cosmetic_condition }
  modal.value='edit'
}
function upgrade() { form.value = { field_name: Object.keys(item.value.specifications)[0] || 'ram', new_value:'', change_reason:'' }; modal.value='upgrade' }
function defect() { form.value = { description:'' }; modal.value='defect' }
async function save() {
  busy.value=true
  try {
    const path = { edit:'', upgrade:'/upgrade-spec', defect:'/defects' }[modal.value]
    item.value = await api('/passports/' + id + path, {method: modal.value === 'edit' ? 'PUT' : 'POST', data:form.value})
    modal.value=''; session.notify('Паспорт оновлено.')
  } catch(e) { session.notify(e.message, 'error') } finally { busy.value=false }
}
async function showQr() {
  try {
    if (!qr.value) qr.value = URL.createObjectURL(await api('/passports/' + id + '/qr', { blob:true }))
    modal.value='qr'
  } catch(e) { session.notify(e.message, 'error') }
}
async function copy() {
  try { await navigator.clipboard.writeText(item.value.serial_number); session.notify('Серійний номер скопійовано.') }
  catch { session.notify('Не вдалося скопіювати номер.', 'error') }
}
</script>
<template>
  <RouterLink class="back" to="/passports"><ArrowLeft :size="16"/> Паспорти пристроїв</RouterLink>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="item">
    <div class="page-head"><div><div class="eyebrow"><component :is="icons[item.device_category] || Cpu" :size="16"/> {{ item.device_category.toUpperCase() }} · ЦИФРОВИЙ ПАСПОРТ</div><h1>{{ item.brand }} {{ item.model }}</h1><p>Власник: {{ item.owner_name }}</p></div>
      <div class="actions"><button class="button" @click="showQr"><QrCode :size="18"/> Код паспорта</button><button v-if="session.staff" class="button primary" @click="edit"><Pencil :size="16"/> Редагувати</button></div></div>
    <div class="card stack">
      <div class="section-head"><div><small>Серійний номер</small><div class="actions"><strong class="mono">{{ item.serial_number }}</strong><button class="icon-button" aria-label="Скопіювати серійний номер" @click="copy"><Copy :size="15"/></button></div></div>
        <RouterLink v-if="session.staff" class="button" :to="{path:'/orders/new',query:{serial:item.serial_number}}">Нова заявка <ArrowUpRight :size="16"/></RouterLink></div>
      <Warranty :warranty="item.warranty"/>
      <div class="tabs"><button v-for="[value,label] in [['spec','Характеристики'],['history','Живий паспорт'],['repairs','Ремонти й дефекти']]" :key="value" class="tab" :class="{active:tab===value}" @click="tab=value">{{ label }}</button></div>
      <template v-if="tab==='spec'">
        <dl v-if="Object.keys(item.specifications).length" class="specs"><div v-for="(value,key) in item.specifications" :key="key"><dt>{{ specLabels[key] || key }}</dt><dd>{{ value || '—' }}</dd></div></dl>
        <p v-else>Характеристики ще не внесено.</p>
        <div><h3>Зовнішній стан</h3><p class="wrap-text">{{ item.cosmetic_condition || 'Відомості про стан відсутні.' }}</p></div>
      </template>
      <template v-if="tab==='history'">
        <div class="section-head"><h2>Історія конфігурації</h2><button v-if="session.staff" class="button" @click="upgrade"><Wrench :size="16"/> Оновити характеристику</button></div>
        <ul v-if="item.spec_history.length" class="log"><li v-for="entry in item.spec_history" :key="entry.id"><strong>{{ specLabels[entry.field_name] || entry.field_name }}</strong> · {{ entry.old_value || '—' }} → {{ entry.new_value || '—' }}<small>{{ dateTime(entry.changed_at) }} · {{ entry.technician }} {{ entry.order_number || '' }}</small><p>{{ entry.change_reason }}</p></li></ul>
        <div v-else class="empty">Змін конфігурації ще немає.</div>
      </template>
      <template v-if="tab==='repairs'">
        <div class="section-head"><h2>Дефекти й ремонти</h2><button v-if="session.staff" class="button" @click="defect">Зафіксувати дефект</button></div>
        <ul v-if="item.known_defects_history.length" class="log"><li v-for="(defect,i) in item.known_defects_history" :key="i">{{ defect }}</li></ul>
        <div v-if="item.orders.length" class="table-scroll"><table><thead><tr><th>Заявка</th><th>Несправність</th><th>Етап</th></tr></thead><tbody><tr v-for="order in item.orders" :key="order.id"><td><RouterLink :to="'/orders/'+order.id" class="mono">{{ order.order_number }}</RouterLink></td><td>{{ order.problem_description }}</td><td><Stage :status="order.status"/></td></tr></tbody></table></div>
        <div v-else class="empty">Ремонтів ще немає.</div>
      </template>
    </div>
    <Modal v-if="modal" :title="{edit:'Редагування паспорта',upgrade:'Оновлення конфігурації',defect:'Запис про дефект',qr:'Код цифрового паспорта'}[modal]" @close="modal=''">
      <img v-if="modal==='qr'" :src="qr" class="qr-preview" alt="Код для відкриття паспорта">
      <form v-else class="form-stack" @submit.prevent="save">
        <PassportFields v-if="modal==='edit'" v-model="form"/>
        <label v-else-if="modal==='defect'">Опис виявленого дефекту<textarea v-model.trim="form.description" minlength="3" maxlength="4000" required></textarea></label>
        <template v-else><label>Характеристика<select v-model="form.field_name" required><option v-for="(label,key) in specLabels" :key="key" :value="key">{{ label }}</option></select></label>
          <label>Нове значення<input v-model.trim="form.new_value" required maxlength="160"></label><label>Причина<textarea v-model.trim="form.change_reason"></textarea></label></template>
        <button class="button primary" :disabled="busy">Зберегти зміни</button>
      </form>
    </Modal>
  </template>
</template>
