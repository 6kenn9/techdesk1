<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Activity, Boxes, ChartNoAxesCombined, CircleDollarSign, ReceiptText, RefreshCw, Wrench } from 'lucide-vue-next'
import { api, query } from '../api'
import { date, money } from '../domain'
import Graph from '../components/Graph.vue'
const dashboard=ref(null), error=ref(''), busy=ref(false)
const range=reactive({start:'',end:''})
const palette=['#3267e4','#7e66d4','#e6a237','#3a9fc5','#1ea57b','#6b849f','#d96783','#4bc2c5','#787aab','#9e77a7']
const kpis=computed(()=>dashboard.value ? [
  ['Виручка',money(dashboard.value.revenue),CircleDollarSign],['Собівартість деталей',money(dashboard.value.parts_cost),Boxes],
  ['Розрахунковий прибуток',money(dashboard.value.profit),ChartNoAxesCombined],
  ['Активні ремонти',dashboard.value.active,Wrench],['Середній чек',money(dashboard.value.average),ReceiptText],
] : [])
const financial=computed(()=>({labels:dashboard.value.daily.map(item=>date(item.date)),datasets:[
  {label:'Виручка',data:dashboard.value.daily.map(item=>item.revenue),backgroundColor:palette[0],borderRadius:5},
  {label:'Собівартість',data:dashboard.value.daily.map(item=>item.parts_cost),backgroundColor:palette[3],borderRadius:5},
  {label:'Прибуток',data:dashboard.value.daily.map(item=>item.profit),backgroundColor:palette[4],borderRadius:5},
]}))
function distribution(values){
  const entries=Object.entries(values).filter(([,count])=>count>0)
  return {labels:entries.map(([name])=>name),datasets:[{data:entries.map(([,count])=>count),backgroundColor:palette,borderWidth:2,borderColor:'#fff'}]}
}
const workload=computed(()=>({labels:dashboard.value.staff.map(item=>item.name.split(' ')[0]),datasets:[
  {label:'Активні заявки',data:dashboard.value.staff.map(item=>item.active),backgroundColor:palette[0],borderRadius:5},
  {label:'Завершені за період',data:dashboard.value.staff.map(item=>item.completed),backgroundColor:palette[4],borderRadius:5},
]}))
async function load(){
  busy.value=true
  try{dashboard.value=await api('/analytics/dashboard'+query(range));error.value=''}
  catch(e){error.value=e.message}finally{busy.value=false}
}
onMounted(load)
</script>
<template>
  <div class="page-head"><div><div class="eyebrow"><Activity :size="15"/> КЕРУВАННЯ СЕРВІСНИМ ЦЕНТРОМ</div><h1>Огляд роботи центру</h1><p>Показники ремонтів, складських витрат і завантаженості команди.</p></div><RouterLink class="button primary" to="/orders/new">Нова заявка</RouterLink></div>
  <div class="stack">
    <form class="card filters" style="margin-bottom:0" @submit.prevent="load"><label>Початок періоду<input v-model="range.start" type="date"></label><label>Кінець періоду<input v-model="range.end" type="date"></label><button class="button" style="align-self:end" :disabled="busy"><RefreshCw :size="16"/> Оновити звіт</button></form>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="dashboard">
      <div class="kpis"><article v-for="[title,value,Icon] in kpis" :key="title" class="card kpi"><div class="actions"><span class="tile-icon" style="width:30px;height:30px"><component :is="Icon" :size="17"/></span><span>{{ title }}</span></div><strong>{{ value }}</strong></article></div>
      <div class="metric-grid">
        <section class="card"><div class="section-head"><div><h2>Фінанси за днями завершення</h2><p>Прибуток розраховано за вартістю замовлень і закупівельними цінами деталей.</p></div></div>
          <Graph v-if="dashboard.daily.length" type="bar" :data="financial" label="Виручка, собівартість запчастин і розрахунковий прибуток" tall/><div v-else class="empty">У вибраному періоді немає завершених заявок.</div></section>
        <section class="card"><div class="section-head"><div><h2>Етапи заявок</h2><p>Розподіл за заявками, прийнятими в періоді.</p></div></div><Graph v-if="Object.values(dashboard.statuses).some(Boolean)" type="doughnut" :data="distribution(dashboard.statuses)" label="Розподіл заявок за етапами" tall/><div v-else class="empty">Заявок у періоді немає.</div></section>
      </div>
      <div class="metric-grid">
        <section class="card"><div class="section-head"><h2>Завантаженість майстрів</h2></div><Graph v-if="dashboard.staff.length" type="bar" :data="workload" label="Активні та завершені заявки майстрів"/><div v-else class="empty">Майстрів ще не додано.</div></section>
        <section class="card"><div class="section-head"><h2>Категорії пристроїв</h2></div><Graph v-if="Object.keys(dashboard.categories).length" type="doughnut" :data="distribution(dashboard.categories)" label="Категорії пристроїв у заявках"/><div v-else class="empty">Даних у періоді немає.</div></section>
      </div>
      <section class="card"><div class="section-head"><h2>Результати команди</h2><RouterLink class="button small" to="/staff">Керування командою</RouterLink></div><div class="table-scroll"><table><thead><tr><th>Майстер</th><th>Спеціалізація</th><th>Активні</th><th>Завершені</th><th>Виручка</th></tr></thead><tbody><tr v-for="person in dashboard.staff" :key="person.id"><td><strong>{{ person.name }}</strong></td><td>{{ person.specialization || '—' }}</td><td>{{ person.active }}</td><td>{{ person.completed }}</td><td class="mono nowrap">{{ money(person.revenue) }}</td></tr></tbody></table></div></section>
    </template>
  </div>
</template>
