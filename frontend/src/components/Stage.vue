<script setup>
import { statuses } from '../domain'
defineProps({ status: String })
</script>
<template><span class="status" :class="status"><i></i>{{ statuses[status] }}</span></template>
