<script setup>
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowUpRight,
  Boxes,
  ClipboardList,
  Cpu,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  ScanLine,
  Sun,
  UserRound,
  UsersRound,
  X,
} from "lucide-vue-next";
import TelegramConnect from "./components/TelegramConnect.vue";
import ThemeToggle from "./components/ThemeToggle.vue";
import NotificationBell from "./components/NotificationBell.vue";
import { useSession } from "./state";
import { api, watchToken } from "./api";
import { roles, workload } from "./domain";

const session = useSession();
const route = useRoute();
const router = useRouter();
const menu = ref(false);
const links = [
  ["/analytics", "Аналітика", LayoutDashboard, ["admin"]],
  ["/my-day", "Мій день", Sun, ["master"]],
  ["/orders", "Журнал заявок", ClipboardList, ["admin", "master"]],
  ["/my-cabinet", "Мій кабінет", LayoutDashboard, ["client"]],
  ["/passports", "Паспорти пристроїв", Cpu, ["admin", "master", "client"]],
  ["/scan", "Сканер", ScanLine, ["admin", "master"]],
  ["/warehouse", "Склад і послуги", Boxes, ["admin", "master"]],
  ["/staff", "Адміністрування", UsersRound, ["admin"]],
  ["/profile", "Профіль", UserRound, ["admin", "master", "client"]],
];
// Позначка біля «Мого дня»: скільки заявок чекає на дію майстра. Оновлюється при переході між сторінками й раз на хвилину.
const todo = ref(0);
let todoTimer;
async function refreshTodo() {
  if (session.user?.role !== "master") {
    todo.value = 0;
    return;
  }
  try {
    todo.value = workload(await api("/orders"), session.user.id);
  } catch {
    /* позначка не критична: без неї меню працює як раніше */
  }
}
watch(() => [route.path, session.user?.id], refreshTodo);
function signOut() {
  session.clear();
  router.push("/login");
}
function expire() {
  session.clear();
  if (route.meta.auth || route.meta.roles) router.push("/login");
}
onMounted(() => {
  window.addEventListener("techdesk-expired", expire);
  watchToken();
  refreshTodo();
  todoTimer = setInterval(refreshTodo, 60000);
});
onUnmounted(() => {
  window.removeEventListener("techdesk-expired", expire);
  clearInterval(todoTimer);
});
</script>

<template>
  <div v-if="session.user && route.meta.label" class="workspace">
    <aside class="sidebar" :class="{ opened: menu }">
      <RouterLink :to="session.home" class="brand" @click="menu = false">
        <img src="/mark.svg" alt="" width="28" height="28" />
        TechDesk
      </RouterLink>
      <nav aria-label="Основна навігація">
        <template v-for="[path, label, Icon, allowed] in links" :key="path">
          <RouterLink
            v-if="allowed.includes(session.user.role)"
            :to="path"
            @click="menu = false"
          >
            <component :is="Icon" :size="17" />
            {{ label }}
            <span
              v-if="path === '/my-day' && todo"
              class="nav-badge"
              :title="`Чекають на вашу дію: ${todo}`"
              >{{ todo }}</span
            >
          </RouterLink>
        </template>
      </nav>
      <div class="sidebar-bottom">
        <TelegramConnect compact />
        <RouterLink to="/" class="public-link">
          <ArrowUpRight :size="16" />
          Публічний сайт
        </RouterLink>
        <div class="identity">
          <span class="avatar">{{ session.user.full_name.slice(0, 1) }}</span>
          <div>
            <strong>{{ session.user.full_name }}</strong>
            <small>{{ roles[session.user.role] }}</small>
          </div>
          <button
            class="icon-button logout"
            aria-label="Вийти"
            title="Вийти"
            @click="signOut"
          >
            <LogOut :size="17" />
          </button>
        </div>
      </div>
    </aside>
    <div v-if="menu" class="scrim" @click="menu = false"></div>
    <div class="workspace-main">
      <header class="topbar">
        <button
          class="icon-button mobile-menu"
          aria-label="Відкрити меню"
          :aria-expanded="menu"
          @click="menu = !menu"
        >
          <Menu :size="19" />
        </button>
        <span class="crumb">
          Робочий простір
          <span>/</span>
          <strong>{{ route.meta.label }}</strong>
        </span>
        <span class="actions">
          <NotificationBell v-if="session.staff" />
          <ThemeToggle />
        </span>
      </header>
      <main class="content">
        <RouterLink
          v-if="session.user.must_change_password && route.path !== '/profile'"
          to="/profile"
          class="alert warranty password-banner"
        >
          <KeyRound :size="17" />
          Ви увійшли з тимчасовим паролем. Натисніть, щоб задати власний.
        </RouterLink>
        <RouterView :key="route.path" />
      </main>
    </div>
  </div>
  <RouterView v-else-if="!route.meta.label" :key="route.path" />
  <div
    v-if="session.notice"
    class="toast"
    :class="session.noticeType"
    role="status"
  >
    {{ session.notice }}
    <button
      class="icon-button"
      aria-label="Закрити повідомлення"
      @click="session.notice = ''"
    >
      <X :size="17" />
    </button>
  </div>
</template>
