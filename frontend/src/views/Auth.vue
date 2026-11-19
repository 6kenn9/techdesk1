<script setup>
import { computed, onMounted, reactive, ref, watch, nextTick } from "vue";
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

// ----- Вхід через Google (Google Identity Services) -----
const googleId = ref("");
const googleButton = ref(null);
const googleCredential = ref("");
const googlePhone = ref("");
const googleName = ref("");
// Кабінет із цією поштою вже є: власник один раз підтверджує пароль, щоб пов’язати з ним вхід через Google.
const googlePassword = ref("");
const googleLinkEmail = ref("");
const googleCanReset = ref(false);
const googleReset = ref(false);
async function finish() {
  const next = route.query.next;
  await router.push(
    typeof next === "string" && next.startsWith("/") && !next.startsWith("//")
      ? next
      : session.home,
  );
}
async function sendGoogle() {
  error.value = "";
  busy.value = true;
  try {
    const data = { credential: googleCredential.value };
    if (googlePhone.value) data.phone = googlePhone.value;
    if (googlePassword.value) data.password = googlePassword.value;
    if (googleReset.value) data.reset_password = true;
    const response = await api("/auth/google", { method: "POST", data });
    if (response.needs_phone) {
      googleName.value = response.full_name;
      return;
    }
    if (response.needs_password) {
      googleLinkEmail.value = response.email;
      googleCanReset.value = !!response.can_reset;
      return;
    }
    await session.accept(response);
    await finish();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
    googleReset.value = false;
  }
}
function linkWithoutPassword() {
  if (!confirm("Кабінет буде прив’язано до Google. Старий пароль перестане діяти, а інші сеанси буде завершено. Надалі входьте кнопкою Google. Продовжити?")) return;
  googlePassword.value = "";
  googleReset.value = true;
  sendGoogle();
}
function onGoogle(response) {
  googleCredential.value = response.credential;
  googlePhone.value = "";
  googleName.value = "";
  googlePassword.value = "";
  googleLinkEmail.value = "";
  sendGoogle();
}
function loadGoogle() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}
async function drawGoogle() {
  if (!googleId.value) return;
  await nextTick();
  if (!googleButton.value) return;
  const dark = document.documentElement.dataset.theme === "dark";
  window.google.accounts.id.initialize({
    client_id: googleId.value,
    callback: onGoogle,
    ux_mode: "popup",
  });
  googleButton.value.innerHTML = "";
  window.google.accounts.id.renderButton(googleButton.value, {
    type: "standard",
    theme: dark ? "filled_black" : "outline",
    size: "large",
    text: register.value ? "signup_with" : "signin_with",
    shape: "rectangular",
    logo_alignment: "left",
    width: 320,
    locale: "uk",
  });
}
onMounted(async () => {
  try {
    googleId.value = (await api("/auth/options")).google_client_id || "";
    if (!googleId.value) return;
    await loadGoogle();
    await drawGoogle();
  } catch {
    googleId.value = ""; // немає доступу до Google — лишається звичайна форма
  }
});
watch(register, drawGoogle);

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
            Прізвище та ім’я
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
          <RouterLink v-if="!register" to="/reset" style="justify-self: end; align-self: flex-end; margin-top: -8px; font-size: .86rem">Забули пароль?</RouterLink>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="button primary wide" :disabled="busy">
            {{ register ? "Зареєструватися" : "Увійти" }}
            <ArrowRight :size="17" />
          </button>
        </form>
        <template v-if="googleId">
          <div class="auth-or"><span>або</span></div>
          <form
            v-if="googleName"
            class="form-stack"
            @submit.prevent="sendGoogle()"
          >
            <p class="muted">
              Вітаємо, {{ googleName }}! Для зв’язку з майстром вкажіть телефон
              — і кабінет буде створено.
            </p>
            <label>
              Телефон
              <input
                v-model.trim="googlePhone"
                autocomplete="tel"
                type="tel"
                placeholder="+380…"
                required
              />
            </label>
            <button class="button primary wide" :disabled="busy">
              Завершити реєстрацію
              <ArrowRight :size="17" />
            </button>
          </form>
          <form
            v-else-if="googleLinkEmail"
            class="form-stack"
            @submit.prevent="sendGoogle()"
          >
            <p class="muted">
              Кабінет із поштою {{ googleLinkEmail }} уже існує. Щоб надалі входити через Google,
              один раз підтвердьте його пароль.
            </p>
            <label>
              Пароль кабінету
              <input
                v-model="googlePassword"
                autocomplete="current-password"
                type="password"
                required
              />
            </label>
            <button class="button primary wide" :disabled="busy">
              Пов’язати й увійти
              <ArrowRight :size="17" />
            </button>
            <button v-if="googleCanReset" type="button" class="link-button" :disabled="busy" @click="linkWithoutPassword">
              Не знаю пароля — кабінет створено через Google
            </button>
          </form>
          <div v-else ref="googleButton" class="google-slot"></div>
        </template>
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
