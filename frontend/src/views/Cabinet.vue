<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ArrowUpRight, Download, Plus, RefreshCw } from 'lucide-vue-next'
import { api, download } from '../api'
import { date, money } from '../domain'
import { useSession } from '../state'
import DeviceCard from '../components/DeviceCard.vue'
import TelegramConnect from '../components/TelegramConnect.vue'
import Stage from '../components/Stage.vue'
import Timeline from '../components/Timeline.vue'
const guest=reactive({email:'',password:''}), saving=ref(false)
async function completeRegistration(){
  saving.value=true
  try{session.user=await api('/auth/complete-registration',{method:'POST',data:guest});session.notify('Обліковий запис завершено: тепер можна входити за поштою.')}
  catch(e){session.notify(e.message,'error')}finally{saving.value=false}
}
const session=useSession(), devices=ref([]), orders=ref([]), error=ref(''), busy=ref(true)
const waiting=computed(()=>orders.value.filter(item=>item.status==='waiting_approval' && item.client_approval_status==='pending'))
async function load(){
  busy.value=true
  try { [devices.value,orders.value]=await Promise.all([api('/passports'),api('/orders')]);error.value='' }
  catch(e){error.value=e.message}finally{busy.value=false}
}
let refresh
onMounted(() => {
  load()
  refresh=setInterval(() => { if (!document.hidden && !busy.value) load() }, 15000)
})
onUnmounted(() => clearInterval(refresh))
async function pdf(order, kind){
  try{await download('/orders/'+order.id+'/pdf/'+kind,order.order_number+(kind==='receipt'?'-квитанція.pdf':'-гарантія.pdf'))}
  catch(e){session.notify(e.message,'error')}
}
</script>
<template>
  <div class="page-head"><div class="page-title"><h1>Особистий кабінет</h1><span class="count" title="Замовлення">{{ orders.length }}</span></div><div class="actions"><button class="button" :disabled="busy" @click="load"><RefreshCw :size="16"/> Оновити</button><RouterLink class="button primary" to="/orders/new"><Plus :size="16"/> Заявка на ремонт</RouterLink></div></div>
  <p v-if="error" class="error">{{ error }}</p>
  <div class="stack">
    <section v-if="session.user.is_guest" class="card guest-banner"><div><h2>Збережіть доступ до кабінету</h2><p class="muted">Зараз ви увійшли за особистим посиланням. Вкажіть пошту й пароль, щоб заходити будь-коли.</p></div>
      <form class="form-grid" @submit.prevent="completeRegistration"><label>Електронна пошта<input v-model.trim="guest.email" type="email" autocomplete="email" required></label><label>Пароль<input v-model="guest.password" type="password" minlength="8" autocomplete="new-password" required></label><div class="actions full"><button class="button primary" :disabled="saving">Завершити реєстрацію</button></div></form></section>
    <TelegramConnect/>
    <div v-for="item in waiting" :key="item.id" class="alert warranty section-head"><div><strong>{{ item.order_number }} очікує погодження</strong><p>{{ item.device }} · {{ money(item.total_cost) }}</p></div><RouterLink class="button primary" :to="'/orders/'+item.id">Переглянути кошторис <ArrowUpRight :size="16"/></RouterLink></div>
    <section><div class="section-head"><h2>Мої пристрої <span class="count">{{ devices.length }}</span></h2><RouterLink to="/passports" class="button small">Усі паспорти</RouterLink></div><div v-if="devices.length" class="grid-3"><DeviceCard v-for="item in devices" :key="item.id" :item="item"/></div><div v-else-if="!busy" class="empty">Паспорти з’являться після реєстрації пристрою.</div></section>
    <section><div class="section-head"><h2>Мої замовлення</h2></div><div v-if="orders.length" class="order-list">
      <article v-for="item in orders" :key="item.id" class="order-list-row">
        <div class="section-head"><div><h3><RouterLink :to="'/orders/'+item.id" class="mono">{{ item.order_number }}</RouterLink> · {{ item.device }}</h3><small>{{ date(item.created_at) }}</small></div><Stage :status="item.status"/></div>
        <Timeline :status="item.status"/>
        <div class="actions order-docs"><RouterLink :to="'/orders/'+item.id" class="button small">Деталі заявки <ArrowUpRight :size="15"/></RouterLink><button class="button small" @click="pdf(item,'receipt')"><Download :size="15"/> Квитанція</button><button v-if="['ready_for_pickup','completed'].includes(item.status)" class="button small" @click="pdf(item,'warranty')"><Download :size="15"/> Гарантійний талон</button></div>
      </article>
    </div><div v-else-if="!busy" class="empty">Ви ще не подавали заявок на ремонт.</div></section>
  </div>
</template>
