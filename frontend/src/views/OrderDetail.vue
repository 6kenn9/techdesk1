<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, Check, Download, Plus, Trash2, Wrench } from 'lucide-vue-next'
import { api, download } from '../api'
import { approvals, date, dateTime, money, specLabels, statuses } from '../domain'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
import Timeline from '../components/Timeline.vue'
import Modal from '../components/Modal.vue'

const id=useRoute().params.id, session=useSession(), base='/orders/'+id
const item=ref(null), error=ref(''), busy=ref(false), modal=ref(''), catalog=ref([]), inventory=ref([]), workers=ref([])
const edit=reactive({ diagnostics:'', internal_notes:'' })
const work=reactive({service_id:null,work_name:'',price:'',field:'',value:''})
const spare=reactive({part_id:null,quantity:1})
const approval=reactive({approved:true,comment:''})
const control=reactive({master_id:null,warranty_days:90,paid_amount:0})
const staffWrite=computed(()=>session.admin || (session.staff && (!item.value?.master_id || item.value.master_id===session.user.id)))
const draft=computed(()=>staffWrite.value && ['registered','diagnostics'].includes(item.value?.status))
const certificate=computed(()=>['ready_for_pickup','completed'].includes(item.value?.status))
const active=computed(()=>!['completed','cancelled'].includes(item.value?.status))
let refresh
const pending=computed(()=>item.value?.status==='waiting_approval' && item.value?.client_approval_status==='pending')
const next=computed(()=>{
  const transitions={registered:['diagnostics','Почати діагностику'],diagnostics:['waiting_approval','Надіслати кошторис'],in_repair:['ready_for_pickup','Готова до видачі'],ready_for_pickup:['completed','Завершити заявку']}
  if(item.value?.status==='waiting_approval' && item.value.client_approval_status==='approved') return ['in_repair','Почати ремонт']
  return transitions[item.value?.status]
})
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
function transition(status){ return action('/status','PATCH',{status},'Етап заявки оновлено.',status==='cancelled') }
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
    <div class="page-head"><div><div class="eyebrow">РЕМОНТНА ЗАЯВКА</div><h1 class="mono" style="font-size:2.15rem">{{ item.order_number }}</h1><p>{{ item.device }} · <span class="mono">{{ item.serial_number }}</span></p></div><Stage :status="item.status"/></div>
    <div class="stack">
      <section class="card"><div class="section-head"><h2>Хід ремонту</h2><span v-if="item.is_warranty_case" class="chip">Гарантійний випадок</span></div>
        <Timeline :status="item.status"/>
        <div v-if="staffWrite && active" class="actions" style="margin-top:16px">
          <button v-if="next" class="button primary" :disabled="busy" @click="transition(next[0])">{{ next[1] }}</button>
          <button v-if="item.status==='waiting_approval' && item.client_approval_status!=='approved'" class="button" :disabled="busy" @click="transition('diagnostics')">Уточнити кошторис</button>
          <button v-if="['registered','diagnostics','waiting_approval'].includes(item.status)" class="button danger" :disabled="busy" @click="modal='cancel'">Скасувати заявку</button>
        </div>
      </section>
      <div v-if="pending && !session.staff" class="alert warranty"><div><strong>Потрібне ваше рішення щодо кошторису</strong><p>Перегляньте роботи та деталі нижче. Після погодження майстер зможе виконати ремонт.</p><div class="actions" style="margin-top:9px"><button class="button primary" @click="approve(true)"><Check :size="17"/> Погодити вартість</button><button class="button danger" @click="approve(false)">Відхилити вартість</button></div></div></div>
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
          <section class="card"><div class="section-head"><h2>Історія етапів</h2></div><ul class="log"><li v-for="line in item.history" :key="line.id"><strong>{{ statuses[line.new_status] }}</strong><small>{{ dateTime(line.changed_at) }}</small><p v-if="line.comment">{{ line.comment }}</p></li></ul></section>
        </div>
        <aside class="stack">
          <section class="card"><div class="section-head"><h2>Кошторис</h2></div>
            <dl class="money-list"><div><dt>Вартість робіт</dt><dd>{{ money(item.works_total) }}</dd></div><div><dt>Вартість запчастин</dt><dd>{{ money(item.parts_total) }}</dd></div><div class="total"><dt>Підсумкова вартість</dt><dd>{{ money(item.total_cost) }}</dd></div><div v-if="certificate"><dt>Облікована оплата</dt><dd>{{ money(item.paid_amount) }}</dd></div></dl>
            <p style="margin-top:12px"><span class="chip">{{ approvals[item.client_approval_status] }}</span></p><p v-if="item.approved_at">Погоджено {{ dateTime(item.approved_at) }}</p>
            <p v-if="item.approval_comment && (session.staff || item.client_approval_status==='rejected')" class="wrap-text">{{ item.approval_comment }}</p>
            <div v-if="session.admin && pending" class="actions"><button class="button small" @click="approve(true)">Записати згоду</button><button class="button small danger" @click="approve(false)">Записати відмову</button></div>
          </section>
          <section id="warranty" class="card"><div class="section-head"><h2>Документи й гарантія</h2></div><div class="form-stack"><button class="button" @click="pdf('receipt')"><Download :size="17"/> Квитанція про приймання</button><button v-if="certificate" class="button" @click="pdf('warranty')"><Download :size="17"/> Талон та акт</button><small v-else>Гарантійний талон стане доступним після ремонту.</small><small v-if="item.warranty_expires_at">Гарантія до {{ date(item.warranty_expires_at) }}</small></div></section>
          <section v-if="session.staff" class="card"><div class="section-head"><h2>Керування</h2></div><div class="form-stack">
            <form v-if="session.admin && active" class="form-stack" @submit.prevent="action('','PUT',{master_id:control.master_id},'Призначення оновлено.')"><label>Майстер<select v-model="control.master_id"><option :value="null">Не призначено</option><option v-for="m in workers" :key="m.id" :value="m.id">{{ m.full_name }} · {{ m.active_orders }}</option></select></label><button class="button" :disabled="busy">Зберегти призначення</button></form>
            <button v-if="session.user.role==='master' && !item.master_id && active" class="button primary" :disabled="busy" @click="action('','PUT',{master_id:session.user.id},'Заявку закріплено за вами.')">Взяти заявку</button>
            <form v-if="staffWrite && active" class="form-stack" @submit.prevent="action('','PUT',{warranty_days:control.warranty_days},'Гарантійний строк оновлено.')"><label>Гарантійний строк, днів<input v-model.number="control.warranty_days" type="number" min="0" max="3650" required></label><button class="button" :disabled="busy">Зберегти строк</button></form>
            <form v-if="staffWrite && certificate" class="form-stack" @submit.prevent="action('','PUT',{paid_amount:control.paid_amount},'Оплату обліковано.')"><label>Отримана оплата, грн<input v-model="control.paid_amount" type="number" min="0" :max="item.total_cost" step=".01" required></label><button class="button" :disabled="busy">Зберегти оплату</button></form>
          </div></section>
        </aside>
      </div>
    </div>
    <Modal v-if="modal==='cancel'" title="Скасувати заявку?" @close="modal=''"><p>Зарезервовані запчастини буде повернено на склад.</p><button class="button danger" :disabled="busy" @click="transition('cancelled')">Підтвердити скасування</button></Modal>
    <Modal v-if="modal==='approval'" :title="approval.approved?'Погодження кошторису':'Відхилення кошторису'" @close="modal=''"><form class="form-stack" @submit.prevent="submitApproval">
      <p>Підсумкова вартість: <strong class="mono">{{ money(item.total_cost) }}</strong></p><label v-if="session.admin || !approval.approved">{{ session.admin?'Як отримано рішення клієнта':'Коментар до відмови' }}<textarea v-model.trim="approval.comment" :required="session.admin" maxlength="4000"></textarea></label><button class="button" :class="approval.approved?'primary':'danger'" :disabled="busy">Підтвердити рішення</button></form></Modal>
  </template>
</template>
