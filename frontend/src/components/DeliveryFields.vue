<script setup>
// Вибір способу повернення пристрою: самовивіз із центру або відправка Новою Поштою.
import { Store, Truck } from 'lucide-vue-next'
const model = defineModel({ type: Object, required: true })
const options = [['pickup', 'Заберу сам', Store], ['nova_poshta', 'Нова Пошта', Truck]]
</script>
<template>
  <fieldset class="tile-group delivery-fields">
    <legend>Як повернути пристрій після ремонту?</legend>
    <div class="segmented">
      <button v-for="[key, label, icon] in options" :key="key" type="button" class="button small" :aria-pressed="model.method === key" @click="model.method = key">
        <component :is="icon" :size="16"/> {{ label }}
      </button>
    </div>
    <div v-if="model.method === 'nova_poshta'" class="form-grid" style="margin-top:10px">
      <label>Місто<input v-model.trim="model.city" required minlength="2" maxlength="80" placeholder="Київ" autocomplete="address-level2"></label>
      <label>Відділення або поштомат<input v-model.trim="model.branch" required maxlength="120" placeholder="Відділення №12"></label>
      <small class="muted full">Відправимо після повної оплати ремонту. Доставку оплачує отримувач за тарифами перевізника.</small>
    </div>
  </fieldset>
</template>
