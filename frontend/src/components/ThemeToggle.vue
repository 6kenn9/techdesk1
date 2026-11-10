<script setup>
import { computed } from 'vue'
import { Monitor, Moon, Sun } from 'lucide-vue-next'
import { mode, setMode } from '../theme'
const options = [['light', 'Світла тема', Sun], ['dark', 'Темна тема', Moon], ['system', 'Як у системі', Monitor]]
const current = computed(() => options.find(item => item[0] === mode.value) || options[2])
const next = computed(() => options[(options.indexOf(current.value) + 1) % options.length])
</script>
<template>
  <button class="icon-button theme-toggle" type="button" :title="`${current[1]}. Натисніть: ${next[1].toLowerCase()}`"
          :aria-label="`Тема: ${current[1]}. Перемкнути на: ${next[1]}`" @click="setMode(next[0])">
    <component :is="current[2]" :size="17"/>
  </button>
</template>
