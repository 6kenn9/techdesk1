<script setup>
// Зірки 1–5: інтерактивні для вибору оцінки або лише для показу (readonly).
import { ref } from 'vue'
import { Star } from 'lucide-vue-next'
const model = defineModel({ type: Number, default: 0 })
const props = defineProps({ readonly: Boolean, size: { type: Number, default: 26 } })
const hover = ref(0)
const words = ['', 'Дуже погано', 'Погано', 'Нормально', 'Добре', 'Чудово']
</script>
<template>
  <span v-if="readonly" class="stars" :aria-label="`Оцінка ${model} з 5`">
    <Star v-for="n in 5" :key="n" :size="size" :class="{ on: n <= Math.round(model) }"/>
  </span>
  <span v-else class="stars pick" role="radiogroup" aria-label="Оцінка ремонту" @mouseleave="hover = 0">
    <button v-for="n in 5" :key="n" type="button" role="radio" :aria-checked="model === n" :aria-label="`${n} — ${words[n]}`"
            @mouseenter="hover = n" @focus="hover = n" @blur="hover = 0" @click="model = n">
      <Star :size="size" :class="{ on: n <= (hover || model) }"/>
    </button>
    <small class="muted">{{ words[hover || model] }}</small>
  </span>
</template>
