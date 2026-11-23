<script setup>
import { ref } from 'vue'
import { api, query } from '../api'
import { categories, icons, problemHints } from '../domain'
const form = defineModel({ required: true })
defineProps({ serialLabel: { type: String, default: 'Серійний номер (необов’язково)' }, showSerial: { type: Boolean, default: false } })
const suggestions = ref([]),
  open = ref(false),
  serial = ref(false)
let timer,
  sequence = 0
function typed() {
  form.value.brand = form.value.model = ''
  clearTimeout(timer)
  timer = setTimeout(async () => {
    const seq = ++sequence
    try {
      const found = await api('/public/models' + query({ q: form.value.title, category: form.value.device_category }))
      if (seq === sequence) {
        suggestions.value = found
        open.value = found.length > 0
      }
    } catch {
      suggestions.value = []
    }
  }, 200)
}
function closeLater() {
  setTimeout(() => {
    open.value = false
  }, 150)
}
function choose(item) {
  Object.assign(form.value, { device_category: item.device_category, brand: item.brand, model: item.model, title: `${item.brand} ${item.model}` })
  open.value = false
}
function hint(text) {
  const current = form.value.problem_description.trim()
  if (current.toLowerCase().includes(text.toLowerCase())) return
  form.value.problem_description = current ? `${current}. ${text}` : text
}
</script>
<template>
  <div class="form-stack quick-fields">
    <fieldset class="tile-group">
      <legend>Що за пристрій?</legend>
      <div class="tiles">
        <label v-for="item in categories" :key="item" class="tile" :class="{ active: form.device_category === item }">
          <input v-model="form.device_category" type="radio" :value="item" name="category" @change="typed" />
          <component :is="icons[item]" :size="22" />
          <span>{{ item }}</span>
        </label>
      </div>
    </fieldset>
    <label class="suggest">
      Виробник і модель
      <input
        v-model="form.title"
        required
        maxlength="180"
        autocomplete="off"
        :placeholder="form.device_category === 'Інше' ? 'Що це за пристрій, наприклад принтер HP LaserJet 1020' : 'Наприклад, Lenovo IdeaPad 3'"
        @input="typed"
        @focus="open = suggestions.length > 0"
        @blur="closeLater"
      />
      <ul v-if="open" class="suggest-list" role="listbox">
        <li v-for="item in suggestions" :key="item.brand + item.model + item.device_category" role="option" @mousedown.prevent="choose(item)">
          {{ item.brand }} {{ item.model }}
          <small>{{ item.device_category }}</small>
        </li>
      </ul>
    </label>
    <label>
      Що сталося?
      <textarea
        v-model.trim="form.problem_description"
        required
        minlength="3"
        maxlength="4000"
        rows="3"
        placeholder="Коротко опишіть несправність"
      ></textarea>
    </label>
    <div class="hint-chips" aria-label="Типові несправності">
      <button v-for="text in problemHints" :key="text" type="button" class="chip-button" @click="hint(text)">{{ text }}</button>
    </div>
    <template v-if="showSerial">
      <button v-if="!serial && !form.serial_number" type="button" class="link-button" @click="serial = true">
        + Додати серійний номер (необов’язково)
      </button>
      <label v-else>
        {{ serialLabel }}
        <input v-model.trim="form.serial_number" maxlength="80" placeholder="Знайдете на наліпці або в налаштуваннях" />
      </label>
    </template>
  </div>
</template>
