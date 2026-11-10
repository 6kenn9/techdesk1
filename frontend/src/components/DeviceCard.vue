<script setup>
import { computed } from 'vue'
import { ArrowUpRight, Cpu } from 'lucide-vue-next'
import { icons, specLabels } from '../domain'

const props = defineProps({ item: Object })
const preview = computed(() => {
  const values = props.item.specifications || {}
  const fields = [...new Set(['cpu', 'ram', 'storage', ...Object.keys(values)])]
  return fields.filter(field => values[field]).slice(0, 3).map(field => [specLabels[field] || field, values[field]])
})
</script>
<template>
  <RouterLink class="card device-card" :to="'/passports/' + item.id">
    <div class="device-meta">
      <span class="chip"><component :is="icons[item.device_category] || Cpu" :size="16"/>{{ item.device_category }}</span>
      <span class="serial-chip mono">{{ item.serial_number || 'без серійного номера' }}</span>
      <span v-if="item.warranty" class="status completed"><i></i> Гарантія</span>
    </div>
    <div class="device-title"><h3>{{ item.brand }} {{ item.model }}</h3><ArrowUpRight :size="16"/></div>
    <dl v-if="preview.length" class="device-preview">
      <div v-for="[label, value] in preview" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div>
    </dl>
    <p v-else class="device-owner">Власник: {{ item.owner_name }}</p>
  </RouterLink>
</template>
