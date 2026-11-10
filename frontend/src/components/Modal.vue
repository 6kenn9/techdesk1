<script setup>
import { onMounted, ref } from 'vue'
import { X } from 'lucide-vue-next'
defineProps({ title: String })
const emit = defineEmits(['close'])
const dialog = ref(null)
onMounted(() => dialog.value.showModal())
</script>
<template>
  <dialog ref="dialog" class="modal" @cancel.prevent="emit('close')" @click.self="emit('close')">
    <div class="modal-body">
      <div class="section-head">
        <h2>{{ title }}</h2>
        <button type="button" class="icon-button" aria-label="Закрити" @click="emit('close')"><X :size="21" /></button>
      </div>
      <slot />
    </div>
  </dialog>
</template>
