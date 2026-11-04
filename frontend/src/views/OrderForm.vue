<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, ScanLine } from 'lucide-vue-next'
import { api } from '../api'
import { useSession } from '../state'
import PassportFields from '../components/PassportFields.vue'
import Warranty from '../components/Warranty.vue'
import Modal from '../components/Modal.vue'

const session=useSession(), route=useRoute(), router=useRouter()
const staff=computed(()=>session.staff)
const step=ref(staff.value ? 1 : 2)
const clients=ref([]), masters=ref([]), devices=ref([]), owner=ref(''), device=ref(null), deviceId=ref('')
const serial=ref(route.query.serial || ''), newDevice=ref(false), error=ref(''), busy=ref(false), clientModal=ref(false)
const hardware=ref({serial_number:'',device_category:'Ноутбук',brand:'',model:'',specifications:{},cosmetic_condition:'',save_preset:false})
const order=reactive({problem_description:'',completeness:'',cosmetic_notes:'',priority:'normal',master_id:null,is_warranty_case:false})
const clientForm=reactive({full_name:'',email:'',phone:'',password:'',role:'client'})
const available=computed(()=>staff.value ? devices.value.filter(item=>item.owner_id===owner.value) : devices.value)
let lookupSequence=0
onMounted(async()=>{
  try{
    const list=await api('/passports')
    devices.value=list
    if(staff.value){
      const [people, workers]=await Promise.all([api('/users?role=client'),api('/users?role=master')])
      clients.value=people.filter(item=>item.is_active); masters.value=workers.filter(item=>item.is_active)
      if(serial.value){
        const found=list.find(item=>item.serial_number===serial.value)
        if(found){owner.value=found.owner_id;step.value=2;await lookup()}
      }
    }
  }catch(e){error.value=e.message}
})
function pick() {
  device.value=available.value.find(item=>item.id===deviceId.value) || null
  serial.value=device.value?.serial_number || ''
  newDevice.value=false
}
async function lookup(){
  if(!serial.value.trim())return
  const seq=++lookupSequence
  error.value=''
  try {
    const found=await api('/passports/lookup-sn/'+encodeURIComponent(serial.value.trim()))
    if(seq!==lookupSequence)return
    if(found && found.owner_id!==owner.value){device.value=null;deviceId.value='';newDevice.value=false;error.value='Цей пристрій зареєстровано за іншим клієнтом.';return}
    device.value=found;deviceId.value=found?.id || ''
    newDevice.value=!found
    hardware.value.serial_number=serial.value
  }catch(e){if(seq===lookupSequence)error.value=e.message}
}
function useNew(){
  deviceId.value='';device.value=null;newDevice.value=true
  hardware.value.serial_number=serial.value
}
function back(){
  error.value=''
  if(step.value===3){step.value=2;return}
  if(staff.value){step.value=1;deviceId.value='';device.value=null;newDevice.value=false}
}
async function addClient(){
  busy.value=true
  try{ const result=await api('/users',{method:'POST',data:clientForm}); clients.value.push(result); owner.value=result.id; clientModal.value=false }
  catch(e){session.notify(e.message,'error')} finally{busy.value=false}
}
async function save(){
  error.value='';busy.value=true
  try{
    let id=device.value?.id
    const {save_preset,...specs}=hardware.value
    if(!id && staff.value){
      const created=await api('/passports',{method:'POST',data:{...specs,owner_id:owner.value,save_preset}})
      device.value=created; id=created.id
    }
    const payload={...order,...(id ? {device_id:id} : {new_device:specs})}
    const result=await api('/orders',{method:'POST',data:payload})
    session.notify('Заявку зареєстровано.')
    await router.push('/orders/'+result.id)
  }catch(e){error.value=e.message}finally{busy.value=false}
}
</script>

<template>
  <RouterLink :to="staff?'/orders':'/my-cabinet'" class="back"><ArrowLeft :size="16"/> Повернутися до заявок</RouterLink>
  <div class="page-head"><div><div class="eyebrow">ПРИЙМАННЯ ТЕХНІКИ</div><h1>Нова заявка</h1><p>{{ staff ? 'Виберіть клієнта, знайдіть паспорт та опишіть несправність.' : 'Оберіть пристрій і розкажіть, що з ним сталося.' }}</p></div></div>
  <section class="card form-card">
    <div class="pills" aria-label="Кроки реєстрації"><span v-if="staff" class="pill" :class="{active:step===1}">1. Клієнт</span><span class="pill" :class="{active:step===2}">{{ staff ? '2.' : '1.' }} Пристрій</span><span class="pill" :class="{active:step===3}">{{ staff ? '3.' : '2.' }} Заявка</span></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <form v-if="step===1" class="form-stack" @submit.prevent="step=2">
      <label>Клієнт<select v-model="owner" required><option value="">Оберіть клієнта</option><option v-for="person in clients" :key="person.id" :value="person.id">{{ person.full_name }} · {{ person.phone }}</option></select></label>
      <div class="actions"><button v-if="session.admin" class="button" type="button" @click="clientModal=true">Зареєструвати клієнта</button><button class="button primary">Далі <ArrowRight :size="16"/></button></div>
    </form>
    <form v-else-if="step===2" class="form-stack" @submit.prevent="step=3">
      <label>Пристрій із реєстру<select v-model="deviceId" @change="pick"><option value="">Оберіть наявний пристрій</option><option v-for="item in available" :key="item.id" :value="item.id">{{ item.brand }} {{ item.model }} · {{ item.serial_number }}</option></select></label>
      <div v-if="staff" class="search-form"><label>Серійний номер або IMEI<input v-model.trim="serial" maxlength="80" placeholder="Введіть серійний номер" @change="lookup"></label><button type="button" class="button" style="align-self:end" @click="lookup"><ScanLine :size="17"/> Знайти паспорт</button></div>
      <Warranty :warranty="device?.warranty"/>
      <PassportFields v-if="newDevice" v-model="hardware" :allow-preset="staff"/>
      <div class="actions"><button v-if="staff" type="button" class="button" @click="back"><ArrowLeft :size="16"/> Назад</button><button v-if="!newDevice" type="button" class="button" @click="useNew">Новий пристрій</button><button class="button primary" :disabled="!device && !newDevice">Далі <ArrowRight :size="16"/></button></div>
    </form>
    <form v-else class="form-stack" @submit.prevent="save">
      <p><strong>{{ device ? device.brand+' '+device.model : hardware.brand+' '+hardware.model }}</strong> · <span class="mono">{{ device?.serial_number || hardware.serial_number }}</span></p>
      <Warranty :warranty="device?.warranty"/>
      <label>Опис несправності<textarea v-model.trim="order.problem_description" minlength="3" maxlength="4000" required></textarea></label>
      <label>Комплектація<input v-model.trim="order.completeness" placeholder="Наприклад, кабель живлення та сумка"></label>
      <label>Примітки про зовнішній стан<textarea v-model.trim="order.cosmetic_notes"></textarea></label>
      <div v-if="staff" class="form-grid">
        <label>Пріоритет<select v-model="order.priority"><option value="normal">Звичайний</option><option value="urgent">Терміновий</option></select></label>
        <label>Майстер<select v-model="order.master_id"><option :value="null">Не призначати</option><option v-for="worker in masters.filter(m=>session.admin || m.id===session.user.id)" :key="worker.id" :value="worker.id">{{ worker.full_name }} · активних: {{ worker.active_orders }}</option></select></label>
        <label class="check full"><input v-model="order.is_warranty_case" type="checkbox"> Гарантійний випадок</label>
      </div>
      <div class="actions"><button type="button" class="button" @click="back"><ArrowLeft :size="16"/> Назад</button><button class="button primary" :disabled="busy">{{ busy ? 'Зберігаємо…' : 'Зареєструвати заявку' }}</button></div>
    </form>
  </section>
  <Modal v-if="clientModal" title="Новий клієнт" @close="clientModal=false"><form class="form-stack" @submit.prevent="addClient">
    <label>Ім’я та прізвище<input v-model.trim="clientForm.full_name" required></label><label>Електронна пошта<input v-model.trim="clientForm.email" type="email" required></label>
    <label>Телефон<input v-model.trim="clientForm.phone" type="tel" required placeholder="+380…"></label><label>Тимчасовий пароль<input v-model="clientForm.password" type="password" minlength="8" required></label>
    <button class="button primary" :disabled="busy">Створити клієнта</button></form></Modal>
</template>
