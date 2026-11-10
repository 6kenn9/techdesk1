<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, BadgeCheck, Check, CircleDollarSign, CircleX, Download, Inbox, PackageCheck, Plus, Search, Store, Trash2, Truck, Wrench } from 'lucide-vue-next'
import { api, download } from '../api'
import { ageLabel, approvals, date, dateTime, money, specLabels, statuses } from '../domain'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
import Timeline from '../components/Timeline.vue'
import Modal from '../components/Modal.vue'
import PhotoGallery from '../components/PhotoGallery.vue'
import DeliveryFields from '../components/DeliveryFields.vue'
import StarRating from '../components/StarRating.vue'

const id=useRoute().params.id, session=useSession(), base='/orders/'+id
const item=ref(null), error=ref(''), busy=ref(false), modal=ref(''), catalog=ref([]), inventory=ref([]), workers=ref([])
const edit=reactive({ diagnostics:'', internal_notes:'' })
const work=reactive({service_id:null,work_name:'',price:'',field:'',value:''})
const spare=reactive({part_id:null,quantity:1})
const approval=reactive({approved:true,comment:''})
const control=reactive({master_id:null,warranty_days:90,paid_amount:0})
const cancelReason=ref('')
const payment=reactive({amount:0,method:'cash',note:''})
const methods={cash:'Готівка',card:'Картка',transfer:'Переказ'}
const deliveryForm=ref({method:'pickup',city:'',branch:''}), ttn=ref('')
const review=reactive({rating:0,comment:''})
const shipping=computed(()=>item.value?.delivery_method==='nova_poshta')
const canChangeDelivery=computed(()=>active.value && !item.value?.delivery_ttn && (!session.staff || staffWrite.value))
const tracking=computed(()=>'https://novaposhta.ua/tracking/?cargo_number='+item.value?.delivery_ttn)
function openDelivery(){deliveryForm.value={method:item.value.delivery_method,city:item.value.delivery_city,branch:item.value.delivery_branch};modal.value='delivery'}
function openShip(){ttn.value='';modal.value='ship'}
async function rate(){ if(await action('/rating','POST',{rating:review.rating,comment:review.comment},'Дякуємо за оцінку!')) Object.assign(review,{rating:0,comment:''}) }
function openPayment(){payment.amount=Number(due.value.toFixed(2));payment.method='cash';payment.note='';modal.value='payment'}
async function clientCancel(){ if(await action('/cancel','POST',{comment:cancelReason.value},'Заявку скасовано.')) cancelReason.value='' }
const staffWrite=computed(()=>session.admin || (session.staff && (!item.value?.master_id || item.value.master_id===session.user.id)))
const draft=computed(()=>staffWrite.value && ['registered','diagnostics'].includes(item.value?.status))
const certificate=computed(()=>['ready_for_pickup','completed'].includes(item.value?.status))
const active=computed(()=>!['completed','cancelled'].includes(item.value?.status))
let refresh
const pending=computed(()=>item.value?.status==='waiting_approval' && item.value?.client_approval_status==='pending')
const selectedPart=computed(()=>inventory.value.find(part=>part.id===spare.part_id))
function assign(data, sync=true){
  item.value=data
  if(sync){edit.diagnostics=data.diagnostics;edit.internal_notes=data.internal_notes || '';control.master_id=data.master_id;control.warranty_days=data.warranty_days;control.paid_amount=data.paid_amount}
}
async function loadStock(){inventory.value=await api('/warehouse/parts')}
onMounted(async()=>{
  try{
    assign(await api(base))
    if(session.staff){
      const [services, people]=await Promise.all([api('/warehouse/services'),api('/users?role=master'),loadStock()])
      catalog.value=services; workers.value=people.filter(person=>person.is_active)
    } else {
      refresh=setInterval(async () => {
        if (busy.value || modal.value || document.hidden) return
        try {
          const current = await api(base)
          if (!busy.value && !modal.value) assign(current)
        } catch(e) { error.value=e.message }
      }, 15000)
    }
  }catch(e){error.value=e.message}
})
onUnmounted(() => clearInterval(refresh))
async function action(path, method, data, message, refreshStock=false){
  if(busy.value)return
  busy.value=true;error.value=''
  try {
    assign(await api(base+path,{method,data}), path==='' || path==='/status')
    modal.value=''
    if(refreshStock)await loadStock()
    if(message)session.notify(message)
    return true
  } catch(e){error.value=e.message;session.notify(e.message,'error');return false} finally{busy.value=false}
}
function transition(status, comment=''){ return action('/status','PATCH',{status,comment},'Етап заявки оновлено.',status==='cancelled') }
const due=computed(()=>Number(item.value?.total_cost||0)-Number(item.value?.paid_amount||0))
function since(value){ const age=ageLabel(value); return age==='сьогодні' ? 'сьогодні' : age+' тому' }
// Підказка «що робити далі» для працівника: одна головна дія замість набору рівноцінних кнопок.
const guide=computed(()=>{
  const o=item.value
  if(!o || !session.staff) return null
  const can=staffWrite.value
  const cancel={label:'Скасувати заявку',kind:'danger',run:()=>{cancelReason.value='';modal.value='cancel'}}
  const only=list=>can?list:[]
  switch(o.status){
    case 'registered':
      if(!o.master_id) return session.admin
        ? {title:'Призначте майстра',text:'Без відповідального майстра діагностику не почати. Оберіть його в блоці «Керування».',tone:'warn',actions:[cancel]}
        : {title:'Заявка вільна',text:'Візьміть її, щоб почати діагностику.',actions:[{label:'Взяти заявку',kind:'primary',run:()=>action('','PUT',{master_id:session.user.id},'Заявку закріплено за вами.')}]}
      return {title:'Почніть діагностику',text:'Огляньте пристрій і сфотографуйте зовнішній стан.',actions:only([{label:'Почати діагностику',kind:'primary',run:()=>transition('diagnostics')},cancel])}
    case 'diagnostics':
      return {title:'Складіть кошторис',text:o.diagnostics?`Робіт: ${o.works.length}, запчастин: ${o.parts.length}, разом ${money(o.total_cost)}. Коли все готово, надішліть клієнту.`:'Внесіть висновок діагностики, додайте роботи й запчастини.',
        actions:only([{label:'Надіслати кошторис клієнту',kind:'primary',run:()=>transition('waiting_approval'),disabled:!o.diagnostics},cancel])}
    case 'waiting_approval':
      if(o.client_approval_status==='rejected') return {title:'Клієнт відхилив кошторис',text:o.approval_comment||'Зв’яжіться з клієнтом і уточніть перелік робіт.',tone:'danger',actions:only([{label:'Уточнити кошторис',kind:'primary',run:()=>transition('diagnostics')},cancel])}
      return {title:'Очікуємо рішення клієнта',text:`Кошторис на ${money(o.total_cost)} надіслано ${since(o.stage_since)}.`,tone:'wait',
        actions:[...(session.admin?[{label:'Записати згоду',kind:'primary',run:()=>approve(true)},{label:'Записати відмову',run:()=>approve(false)}]:[]),...only([{label:'Уточнити кошторис',run:()=>transition('diagnostics')},cancel])]}
    case 'in_repair':
      return {title:'Виконайте ремонт',text:'Після перевірки позначте пристрій готовим — клієнт отримає сповіщення.',actions:only([{label:'Готово до видачі',kind:'primary',run:()=>transition('ready_for_pickup')},cancel])}
    case 'ready_for_pickup':
      if(due.value>0) return {title:'Прийміть оплату',text:`До сплати ${money(due.value)}. Після оплати заявку можна ${o.delivery_method==='nova_poshta'?'відправити Новою Поштою':'завершити'}.`,tone:'warn',actions:only([{label:`Прийняти оплату ${money(due.value)}`,kind:'primary',run:openPayment}])}
      if(o.delivery_method==='nova_poshta' && !o.delivery_ttn) return {title:'Відправте Новою Поштою',text:`${o.delivery_city}, ${o.delivery_branch}. Оформіть накладну й внесіть її номер — клієнт отримає його в Telegram.`,tone:'warn',actions:only([{label:'Внести номер накладної',kind:'primary',run:openShip}])}
      if(o.delivery_method==='nova_poshta') return {title:'Пристрій відправлено',text:`ТТН ${o.delivery_ttn}. Завершіть заявку — почнеться гарантійний строк.`,tone:'ok',actions:only([{label:'Завершити заявку',kind:'primary',run:()=>transition('completed')}])}
      return {title:'Видайте пристрій',text:'Оплату отримано. Завершіть заявку — почнеться гарантійний строк.',tone:'ok',actions:only([{label:'Завершити й видати',kind:'primary',run:()=>transition('completed')}])}
  }
  return null
})
// Пояснення стану ремонту для клієнта простими словами.
const hero=computed(()=>{
  const o=item.value
  if(!o) return null
  const map={
    registered:[Inbox,'Пристрій прийнято','Заявку зареєстровано. Найближчим часом майстер почне діагностику.',''],
    diagnostics:[Search,'Йде діагностика','Майстер шукає причину несправності. Потім ви отримаєте кошторис на погодження.',''],
    waiting_approval:o.client_approval_status==='rejected'
      ?[CircleX,'Кошторис відхилено','Майстер уточнить перелік робіт і зв’яжеться з вами.','danger']
      :[CircleDollarSign,'Потрібне ваше рішення',`Ремонт коштуватиме ${money(o.total_cost)}. Без вашої згоди роботи не почнуться.`,'warn'],
    in_repair:[Wrench,'Ремонт триває','Майстер виконує погоджені роботи. Ми повідомимо, щойно все буде готово.',''],
    ready_for_pickup:o.delivery_method==='nova_poshta'
      ?(o.delivery_ttn?[Truck,'Пристрій у дорозі',`Відправлено Новою Поштою, накладна ${o.delivery_ttn}.`,'ok']
        :[Truck,'Готуємо відправку',due.value>0?`Після оплати ${money(due.value)} відправимо пристрій у ${o.delivery_city}, ${o.delivery_branch}.`:`Оплату отримано. Найближчим часом відправимо пристрій у ${o.delivery_city}.`,'ok'])
      :[PackageCheck,'Можна забирати!',due.value>0?`До сплати ${money(due.value)}. Назвіть номер заявки на видачі.`:'Оплату отримано. Назвіть номер заявки на видачі.','ok'],
    completed:[BadgeCheck,'Ремонт завершено',o.warranty_expires_at?`Гарантія діє до ${date(o.warranty_expires_at).replace(/\.$/,'')}.`:'Дякуємо, що обрали TechDesk.','ok'],
    cancelled:[CircleX,'Заявку скасовано','Ремонт не виконувався. Якщо маєте питання — зверніться до сервісного центру.','muted'],
  }
  const [icon,title,text,tone]=map[o.status]
  return {icon,title,text,tone}
})
const estimateLines=computed(()=>item.value?[...item.value.works.map(w=>({id:'w'+w.id,name:w.work_name,meta:'Робота',sum:w.price})),...item.value.parts.map(p=>({id:'p'+p.id,name:p.part_name,meta:`Запчастина · ${p.quantity} шт.`,sum:p.total_sale_price}))]:[])
async function toggleWarranty(event){
  if(!await action('','PUT',{is_warranty_case:event.target.checked},'Ознаку гарантійного випадку оновлено.')) event.target.checked=item.value.is_warranty_case
}
function approve(value){approval.approved=value;approval.comment='';modal.value='approval'}
function submitApproval(){
  return action('/approve-cost','POST',{...approval,expected_total:item.value.total_cost,estimate_version:item.value.estimate_version},approval.approved?'Кошторис погоджено.':'Кошторис відхилено.')
}
async function addWork(){
  const data={service_id:work.service_id,work_name:work.work_name || null,price:work.price===''?null:work.price,
    updates_passport_spec:work.field && work.value ? {[work.field]:work.value} : {}}
  if(await action('/works','POST',data,'Роботу додано.'))Object.assign(work,{service_id:null,work_name:'',price:'',field:'',value:''})
}
async function addPart(){
  if(await action('/parts','POST',{...spare},'Деталь зарезервовано зі складу.',true))Object.assign(spare,{part_id:null,quantity:1})
}
async function pdf(kind){
  try{await download(base+'/pdf/'+kind,item.value.order_number+(kind==='receipt'?'-квитанція.pdf':'-гарантія.pdf'))}
  catch(e){session.notify(e.message,'error')}
}
async function upgrade(line){
  try{await api('/passports/'+item.value.device_id+'/upgrade-spec',{method:'POST',data:{
    order_id:item.value.id,field_name:line.spec_upgrade_target,new_value:line.spec_upgrade_value,change_reason:line.part_name,
  }});session.notify('Характеристику оновлено в паспорті.')}
  catch(e){session.notify(e.message,'error')}
}
</script>

<template>
  <RouterLink :to="session.staff?'/orders':'/my-cabinet'" class="back"><ArrowLeft :size="16"/> До переліку заявок</RouterLink>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <template v-if="item">
    <div class="page-head"><div class="page-title"><h1 class="mono">{{ item.order_number }}</h1><span class="record-meta">{{ item.device }} · <span class="mono">{{ item.serial_number || 'S/N не вказано' }}</span></span></div><Stage :status="item.status"/></div>
    <div class="stack">
      <section v-if="guide" class="next-step" :class="guide.tone">
        <div><small>Наступний крок</small><strong>{{ guide.title }}</strong><p>{{ guide.text }}</p></div>
        <div v-if="guide.actions.length" class="actions"><button v-for="b in guide.actions" :key="b.label" class="button" :class="b.kind" :disabled="busy || b.disabled" @click="b.run()">{{ b.label }}</button></div>
      </section>
      <section v-if="!session.staff" class="status-hero" :class="hero.tone">
        <span class="status-hero-icon"><component :is="hero.icon" :size="26"/></span>
        <div class="status-hero-body"><h2>{{ hero.title }}</h2><p>{{ hero.text }}</p>
          <dl class="hero-meta"><div><dt>Майстер</dt><dd>{{ item.master || 'буде призначено' }}</dd></div><div><dt>На цьому етапі</dt><dd>{{ ageLabel(item.stage_since) }}</dd></div><div><dt>Прийнято</dt><dd>{{ date(item.created_at) }}</dd></div></dl>
          <div v-if="item.status==='registered'" class="actions"><button class="button large" @click="cancelReason='';modal='client-cancel'"><CircleX :size="18"/> Скасувати заявку</button></div>
          <div v-if="pending" class="actions"><button class="button primary large" @click="approve(true)"><Check :size="18"/> Погодити {{ money(item.total_cost) }}</button><button class="button large" @click="approve(false)">Відхилити</button></div>
        </div>
      </section>
      <section class="card"><div class="section-head"><h2>Хід ремонту</h2><span v-if="item.is_warranty_case" class="chip">Гарантійний випадок</span></div>
        <Timeline :status="item.status"/>
      </section>
      <section v-if="item.status==='completed' && (item.rating || !session.staff)" class="card rating-card">
        <template v-if="item.rating">
          <div class="section-head"><h2>{{ session.staff ? 'Оцінка клієнта' : 'Ваша оцінка' }}</h2><small class="muted">{{ dateTime(item.rated_at) }}</small></div>
          <StarRating :model-value="item.rating" readonly/>
          <p v-if="item.rating_comment" class="quote wrap-text">{{ item.rating_comment }}</p>
        </template>
        <form v-else class="form-stack" @submit.prevent="rate">
          <div class="section-head"><h2>Як вам ремонт?</h2></div>
          <p class="muted">Оцінка допомагає нам працювати краще. Її бачать адміністратор і ваш майстер.</p>
          <StarRating v-model="review.rating"/>
          <label v-if="review.rating">Коментар (необов’язково)<textarea v-model.trim="review.comment" maxlength="1000" rows="2" :placeholder="review.rating<4?'Що нам варто покращити?':'Що сподобалось?'"></textarea></label>
          <div><button class="button primary" :disabled="busy || !review.rating">Надіслати оцінку</button></div>
        </form>
      </section>
      <div class="cols">
        <div class="stack">
          <section class="card">
            <div class="section-head"><h2>Приймання та діагностика</h2><RouterLink class="button small" :to="'/passports/'+item.device_id">Паспорт <ArrowUpRight :size="15"/></RouterLink></div>
            <dl class="specs"><div><dt>Клієнт</dt><dd>{{ item.client }}</dd></div><div><dt>Відповідальний майстер</dt><dd>{{ item.master || 'Не призначено' }}</dd></div><div><dt>Комплектація</dt><dd>{{ item.completeness || 'Не зазначено' }}</dd></div><div><dt>Пріоритет</dt><dd>{{ item.priority==='urgent'?'Терміновий':'Звичайний' }}</dd></div></dl>
            <h3>Опис несправності</h3><p class="wrap-text">{{ item.problem_description }}</p><p v-if="item.cosmetic_notes" class="wrap-text">Зовнішній стан: {{ item.cosmetic_notes }}</p>
            <form v-if="draft" class="form-stack" @submit.prevent="action('','PUT',{...edit},'Дані діагностики збережено.')">
              <label>Висновок діагностики<textarea v-model.trim="edit.diagnostics" maxlength="4000"></textarea></label><label>Внутрішні примітки<textarea v-model.trim="edit.internal_notes" maxlength="4000"></textarea></label><div><button class="button" :disabled="busy">Зберегти діагностику</button></div>
            </form>
            <div v-else><h3>Висновок діагностики</h3><p class="wrap-text">{{ item.diagnostics || 'Діагностику ще не внесено.' }}</p><p v-if="item.internal_notes" class="wrap-text">Внутрішні примітки: {{ item.internal_notes }}</p></div>
          </section>
          <section v-if="!session.staff" class="card"><div class="section-head"><h2>Що входить у кошторис</h2><span class="chip">{{ estimateLines.length }}</span></div>
            <ul v-if="estimateLines.length" class="estimate-lines"><li v-for="line in estimateLines" :key="line.id"><div><strong>{{ line.name }}</strong><small>{{ line.meta }}</small></div><span class="mono nowrap">{{ money(line.sum) }}</span></li>
              <li class="total"><strong>Разом</strong><span class="mono nowrap">{{ money(item.total_cost) }}</span></li></ul>
            <p v-else>Кошторис з’явиться після діагностики.</p>
          </section>
          <template v-if="session.staff">
          <section class="card">
            <div class="section-head"><h2>Роботи</h2><span class="chip">{{ item.works.length }}</span></div>
            <div v-if="item.works.length" class="table-scroll"><table class="compact"><thead><tr><th>Робота</th><th>Вартість</th><th v-if="draft">Дія</th></tr></thead><tbody><tr v-for="line in item.works" :key="line.id"><td>{{ line.work_name }}</td><td class="mono nowrap">{{ money(line.price) }}</td><td v-if="draft"><button class="icon-button" aria-label="Видалити роботу" :disabled="busy" @click="action('/works/'+line.id,'DELETE',undefined,'Роботу видалено.')"><Trash2 :size="16"/></button></td></tr></tbody></table></div><p v-else>Роботи ще не додано.</p>
            <form v-if="draft" class="form-grid" style="margin-top:13px" @submit.prevent="addWork">
              <label class="full">Робота з прейскуранта<select v-model="work.service_id"><option :value="null">Ввести роботу вручну</option><option v-for="s in catalog" :key="s.id" :value="s.id">{{ s.name }} · {{ money(s.default_price) }}</option></select></label>
              <label>Назва роботи<input v-model.trim="work.work_name" :required="!work.service_id" maxlength="160"></label><label>Власна ціна<input v-model="work.price" type="number" min="0" step=".01" :required="!work.service_id"></label>
              <label>Зміна в паспорті<select v-model="work.field"><option value="">Без зміни</option><option v-for="(label,key) in specLabels" :key="key" :value="key">{{ label }}</option></select></label><label v-if="work.field">Нове значення<input v-model.trim="work.value" required maxlength="160"></label>
              <div class="full"><button class="button" :disabled="busy"><Plus :size="17"/> Додати роботу</button></div>
            </form>
          </section>
          <section class="card">
            <div class="section-head"><h2>Запчастини</h2><span class="chip">{{ item.parts.length }}</span></div>
            <div v-if="item.parts.length" class="table-scroll"><table class="compact"><thead><tr><th>Запчастина</th><th>Кількість</th><th>Сума</th><th v-if="staffWrite">Дія</th></tr></thead><tbody><tr v-for="line in item.parts" :key="line.id"><td>{{ line.part_name }}</td><td>{{ line.quantity }}</td><td class="mono nowrap">{{ money(line.total_sale_price) }}</td><td v-if="staffWrite">
              <button v-if="draft" class="icon-button" aria-label="Повернути запчастину" :disabled="busy" @click="action('/parts/'+line.id,'DELETE',undefined,'Деталь повернено на склад.',true)"><Trash2 :size="16"/></button>
              <button v-else-if="item.status==='in_repair' && line.spec_upgrade_target" class="button small" @click="upgrade(line)"><Wrench :size="15"/> Оновити паспорт</button>
            </td></tr></tbody></table></div><p v-else>Запчастини ще не додано.</p>
            <form v-if="draft" class="form-grid" style="margin-top:13px" @submit.prevent="addPart"><label>Запчастина<select v-model="spare.part_id" required><option :value="null">Оберіть позицію</option><option v-for="p in inventory" :key="p.id" :value="p.id" :disabled="!p.quantity_in_stock">{{ p.name }} · {{ p.quantity_in_stock }} шт.</option></select></label>
              <label>Кількість<input v-model.number="spare.quantity" type="number" min="1" :max="selectedPart?.quantity_in_stock" required></label><div class="full"><button class="button" :disabled="busy"><Plus :size="17"/> Додати зі складу</button></div></form>
          </section>
          </template>
          <PhotoGallery framed title="Фото пристрою" :device-id="item.device_id" :order-id="item.id" :can-upload="staffWrite && active"/>
          <section class="card"><div class="section-head"><h2>Історія етапів</h2></div><ul class="log"><li v-for="line in item.history" :key="line.id"><strong>{{ statuses[line.new_status] }}</strong><small>{{ dateTime(line.changed_at) }}</small><p v-if="line.comment">{{ line.comment }}</p></li></ul></section>
        </div>
        <aside class="stack">
          <section class="card"><div class="section-head"><h2>Кошторис</h2></div>
            <dl class="money-list"><div><dt>Вартість робіт</dt><dd>{{ money(item.works_total) }}</dd></div><div><dt>Вартість запчастин</dt><dd>{{ money(item.parts_total) }}</dd></div><div v-if="item.is_warranty_case"><dt>Покривається гарантією</dt><dd>−{{ money(Number(item.works_total)+Number(item.parts_total)) }}</dd></div><div class="total"><dt>Підсумкова вартість</dt><dd>{{ money(item.total_cost) }}</dd></div><div v-if="certificate"><dt>Облікована оплата</dt><dd>{{ money(item.paid_amount) }}</dd></div><div v-if="certificate && due>0" class="due"><dt>Залишок до сплати</dt><dd>{{ money(due) }}</dd></div></dl>
            <ul v-if="item.payments?.length" class="payments"><li v-for="p in item.payments" :key="p.id"><span>{{ methods[p.method] }}<small>{{ dateTime(p.created_at) }}{{ p.note ? ' · ' + p.note : '' }}</small></span><strong>{{ money(p.amount) }}</strong></li></ul>
            <p style="margin-top:12px"><span class="chip">{{ approvals[item.client_approval_status] }}</span></p><p v-if="item.approved_at">Погоджено {{ dateTime(item.approved_at) }}</p>
            <p v-if="item.approval_comment && (session.staff || item.client_approval_status==='rejected')" class="wrap-text">{{ item.approval_comment }}</p>
          </section>
          <section class="card"><div class="section-head"><h2>Отримання пристрою</h2><button v-if="canChangeDelivery" class="button small" @click="openDelivery">Змінити</button></div>
            <p v-if="!shipping" class="icon-line"><Store :size="18"/> Самовивіз із сервісного центру</p>
            <template v-else>
              <p class="icon-line"><Truck :size="18"/> Нова Пошта</p>
              <dl class="specs"><div><dt>Місто</dt><dd>{{ item.delivery_city }}</dd></div><div><dt>Відділення</dt><dd>{{ item.delivery_branch }}</dd></div>
                <div v-if="item.delivery_ttn"><dt>Накладна</dt><dd><a class="ttn" :href="tracking" target="_blank" rel="noopener">{{ item.delivery_ttn }}</a></dd></div></dl>
              <button v-if="staffWrite && item.status==='ready_for_pickup' && !item.delivery_ttn && due<=0" class="button" style="margin-top:10px" :disabled="busy" @click="openShip"><Truck :size="17"/> Внести номер накладної</button>
            </template>
          </section>
          <section id="warranty" class="card"><div class="section-head"><h2>Документи й гарантія</h2></div><div class="form-stack"><button class="button" @click="pdf('receipt')"><Download :size="17"/> Квитанція про приймання</button><button v-if="certificate" class="button" @click="pdf('warranty')"><Download :size="17"/> Талон та акт</button><small v-else>Гарантійний талон стане доступним після ремонту.</small><small v-if="item.warranty_expires_at">Гарантія до {{ date(item.warranty_expires_at) }}</small></div></section>
          <section v-if="session.staff" class="card"><div class="section-head"><h2>Керування</h2></div><div class="form-stack">
            <label v-if="draft" class="check"><input type="checkbox" :checked="item.is_warranty_case" :disabled="busy" @change="toggleWarranty"> Гарантійний випадок (безкоштовно для клієнта)</label>
            <form v-if="session.admin && active" class="form-stack" @submit.prevent="action('','PUT',{master_id:control.master_id},'Призначення оновлено.')"><label>Майстер<select v-model="control.master_id"><option :value="null">Не призначено</option><option v-for="m in workers" :key="m.id" :value="m.id">{{ m.full_name }} · {{ m.active_orders }}</option></select></label><button class="button" :disabled="busy">Зберегти призначення</button></form>
            <form v-if="staffWrite && active" class="form-stack" @submit.prevent="action('','PUT',{warranty_days:control.warranty_days},'Гарантійний строк оновлено.')"><label>Гарантійний строк, днів<input v-model.number="control.warranty_days" type="number" min="0" max="3650" required></label><button class="button" :disabled="busy">Зберегти строк</button></form>
            <button v-if="staffWrite && item.status==='ready_for_pickup' && due>0" class="button" :disabled="busy" @click="openPayment"><CircleDollarSign :size="17"/> Прийняти оплату</button>
          </div></section>
        </aside>
      </div>
    </div>
    <Modal v-if="modal==='payment'" title="Прийняти оплату" @close="modal=''"><form class="form-stack" @submit.prevent="action('/payments','POST',{amount:payment.amount,method:payment.method,note:payment.note},'Оплату обліковано.')">
      <p>До сплати: <strong>{{ money(due) }}</strong>. Можна прийняти частину, а решту — іншим способом.</p>
      <fieldset class="tile-group"><legend>Спосіб оплати</legend><div class="segmented pay-methods"><button v-for="(label,key) in methods" :key="key" type="button" class="button small" :aria-pressed="payment.method===key" @click="payment.method=key">{{ label }}</button></div></fieldset>
      <label>Сума, грн<input v-model.number="payment.amount" type="number" min="0.01" :max="due" step=".01" required></label>
      <label>Примітка<input v-model.trim="payment.note" maxlength="200" placeholder="Необов’язково: номер чека, термінал…"></label>
      <button class="button primary" :disabled="busy">Зберегти оплату</button></form></Modal>
    <Modal v-if="modal==='delivery'" title="Спосіб отримання" @close="modal=''"><form class="form-stack" @submit.prevent="action('/delivery','PUT',deliveryForm,'Спосіб отримання оновлено.')"><DeliveryFields v-model="deliveryForm"/><button class="button primary" :disabled="busy">Зберегти</button></form></Modal>
    <Modal v-if="modal==='ship'" title="Відправка Новою Поштою" @close="modal=''"><form class="form-stack" @submit.prevent="action('/shipment','POST',{ttn},'Накладну збережено, клієнта сповіщено.')">
      <p>Отримувач: <strong>{{ item.client }}</strong><br>{{ item.delivery_city }}, {{ item.delivery_branch }}</p>
      <label>Номер експрес-накладної (ТТН)<input v-model.trim="ttn" class="ttn" required inputmode="numeric" pattern="[0-9 ]{14,17}" maxlength="17" placeholder="20 4500 0000 0001"></label>
      <button class="button primary" :disabled="busy">Зберегти та сповістити клієнта</button></form></Modal>
    <Modal v-if="modal==='client-cancel'" title="Скасувати заявку?" @close="modal=''"><form class="form-stack" @submit.prevent="clientCancel"><p>Пристрій ще не взяли в роботу, тож заявку можна скасувати. Якщо ви вже передали пристрій у центр, заберіть його за номером заявки.</p><label>Причина (необов’язково)<textarea v-model.trim="cancelReason" maxlength="1000" placeholder="Наприклад: проблема зникла"></textarea></label><button class="button danger" :disabled="busy">Скасувати заявку</button></form></Modal>
    <Modal v-if="modal==='cancel'" title="Скасувати заявку?" @close="modal=''"><form class="form-stack" @submit.prevent="transition('cancelled',cancelReason)"><p>Зарезервовані запчастини буде повернено на склад.</p><label>Причина скасування<textarea v-model.trim="cancelReason" :required="item.status==='in_repair'" maxlength="4000"></textarea></label><button class="button danger" :disabled="busy">Підтвердити скасування</button></form></Modal>
    <Modal v-if="modal==='approval'" :title="approval.approved?'Погодження кошторису':'Відхилення кошторису'" @close="modal=''"><form class="form-stack" @submit.prevent="submitApproval">
      <p>Підсумкова вартість: <strong class="mono">{{ money(item.total_cost) }}</strong></p><label v-if="session.admin || !approval.approved">{{ session.admin?'Як отримано рішення клієнта':'Коментар до відмови' }}<textarea v-model.trim="approval.comment" :required="session.admin" maxlength="4000"></textarea></label><button class="button" :class="approval.approved?'primary':'danger'" :disabled="busy">Підтвердити рішення</button></form></Modal>
  </template>
</template>
