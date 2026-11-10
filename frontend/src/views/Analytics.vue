<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { AlertTriangle, Banknote, CreditCard, FileSpreadsheet, Landmark, Boxes, ChartNoAxesCombined, CircleCheck, CircleDollarSign, Hourglass, PackageX, ReceiptText, RefreshCw, Wrench } from 'lucide-vue-next'
import { api, download, query } from '../api'
import { date, money } from '../domain'
import Graph from '../components/Graph.vue'
import StarRating from '../components/StarRating.vue'
import { cssVar, resolved } from '../theme'
const dashboard=ref(null), error=ref(''), busy=ref(false)
const range=reactive({start:'',end:''})
const presets=[['week','7 днів',7],['month','30 днів',30],['quarter','Квартал',90],['all','Увесь час',0],['custom','Свій період',null]]
const preset=ref('quarter')
const ratingShare=stars=>dashboard.value.rating.count?Math.round(dashboard.value.rating.distribution[stars]/dashboard.value.rating.count*100):0
const iso=value=>new Date(value.getTime()-value.getTimezoneOffset()*6e4).toISOString().slice(0,10)
function choose(key){
  preset.value=key
  const days=presets.find(p=>p[0]===key)[2]
  if(days===null) return
  if(days===0){range.start='';range.end=''}
  else{const end=new Date();const start=new Date(end);start.setDate(end.getDate()-days+1);range.start=iso(start);range.end=iso(end)}
  load()
}
function trend(key, upIsGood=true){
  const prev=dashboard.value?.previous
  if(!prev) return null
  const now=Number(dashboard.value[key]), before=Number(prev[key])
  if(!now && !before) return null
  if(!before) return {text:'нове', tone:upIsGood?'up':''}
  const change=Math.round((now-before)/Math.abs(before)*100)
  return {text:`${change>0?'↑':change<0?'↓':'→'} ${Math.abs(change)}%`, tone:change===0?'':(change>0)===upIsGood?'up':'down'}
}
// Кольори графіків беруться з поточної теми й оновлюються під час її зміни.
const palette=computed(()=>(resolved.value, {revenue:cssVar('--chart-1'), parts:cssVar('--chart-2'), profit:cssVar('--chart-3'), surface:cssVar('--surface'),
  distribution:resolved.value==='dark'
    ? ['#6b9bff','#4fd39d','#f2b84b','#b9a6ff','#ff8b84','#5ec8e5','#c5cbd6','#8a94a6','#3f6fd6','#2f9e74']
    : ['#2457d6','#0e9f6e','#d98a0b','#6d4fd6','#d9473d','#1592b5','#1f2937','#8a94a6','#93b4f5','#7fd8b4']}))
const kpis=computed(()=>dashboard.value ? [
  ['Виручка',money(dashboard.value.revenue),CircleDollarSign,trend('revenue')],['Собівартість деталей',money(dashboard.value.parts_cost),Boxes,trend('parts_cost',false)],
  ['Розрахунковий прибуток',money(dashboard.value.profit),ChartNoAxesCombined,trend('profit')],
  ['Активні ремонти',dashboard.value.active,Wrench,null],['Середній чек',money(dashboard.value.average),ReceiptText,trend('average')],
] : [])
const attention=computed(()=>dashboard.value?.attention)
const attentionCount=computed(()=>attention.value ? attention.value.stale.length+attention.value.waiting_approval.length+attention.value.low_stock.length : 0)
const days=n=>n===1?'1 день':n<5?`${n} дні`:`${n} днів`
const financial=computed(()=>({labels:dashboard.value.daily.map(item=>date(item.date)),datasets:[
  {label:'Виручка',data:dashboard.value.daily.map(item=>item.revenue),backgroundColor:palette.value.revenue,borderRadius:2},
  {label:'Собівартість',data:dashboard.value.daily.map(item=>item.parts_cost),backgroundColor:palette.value.parts,borderRadius:2},
  {label:'Прибуток',data:dashboard.value.daily.map(item=>item.profit),backgroundColor:palette.value.profit,borderRadius:2},
]}))
function distribution(values){
  const entries=Object.entries(values).filter(([,count])=>count>0)
  return {labels:entries.map(([name])=>name),datasets:[{data:entries.map(([,count])=>count),backgroundColor:palette.value.distribution,borderWidth:2,borderColor:palette.value.surface}]}
}
const workload=computed(()=>({labels:dashboard.value.staff.map(item=>item.name.split(' ')[0]),datasets:[
  {label:'Активні заявки',data:dashboard.value.staff.map(item=>item.active),backgroundColor:palette.value.revenue,borderRadius:2},
  {label:'Завершені за період',data:dashboard.value.staff.map(item=>item.completed),backgroundColor:palette.value.profit,borderRadius:2},
]}))
async function load(){
  busy.value=true
  try{dashboard.value=await api('/analytics/dashboard'+query(range));error.value=''}
  catch(e){error.value=e.message}finally{busy.value=false}
}
async function exportCsv(){ try{ await download('/analytics/export.csv'+query(range),`techdesk-аналітика-${range.start||'весь-час'}.csv`) }catch(e){ error.value=e.message } }
const payTotal=computed(()=>dashboard.value?Object.values(dashboard.value.payment_methods).reduce((s,v)=>s+Number(v),0):0)
const payRows=computed(()=>dashboard.value?[['cash','Готівка',Banknote],['card','Картка',CreditCard],['transfer','Переказ',Landmark]].map(([k,l,I])=>({key:k,label:l,icon:I,value:Number(dashboard.value.payment_methods[k]),share:payTotal.value?Math.round(Number(dashboard.value.payment_methods[k])/payTotal.value*100):0})):[])
onMounted(()=>choose('quarter'))
</script>
<template>
  <div class="page-head"><div class="page-title"><h1>Огляд роботи центру</h1><span v-if="dashboard" class="count" title="Активні ремонти">{{ dashboard.active }}</span></div><span class="actions"><button class="button" type="button" title="Завантажити звіт за вибраний період для Excel" @click="exportCsv"><FileSpreadsheet :size="16"/> Експорт</button><RouterLink class="button primary" to="/orders/intake">Швидке приймання</RouterLink></span></div>
  <div class="stack">
    <div class="period-bar"><div class="segmented" role="group" aria-label="Період звіту"><button v-for="[key,label] in presets" :key="key" class="button small" :aria-pressed="preset===key" @click="choose(key)">{{ label }}</button></div>
      <small v-if="dashboard?.previous">Порівняння з {{ date(dashboard.previous.start) }} – {{ date(dashboard.previous.end) }}</small></div>
    <form v-if="preset==='custom'" class="card filters" style="margin-bottom:0" @submit.prevent="load"><label>Початок періоду<input v-model="range.start" type="date"></label><label>Кінець періоду<input v-model="range.end" type="date"></label><button class="button" style="align-self:end" :disabled="busy"><RefreshCw :size="16"/> Показати</button></form>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="dashboard">
      <div class="kpis"><article v-for="[title,value,Icon,change] in kpis" :key="title" class="card kpi"><div class="kpi-label"><component :is="Icon" :size="16"/><span>{{ title }}</span></div><strong>{{ value }}</strong><span v-if="change" class="kpi-trend" :class="change.tone">{{ change.text }} <small>до попер. періоду</small></span></article></div>
      <section class="card attention" :class="{ calm: !attentionCount }">
        <div class="section-head"><h2><component :is="attentionCount ? AlertTriangle : CircleCheck" :size="19"/> {{ attentionCount ? 'Потребує уваги' : 'Усе під контролем' }} <span v-if="attentionCount" class="count">{{ attentionCount }}</span></h2></div>
        <div v-if="attentionCount" class="attention-grid">
          <div><h3><Hourglass :size="16"/> Застрягли на етапі</h3><p>Без майстра або довше {{ days(attention.stale_days) }}.</p>
            <ul v-if="attention.stale.length" class="attention-list"><li v-for="o in attention.stale" :key="o.id"><RouterLink :to="'/orders/'+o.id"><strong class="mono">{{ o.order_number }}</strong> {{ o.device }}</RouterLink><small>{{ o.label }} · {{ o.master ? days(o.days) : 'без майстра' }}</small></li></ul><small v-else>Немає.</small></div>
          <div><h3><CircleDollarSign :size="16"/> Клієнт не відповідає</h3><p>Кошторис без рішення {{ days(attention.approval_days) }} і довше.</p>
            <ul v-if="attention.waiting_approval.length" class="attention-list"><li v-for="o in attention.waiting_approval" :key="o.id"><RouterLink :to="'/orders/'+o.id"><strong class="mono">{{ o.order_number }}</strong> {{ o.device }}</RouterLink><small>чекає {{ days(o.days) }}</small></li></ul><small v-else>Немає.</small></div>
          <div><h3><PackageX :size="16"/> Закінчуються деталі</h3><p>Залишок на мінімумі або нижче.</p>
            <ul v-if="attention.low_stock.length" class="attention-list"><li v-for="p in attention.low_stock" :key="p.id"><RouterLink to="/warehouse">{{ p.name }}</RouterLink><small :class="{ critical: !p.quantity }">{{ p.quantity }} шт. з мінімуму {{ p.minimum }}</small></li></ul><small v-else>Немає.</small></div>
        </div>
        <p v-else>Немає застряглих заявок, кошторисів без відповіді чи дефіциту деталей.</p>
      </section>
      <div class="metric-grid">
        <section class="card"><div class="section-head"><div><h2>Фінанси за днями завершення</h2><p>Прибуток розраховано за вартістю замовлень і закупівельними цінами деталей.</p></div></div>
          <Graph v-if="dashboard.daily.length" type="bar" :data="financial" label="Виручка, собівартість запчастин і розрахунковий прибуток" tall/><div v-else class="empty">У вибраному періоді немає завершених заявок.</div></section>
        <section class="card"><div class="section-head"><div><h2>Етапи заявок</h2><p>Розподіл за заявками, прийнятими в періоді.</p></div></div><Graph v-if="Object.values(dashboard.statuses).some(Boolean)" type="doughnut" :data="distribution(dashboard.statuses)" label="Розподіл заявок за етапами" tall/><div v-else class="empty">Заявок у періоді немає.</div></section>
      </div>
      <section class="card pay-card"><div class="section-head"><div><h2>Оплати за способами</h2><p>Отримані кошти за заявками, завершеними в періоді.</p></div><strong class="mono">{{ money(payTotal) }}</strong></div>
        <div v-if="payTotal" class="pay-rows"><div v-for="row in payRows" :key="row.key" class="pay-row"><span><component :is="row.icon" :size="16"/> {{ row.label }}</span><div class="pay-bar"><i :class="row.key" :style="{width:row.share+'%'}"></i></div><strong class="mono">{{ money(row.value) }}</strong><small>{{ row.share }}%</small></div></div>
        <div v-else class="empty">У вибраному періоді оплат за завершеними заявками немає.</div></section>
      <section class="card rating-card"><div class="section-head"><div><h2>Задоволеність клієнтів</h2><p>Оцінки за ремонти, завершені в періоді.</p></div></div>
        <div v-if="dashboard.rating.count" class="metric-grid">
          <div><div class="rating-big">{{ dashboard.rating.average.toFixed(1).replace('.',',') }}</div><StarRating :model-value="dashboard.rating.average" readonly :size="20"/><p class="muted">{{ dashboard.rating.count }} оцінок</p>
            <div class="rating-bars"><div v-for="n in [5,4,3,2,1]" :key="n"><span>{{ n }} ★</span><i><b :style="{width:ratingShare(n)+'%'}"></b></i><small class="mono">{{ dashboard.rating.distribution[n] }}</small></div></div></div>
          <div><h3>Останні відгуки</h3><ul class="log"><li v-for="r in dashboard.rating.recent" :key="r.id"><RouterLink :to="'/orders/'+r.id" class="mono">{{ r.order_number }}</RouterLink> <StarRating :model-value="r.rating" readonly :size="14"/><p v-if="r.comment" class="wrap-text">{{ r.comment }}</p></li></ul></div>
        </div>
        <div v-else class="empty">Клієнти ще не оцінили жодного ремонту в цьому періоді.</div></section>
      <div class="metric-grid">
        <section class="card"><div class="section-head"><h2>Завантаженість майстрів</h2></div><Graph v-if="dashboard.staff.length" type="bar" :data="workload" label="Активні та завершені заявки майстрів"/><div v-else class="empty">Майстрів ще не додано.</div></section>
        <section class="card"><div class="section-head"><h2>Категорії пристроїв</h2></div><Graph v-if="Object.keys(dashboard.categories).length" type="doughnut" :data="distribution(dashboard.categories)" label="Категорії пристроїв у заявках"/><div v-else class="empty">Даних у періоді немає.</div></section>
      </div>
      <section class="card"><div class="section-head"><h2>Результати команди</h2><RouterLink class="button small" to="/staff">Керування командою</RouterLink></div><div class="table-scroll"><table><thead><tr><th>Майстер</th><th>Спеціалізація</th><th>Активні</th><th>Завершені</th><th>Виручка</th><th>Оцінка</th></tr></thead><tbody><tr v-for="person in dashboard.staff" :key="person.id"><td><strong>{{ person.name }}</strong></td><td>{{ person.specialization || '—' }}</td><td>{{ person.active }}</td><td>{{ person.completed }}</td><td class="mono nowrap">{{ money(person.revenue) }}</td><td class="nowrap">{{ person.rating ? '★ ' + person.rating.toFixed(1).replace('.',',') : '—' }}</td></tr></tbody></table></div></section>
    </template>
  </div>
</template>
