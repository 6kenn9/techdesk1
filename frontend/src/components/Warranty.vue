<script setup>
import { ShieldCheck } from 'lucide-vue-next'
import { date } from '../domain'
defineProps({ warranty: Object })
</script>
<template>
  <div v-if="warranty" class="alert warranty"><ShieldCheck :size="22"/><div><strong>Чинна гарантія до {{ date(warranty.expires_at) }}</strong>
    <p>Заявка {{ warranty.order_number }}<template v-if="warranty.master"> · {{ warranty.master }}</template></p>
    <p v-if="warranty.works.length">{{ warranty.works.join(', ') }}</p></div></div>
</template>
