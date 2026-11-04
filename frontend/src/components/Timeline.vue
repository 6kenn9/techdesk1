<script setup>
import { Check } from 'lucide-vue-next'
import { stages } from '../domain'
defineProps({ status: String })
const shortLabels = ['Приймання', 'Діагностика', 'Кошторис', 'Ремонт', 'Видача', 'Завершення']
</script>
<template>
  <ol v-if="status !== 'cancelled'" class="timeline" aria-label="Етапи ремонту">
    <li v-for="([value, label], i) in stages" :key="value" :class="{ done: i < stages.findIndex(s => s[0] === status), current: value === status }">
      <span><Check v-if="i < stages.findIndex(s => s[0] === status)" :size="16"/><template v-else>{{ i + 1 }}</template></span><small class="stage-full">{{ label }}</small><small class="stage-short" :title="label">{{ shortLabels[i] }}</small>
    </li>
  </ol>
  <div v-else class="alert">Заявку скасовано. Ремонт не виконано.</div>
</template>
