<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { Boxes, PackagePlus, Pencil, Plus, Search } from 'lucide-vue-next'
import { api, query } from '../api'
import { categories, dateTime, money, specLabels } from '../domain'
import { useSession } from '../state'
import Modal from '../components/Modal.vue'
const session=useSession(), tab=ref('parts'), modal=ref(''), selected=ref(null), form=ref({}), busy=ref(false), error=ref('')
const items=ref([]), services=ref([]), movements=ref([]), partCategories=ref([])
const filters=reactive({q:'',category:'',low:false,...session.filters.parts})
const partFields={sku:'',name:'',category:'',compatible_device_category:'',quantity_in_stock:0,min_stock_level:1,cost_price:0,sale_price:0,spec_upgrade_target:'',spec_upgrade_value:''}
const serviceFields={code:'',name:'',category:'',default_price:0,estimated_hours:1,warranty_days:90}
let request=0
async function loadParts(){
  const seq=++request
  try{const data=await api('/warehouse/parts'+query(filters));if(seq===request){items.value=data;error.value=''}}
  catch(e){if(seq===request)error.value=e.message}
}
async function load(){
  await loadParts()
  try{
    const [all, prices, log]=await Promise.all([api('/warehouse/parts'),api('/warehouse/services'),session.admin?api('/warehouse/transactions'):[]])
    partCategories.value=[...new Set(all.map(item=>item.category))]
    services.value=prices;movements.value=log
  }catch(e){error.value=e.message}
}
onMounted(load)
watch(filters,()=>{session.filters.parts={...filters};loadParts()})
function open(kind,item=null){
  modal.value=kind;selected.value=item
  if(kind==='restock'){form.value={quantity:1};return}
  const fields=kind==='part'?partFields:serviceFields
  form.value=Object.fromEntries(Object.entries(fields).map(([key,initial])=>[key,item?.[key] ?? initial]))
  if(kind==='part' && item)delete form.value.quantity_in_stock
}
async function save(){
  busy.value=true
  try{
    const id=selected.value?.id
    const path=modal.value==='restock'?'/parts/'+id+'/restock':(modal.value==='part'?'/parts':'/services')+(id?'/'+id:'')
    const method=!id || modal.value==='restock'?'POST':modal.value==='part'?'PATCH':'PUT'
    await api('/warehouse'+path,{method,data:form.value})
    modal.value='';session.notify('Зміни збережено.');await load()
  }catch(e){session.notify(e.message,'error')}finally{busy.value=false}
}
</script>
<template>
  <div class="page-head"><div><div class="eyebrow"><Boxes :size="16"/> МАТЕРІАЛИ Й ПОСЛУГИ</div><h1>Склад і послуги</h1><p>Запчастини, складські рухи та прейскурант робіт.</p></div><button v-if="session.admin && tab!=='log'" class="button primary" @click="open(tab==='parts'?'part':'service')"><Plus :size="17"/> {{ tab==='parts'?'Нова запчастина':'Нова послуга' }}</button></div>
  <div class="tabs"><button v-for="[key,label] in [['parts','Запчастини'],['services','Прейскурант робіт'],...(session.admin?[['log','Історія руху']]:[])]" :key="key" class="tab" :class="{active:tab===key}" @click="tab=key">{{ label }}</button></div>
  <p v-if="error" class="error">{{ error }}</p>
  <section v-if="tab==='parts'" class="card">
    <div class="filters"><label class="input-icon"><Search :size="18"/><input v-model.trim="filters.q" aria-label="Пошук запчастин" placeholder="Назва або артикул"></label><select v-model="filters.category" aria-label="Категорія запчастин"><option value="">Усі категорії</option><option v-for="c in partCategories" :key="c">{{ c }}</option></select><label class="check"><input v-model="filters.low" type="checkbox"> Тільки критичний залишок</label></div>
    <div v-if="items.length" class="table-scroll"><table><thead><tr><th>Запчастина</th><th>Категорія</th><th>Залишок</th><th v-if="session.admin">Собівартість</th><th>Ціна</th><th v-if="session.admin">Дії</th></tr></thead><tbody><tr v-for="item in items" :key="item.id"><td><strong>{{ item.name }}</strong><small class="mono">{{ item.sku }}</small></td><td>{{ item.category }}</td><td><span class="status" :class="item.quantity_in_stock<=item.min_stock_level?'waiting_approval':'completed'">{{ item.quantity_in_stock }} шт.</span><small v-if="item.quantity_in_stock<=item.min_stock_level">Критичний залишок</small></td><td v-if="session.admin" class="mono nowrap">{{ money(item.cost_price) }}</td><td class="mono nowrap">{{ money(item.sale_price) }}</td><td v-if="session.admin"><div class="actions"><button class="icon-button" aria-label="Оприбуткувати" title="Оприбуткувати" @click="open('restock',item)"><PackagePlus :size="16"/></button><button class="icon-button" aria-label="Редагувати запчастину" @click="open('part',item)"><Pencil :size="16"/></button></div></td></tr></tbody></table></div><div v-else class="empty">Запчастин за вибраними фільтрами немає.</div>
  </section>
  <section v-else-if="tab==='services'" class="card"><div v-if="services.length" class="table-scroll"><table><thead><tr><th>Код</th><th>Послуга</th><th>Ціна</th><th>Тривалість, год</th><th>Гарантія, днів</th><th v-if="session.admin">Дія</th></tr></thead><tbody><tr v-for="item in services" :key="item.id"><td class="mono">{{ item.code }}</td><td>{{ item.name }}<small>{{ item.category }}</small></td><td class="mono nowrap">{{ money(item.default_price) }}</td><td>{{ item.estimated_hours }}</td><td>{{ item.warranty_days }}</td><td v-if="session.admin"><button class="icon-button" aria-label="Редагувати послугу" @click="open('service',item)"><Pencil :size="16"/></button></td></tr></tbody></table></div><div v-else class="empty">Послуг ще немає.</div></section>
  <section v-else class="card"><div v-if="movements.length" class="table-scroll"><table><thead><tr><th>Час</th><th>Запчастина</th><th>Зміна</th><th>Залишок після операції</th><th>Підстава</th><th>Працівник</th></tr></thead><tbody><tr v-for="item in movements" :key="item.id"><td>{{ dateTime(item.created_at) }}</td><td>{{ item.part_name }}</td><td class="mono">{{ item.change_amount>0?'+':'' }}{{ item.change_amount }}</td><td>{{ item.stock_after }}</td><td>{{ item.reason }}</td><td>{{ item.user_name }}</td></tr></tbody></table></div><div v-else class="empty">Операцій ще немає.</div></section>
  <Modal v-if="modal" :title="{restock:'Оприбуткування на склад',part:'Картка запчастини',service:'Картка послуги'}[modal]" @close="modal=''">
    <form class="form-grid" @submit.prevent="save">
      <template v-if="modal==='restock'"><p class="full">{{ selected.name }} · {{ selected.quantity_in_stock }} шт. на складі</p><label class="full">Кількість для оприбуткування<input v-model.number="form.quantity" type="number" min="1" max="100000" required></label></template>
      <template v-else-if="modal==='part'">
        <label>Артикул<input v-model.trim="form.sku" maxlength="60" required></label><label>Категорія запчастини<input v-model.trim="form.category" maxlength="60" required></label><label class="full">Назва<input v-model.trim="form.name" maxlength="160" required></label>
        <label class="full">Сумісна категорія пристроїв<select v-model="form.compatible_device_category"><option value="">Без обмеження</option><option v-for="c in categories" :key="c">{{ c }}</option></select></label>
        <label v-if="!selected">Початковий залишок<input v-model.number="form.quantity_in_stock" type="number" min="0" max="100000" required></label><label>Мінімальний залишок<input v-model.number="form.min_stock_level" type="number" min="0" max="100000" required></label>
        <label>Закупівельна ціна, грн<input v-model="form.cost_price" type="number" min="0" step=".01" required></label><label>Продажна ціна, грн<input v-model="form.sale_price" type="number" min="0" step=".01" required></label>
        <label>Оновлювана характеристика<select v-model="form.spec_upgrade_target"><option value="">Без зміни</option><option v-for="(name,key) in specLabels" :key="key" :value="key">{{ name }}</option></select></label><label v-if="form.spec_upgrade_target">Значення після заміни<input v-model.trim="form.spec_upgrade_value" maxlength="160" required></label>
      </template>
      <template v-else><label>Код<input v-model.trim="form.code" maxlength="32" required></label><label>Категорія<input v-model.trim="form.category" maxlength="60" required></label><label class="full">Назва<input v-model.trim="form.name" maxlength="160" required></label><label>Ціна, грн<input v-model="form.default_price" type="number" min="0" step=".01" required></label><label>Тривалість, год<input v-model="form.estimated_hours" type="number" min="0" step=".01" required></label><label>Гарантія, днів<input v-model.number="form.warranty_days" type="number" min="0" max="3650" required></label></template>
      <button class="button primary full" :disabled="busy">Зберегти</button>
    </form>
  </Modal>
</template>
