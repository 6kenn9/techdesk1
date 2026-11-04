<script setup>
import { ArrowUpRight, Cpu, ShieldCheck } from 'lucide-vue-next'
import { icons } from '../domain'
defineProps({ item: Object })
</script>
<template>
  <RouterLink class="card device-card" :to="'/passports/' + item.id">
    <div class="section-head"><span class="tile-icon"><component :is="icons[item.device_category] || Cpu" :size="22"/></span><ArrowUpRight :size="19"/></div>
    <div><p>{{ item.device_category }}</p><h3>{{ item.brand }} {{ item.model }}</h3></div>
    <div><span class="chip mono">{{ item.serial_number }}</span></div>
    <small>{{ item.owner_name }}</small>
    <small v-if="item.warranty"><ShieldCheck :size="14"/> Чинна гарантія</small>
  </RouterLink>
</template>
