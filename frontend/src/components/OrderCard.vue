<script setup>
import { computed } from 'vue'
import { Clock, Flame, ShieldCheck } from 'lucide-vue-next'
import { ageLabel, daysSince, money, STALE_DAYS } from '../domain'
const props = defineProps({ item: { type: Object, required: true }, showMaster: Boolean, showClient: Boolean })
const stale = computed(() => !['completed', 'cancelled'].includes(props.item.status) && daysSince(props.item.stage_since) >= STALE_DAYS)
</script>
<template>
  <RouterLink :to="'/orders/' + item.id" class="order-card" :class="{ urgent: item.priority === 'urgent' }">
    <div class="order-card-top"><strong class="mono">{{ item.order_number }}</strong>
      <span v-if="!['completed', 'cancelled'].includes(item.status)" class="age" :class="{ stale }" :title="'На етапі ' + ageLabel(item.stage_since)"><Clock :size="12"/>{{ ageLabel(item.stage_since) }}</span></div>
    <span class="order-card-device">{{ item.device }}</span>
    <small v-if="showClient">{{ item.client }}</small>
    <small v-if="showMaster" :class="{ unassigned: !item.master }">{{ item.master || 'Майстра не призначено' }}</small>
    <div v-if="item.priority === 'urgent' || item.is_warranty_case || item.client_approval_status === 'rejected' || Number(item.total_cost)" class="order-card-tags">
      <span v-if="item.priority === 'urgent'" class="tag danger"><Flame :size="12"/>Терміново</span>
      <span v-if="item.client_approval_status === 'rejected' && item.status === 'waiting_approval'" class="tag danger">Кошторис відхилено</span>
      <span v-if="item.is_warranty_case" class="tag ok"><ShieldCheck :size="12"/>Гарантія</span>
      <span v-if="Number(item.total_cost)" class="tag mono">{{ money(item.total_cost) }}</span>
    </div>
  </RouterLink>
</template>
