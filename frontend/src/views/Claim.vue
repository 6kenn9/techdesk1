<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from '../state'
const session = useSession(), route = useRoute(), router = useRouter(), error = ref('')
onMounted(async () => {
  try {
    session.clear()
    await session.authenticate('claim', { token: String(route.params.token) })
    await router.replace('/my-cabinet')
  } catch (e) { error.value = e.message }
})
</script>
<template>
  <div class="auth-shell"><main class="auth-main"><section class="card auth-card">
    <h1>Відкриваємо кабінет…</h1>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <RouterLink v-if="error" to="/login" class="button">Увійти за поштою</RouterLink>
  </section></main></div>
</template>
