<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { categories, categorySpecs, specLabels } from '../domain'
const props = defineProps({ includeSerial: { type: Boolean, default: true }, allowPreset: Boolean })
const form = defineModel({ required: true })
const presets = ref([])
const picked = ref('')
const fields = computed(() => [...new Set([...(categorySpecs[form.value.device_category] || []), ...Object.keys(form.value.specifications)])])
onMounted(async () => {
  try {
    presets.value = await api('/passports/presets')
  } catch {}
})
function fill() {
  const model = presets.value.find(item => item.id === picked.value)
  if (model)
    Object.assign(form.value, {
      device_category: model.device_category,
      brand: model.brand,
      model: model.model_name,
      specifications: { ...model.default_specs },
    })
}
function changeCategory() {
  picked.value = ''
  form.value.specifications = {}
}
</script>
<template>
  <div class="form-grid">
    <label v-if="props.includeSerial" class="full">
      Серійний номер або IMEI
      <input v-model.trim="form.serial_number" maxlength="80" required />
    </label>
    <label class="full">
      Заповнити з довідника
      <select v-model="picked" @change="fill">
        <option value="">Ввести модель вручну</option>
        <option v-for="item in presets" :key="item.id" :value="item.id">{{ item.brand }} {{ item.model_name }} · {{ item.device_category }}</option>
      </select>
    </label>
    <label>
      Категорія
      <select v-model="form.device_category" required @change="changeCategory">
        <option v-for="item in categories" :key="item">{{ item }}</option>
      </select>
    </label>
    <label>
      Виробник
      <input v-model.trim="form.brand" required maxlength="80" />
    </label>
    <label class="full">
      Модель
      <input v-model.trim="form.model" required maxlength="120" />
    </label>
    <label v-for="field in fields" :key="field">
      {{ specLabels[field] || field }}
      <input v-model.trim="form.specifications[field]" maxlength="160" />
    </label>
    <label class="full">
      Зовнішній стан
      <textarea v-model.trim="form.cosmetic_condition" maxlength="4000" placeholder="Наприклад, подряпини на кришці"></textarea>
    </label>
    <label v-if="props.allowPreset && !picked" class="check full">
      <input v-model="form.save_preset" type="checkbox" />
      Зберегти конфігурацію в довідник моделей
    </label>
  </div>
</template>
