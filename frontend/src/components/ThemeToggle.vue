<script setup>
import { computed } from 'vue'
import { Moon, Sun } from 'lucide-vue-next'
import { mode, setMode } from '../theme'
const dark = computed(() => mode.value === 'dark')
const label = computed(() => (dark.value ? 'Темна тема. Увімкнути світлу' : 'Світла тема. Увімкнути темну'))
</script>
<template>
  <button class="icon-button theme-toggle" type="button" :title="label" :aria-label="label" @click="setMode(dark ? 'light' : 'dark')">
    <component :is="dark ? Moon : Sun" :size="17"/>
  </button>
</template>
