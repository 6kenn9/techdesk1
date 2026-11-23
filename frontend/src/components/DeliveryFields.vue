<script setup>
import { ref, watch } from 'vue'
import { Store, Truck } from 'lucide-vue-next'
const model = defineModel({ type: Object, required: true })
const other = ref(!!model.value.recipient_name)
watch(other, (on) => { if (!on) Object.assign(model.value, { recipient_name: '', recipient_phone: '' }) })
const options = [
  ['pickup', 'Заберу сам', Store],
  ['nova_poshta', 'Нова Пошта', Truck],
]
</script>
<template>
  <fieldset class="tile-group delivery-fields">
    <legend>Як повернути пристрій після ремонту?</legend>
    <div class="segmented">
      <button
        v-for="[key, label, icon] in options"
        :key="key"
        type="button"
        class="button small"
        :aria-pressed="model.method === key"
        @click="model.method = key"
      >
        <component :is="icon" :size="16" />
        {{ label }}
      </button>
    </div>
    <div v-if="model.method === 'nova_poshta'" class="form-grid" style="margin-top: 10px">
      <label>
        Місто
        <input v-model.trim="model.city" required minlength="2" maxlength="80" placeholder="Київ" autocomplete="address-level2" />
      </label>
      <label>
        Відділення або поштомат
        <input v-model.trim="model.branch" required maxlength="120" placeholder="Відділення №12" />
      </label>
      <label class="check full">
        <input v-model="other" type="checkbox" />
        Отримувач інша людина
      </label>
      <template v-if="other">
        <label>
          Ім'я та прізвище отримувача
          <input v-model.trim="model.recipient_name" required minlength="2" maxlength="150" placeholder="Петренко Іван" autocomplete="off" />
        </label>
        <label>
          Телефон отримувача
          <input v-model.trim="model.recipient_phone" required type="tel" maxlength="20" placeholder="+380501234567" autocomplete="off" />
        </label>
      </template>
      <small class="muted full">Відправимо після повної оплати ремонту. Доставку оплачує отримувач за тарифами перевізника.</small>
    </div>
  </fieldset>
</template>
