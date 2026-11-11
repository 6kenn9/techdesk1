<script setup>
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, ArrowRight } from "lucide-vue-next";
import { useSession } from "../state";
import { api } from "../api";
import ThemeToggle from "../components/ThemeToggle.vue";

const session = useSession();
const route = useRoute();
const router = useRouter();
const register = computed(() => route.path === "/register");
const form = reactive({ email: "", password: "", full_name: "", phone: "" });
const error = ref("");
const busy = ref(false);
async function submit() {
  error.value = "";
  busy.value = true;
  try {
    const data = register.value
      ? { ...form }
      : { email: form.email, password: form.password };
    await session.authenticate(register.value ? "register" : "login", data);
    const next = route.query.next;
    await router.push(
      typeof next === "string" && next.startsWith("/") && !next.startsWith("//")
        ? next
        : session.home,
    );
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="auth-shell">
    <header class="public-topbar">
      <div class="wrap public-nav">
        <RouterLink to="/" class="brand">
          <img src="/mark.svg" alt="" width="30" height="30" />
          TechDesk
        </RouterLink>
        <span class="actions">
          <ThemeToggle />
          <RouterLink to="/" class="button">
            <ArrowLeft :size="16" />
            На головну
          </RouterLink>
        </span>
      </div>
    </header>
    <main class="auth-main">
      <section class="card auth-card">
        <h1>
          {{ register ? "Створення облікового запису" : "Вхід до TechDesk" }}
        </h1>
        <form class="form-stack" @submit.prevent="submit()">
          <label v-if="register">
            Ім’я та прізвище
            <input
              v-model.trim="form.full_name"
              autocomplete="name"
              required
              maxlength="150"
            />
          </label>
          <label v-if="register">
            Телефон
            <input
              v-model.trim="form.phone"
              autocomplete="tel"
              type="tel"
              placeholder="+380…"
              required
            />
          </label>
          <label>
            Електронна пошта
            <input
              v-model.trim="form.email"
              autocomplete="email"
              type="email"
              required
            />
          </label>
          <label>
            Пароль
            <input
              v-model="form.password"
              :autocomplete="register ? 'new-password' : 'current-password'"
              type="password"
              :minlength="register ? 8 : 1"
              required
            />
          </label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="button primary wide" :disabled="busy">
            {{ register ? "Зареєструватися" : "Увійти" }}
            <ArrowRight :size="17" />
          </button>
        </form>
        <p class="auth-switch">
          <RouterLink :to="register ? '/login' : '/register'">
            {{
              register
                ? "Уже маєте обліковий запис? Увійти"
                : "Створити обліковий запис"
            }}
          </RouterLink>
        </p>
      </section>
    </main>
  </div>
</template>
