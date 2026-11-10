import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './state'
import Landing from './views/Landing.vue'
import Auth from './views/Auth.vue'
import Analytics from './views/Analytics.vue'
import Orders from './views/Orders.vue'
import OrderForm from './views/OrderForm.vue'
import OrderDetail from './views/OrderDetail.vue'
import Passports from './views/Passports.vue'
import PassportDetail from './views/PassportDetail.vue'
import Warehouse from './views/Warehouse.vue'
import Staff from './views/Staff.vue'
import Cabinet from './views/Cabinet.vue'
import Quick from './views/Quick.vue'
import Claim from './views/Claim.vue'
import Intake from './views/Intake.vue'

export function makeRouter(pinia) {
  const router = createRouter({
    history: createWebHistory(),
    scrollBehavior: () => ({ top: 0 }),
    routes: [
      { path: '/', component: Landing },
      { path: '/track/:code', component: Landing },
      { path: '/quick', component: Quick },
      { path: '/claim/:token', component: Claim },
      { path: '/login', component: Auth },
      { path: '/register', component: Auth },
      { path: '/analytics', component: Analytics, meta: { roles: ['admin'], label: 'Аналітика' } },
      { path: '/staff', component: Staff, meta: { roles: ['admin'], label: 'Команда' } },
      { path: '/warehouse', component: Warehouse, meta: { roles: ['admin', 'master'], label: 'Склад і послуги' } },
      { path: '/orders', component: Orders, meta: { roles: ['admin', 'master'], label: 'Журнал заявок' } },
      { path: '/orders/intake', component: Intake, meta: { roles: ['admin', 'master'], label: 'Швидке приймання' } },
      { path: '/orders/new', component: OrderForm, meta: { auth: true, label: 'Нова заявка' } },
      { path: '/orders/:id', component: OrderDetail, meta: { auth: true, label: 'Картка заявки' } },
      { path: '/passports', component: Passports, meta: { auth: true, label: 'Цифрові паспорти' } },
      { path: '/passports/:id', component: PassportDetail, meta: { auth: true, label: 'Паспорт пристрою' } },
      { path: '/my-day', component: () => import('./views/MyDay.vue'), meta: { roles: ['master'], label: 'Мій день' } },
      { path: '/scan', component: () => import('./views/Scan.vue'), meta: { roles: ['admin', 'master'], label: 'Сканер' } },
      { path: '/profile', component: () => import('./views/Profile.vue'), meta: { auth: true, label: 'Профіль' } },
      { path: '/my-cabinet', component: Cabinet, meta: { roles: ['client'], label: 'Особистий кабінет' } },
      { path: '/:pathMatch(.*)*', redirect: '/' },
    ],
  })
  router.beforeEach(async to => {
    const session = useSession(pinia)
    await session.restore()
    if ((to.meta.auth || to.meta.roles) && !session.user) return { path: '/login', query: { next: to.fullPath } }
    if (to.meta.roles && !to.meta.roles.includes(session.user.role)) return session.home
    if (session.user && ['/login', '/register'].includes(to.path)) return session.home
  })
  return router
}
