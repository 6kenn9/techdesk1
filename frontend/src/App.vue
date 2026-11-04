<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, ArrowUpRight, Boxes, ClipboardList, Cpu, LayoutDashboard, LogOut, Menu, UsersRound, X } from 'lucide-vue-next'
import { useSession } from './state'
import { roles } from './domain'

const session = useSession()
const route = useRoute()
const router = useRouter()
const menu = ref(false)
const links = [
  ['/analytics', 'Аналітика', LayoutDashboard, ['admin']],
  ['/orders', 'Журнал заявок', ClipboardList, ['admin', 'master']],
  ['/my-cabinet', 'Мій кабінет', LayoutDashboard, ['client']],
  ['/passports', 'Паспорти пристроїв', Cpu, ['admin', 'master', 'client']],
  ['/warehouse', 'Склад і послуги', Boxes, ['admin', 'master']],
  ['/staff', 'Команда', UsersRound, ['admin']],
]
function signOut() { session.clear(); router.push('/login') }
function expire() { session.clear(); if (route.meta.auth || route.meta.roles) router.push('/login') }
onMounted(() => window.addEventListener('techdesk-expired', expire))
onUnmounted(() => window.removeEventListener('techdesk-expired', expire))
</script>

<template>
  <div v-if="session.user && route.meta.label" class="workspace">
    <aside class="sidebar" :class="{ opened: menu }">
      <RouterLink :to="session.home" class="brand" @click="menu=false">
        <img src="/mark.svg" alt="" width="39" height="39"><div>TechDesk<small>СЕРВІСНИЙ ЦЕНТР</small></div>
      </RouterLink>
      <div class="nav-caption">РОБОЧИЙ ПРОСТІР</div>
      <nav aria-label="Основна навігація">
        <template v-for="[path,label,Icon,allowed] in links" :key="path">
          <RouterLink v-if="allowed.includes(session.user.role)" :to="path" @click="menu=false">
            <component :is="Icon" :size="19"/>{{ label }}
          </RouterLink>
        </template>
      </nav>
      <div class="sidebar-bottom">
        <RouterLink to="/" class="public-link"><ArrowUpRight :size="16"/> Публічний сайт</RouterLink>
        <div class="identity"><span class="avatar">{{ session.user.full_name.slice(0, 1) }}</span><div><strong>{{ session.user.full_name }}</strong><small>{{ roles[session.user.role] }}</small></div>
          <button class="icon-button logout" aria-label="Вийти" title="Вийти" @click="signOut"><LogOut :size="17"/></button>
        </div>
      </div>
    </aside>
    <div v-if="menu" class="scrim" @click="menu=false"></div>
    <div class="workspace-main">
      <header class="topbar"><button class="icon-button mobile-menu" aria-label="Відкрити меню" @click="menu=!menu"><Menu :size="22"/></button>
        <span class="crumb">Робочий простір <span>/</span> <strong>{{ route.meta.label }}</strong></span>
        <span class="role-chip"><Activity :size="15"/>{{ roles[session.user.role] }}</span>
      </header>
      <main class="content"><RouterView :key="route.path"/></main>
    </div>
  </div>
  <RouterView v-else-if="!route.meta.label" :key="route.path"/>
  <div v-if="session.notice" class="toast" :class="session.noticeType" role="status">{{ session.notice }}
    <button class="icon-button" aria-label="Закрити повідомлення" @click="session.notice=''"><X :size="17"/></button>
  </div>
</template>
