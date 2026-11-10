<script setup>
import { Check } from 'lucide-vue-next'
import { stages, statuses } from '../domain'
const shortLabels = ['Приймання', 'Діагностика', 'Кошторис', 'Ремонт', 'Видача', 'Завершення']
const props = defineProps({ status: String })
// Завершена заявка: усі етапи пройдено, тому всі позначені галочкою.
const position = () => (props.status === 'completed' ? stages.length : stages.findIndex(s => s[0] === props.status))
</script>
<template>
  <ol v-if="status !== 'cancelled'" class="timeline" aria-label="Етапи ремонту">
    <li v-for="([value, label], i) in stages" :key="value" :class="{ done: i < position(), current: i === position() }">
      <span>
        <Check v-if="i < position()" :size="15" aria-label="Завершено" />
        <template v-else>{{ i + 1 }}</template>
      </span>
      <small class="stage-full">{{ label }}</small>
      <small class="stage-short" :title="label">{{ shortLabels[i] }}</small>
    </li>
  </ol>
  <p v-if="status !== 'cancelled'" class="timeline-caption">
    Етап {{ stages.findIndex(s => s[0] === status) + 1 }} з {{ stages.length }} ·
    <strong>{{ statuses[status] }}</strong>
  </p>
  <div v-else class="alert">Заявку скасовано. Ремонт не виконано.</div>
</template>
