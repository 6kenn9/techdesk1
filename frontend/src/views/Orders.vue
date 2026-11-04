<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { Columns3, List, Plus, Search } from 'lucide-vue-next'
import { api, query } from '../api'
import { categories, date, money, statuses } from '../domain'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
const session = useSession()
const filters = reactive({ q:'', status:'', category:'', master_id:'', warranty_only:false, ...session.filters.orders })
const items=ref([]), masters=ref([]), error=ref(''), board=ref(false)
let request=0
async function load() {
  const seq=++request
  try { const result=await api('/orders'+query(filters)); if(seq===request){items.value=result;error.value=''} }
  catch(e){if(seq===request) error.value=e.message}
}
watch(filters, () => { session.filters.orders={...filters}; load() })
onMounted(async () => { load(); try{ masters.value=await api('/users?role=master') } catch(e){ error.value=e.message } })
</script>
<template>
  <div class="page-head"><div><div class="eyebrow">ОБЛІК СЕРВІСНИХ РОБІТ</div><h1>Журнал заявок</h1><p>Звернення клієнтів, етапи ремонту й відповідальні майстри.</p></div>
    <RouterLink class="button primary" to="/orders/new"><Plus :size="18"/> Нова заявка</RouterLink></div>
  <section class="card">
    <div class="section-head"><h2>Ремонтні замовлення <span class="chip">{{ items.length }}</span></h2><div class="actions"><button class="button small" :class="{primary:!board}" @click="board=false"><List :size="16"/> Таблиця</button><button class="button small" :class="{primary:board}" @click="board=true"><Columns3 :size="16"/> Дошка</button></div></div>
    <div class="filters">
      <label class="input-icon"><Search :size="18"/><input v-model.trim="filters.q" aria-label="Пошук заявок" placeholder="Номер, пристрій або клієнт"></label>
      <select v-model="filters.status" aria-label="Етап"><option value="">Усі етапи</option><option v-for="(name,key) in statuses" :key="key" :value="key">{{ name }}</option></select>
      <select v-model="filters.category" aria-label="Категорія пристрою"><option value="">Усі категорії</option><option v-for="item in categories" :key="item">{{ item }}</option></select>
      <select v-model="filters.master_id" aria-label="Майстер"><option value="">Усі майстри</option><option v-for="item in masters" :key="item.id" :value="item.id">{{ item.full_name }}</option></select>
      <label class="check"><input v-model="filters.warranty_only" type="checkbox"> Гарантійні</label>
      <button v-if="session.user.role==='master'" class="button small" @click="filters.master_id=filters.master_id===session.user.id?'':session.user.id">Мої заявки</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p><div v-else-if="!items.length" class="empty">Заявок за вибраними фільтрами немає.</div>
    <div v-else-if="board" class="kanban"><section v-for="(name,key) in statuses" :key="key" class="kanban-col"><h3>{{ name }}</h3><RouterLink v-for="item in items.filter(o=>o.status===key)" :key="item.id" :to="'/orders/'+item.id" class="kanban-item"><strong class="mono">{{ item.order_number }}</strong>{{ item.device }}<small>{{ item.master || 'Майстра не призначено' }}</small></RouterLink></section></div>
    <div v-else class="table-scroll"><table><thead><tr><th>Заявка</th><th>Пристрій</th><th>Клієнт</th><th>Етап</th><th>Майстер</th><th class="align-right">Сума</th></tr></thead>
      <tbody><tr v-for="item in items" :key="item.id"><td><RouterLink class="mono nowrap" :to="'/orders/'+item.id">{{ item.order_number }}</RouterLink><small>{{ date(item.created_at) }}</small></td><td><strong>{{ item.device }}</strong><small class="mono">{{ item.serial_number }}</small></td><td>{{ item.client }}</td><td><Stage :status="item.status"/><small v-if="item.is_warranty_case">Гарантійний випадок</small></td><td>{{ item.master || '—' }}</td><td class="align-right mono nowrap">{{ money(item.total_cost) }}</td></tr></tbody></table></div>
  </section>
</template>
