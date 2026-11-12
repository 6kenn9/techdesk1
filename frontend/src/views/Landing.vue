<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  Clock,
  Cpu,
  FileCheck2,
  Gamepad2,
  HardDrive,
  Laptop,
  MapPin,
  Monitor,
  Phone,
  ShieldCheck,
  Truck,
  Smartphone,
  Watch,
  Wrench,
} from 'lucide-vue-next'
import { api, query } from '../api'
import { orderIdByNumber } from '../domain'
import { useSession } from '../state'
import Stage from '../components/Stage.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import Timeline from '../components/Timeline.vue'

const session = useSession()
const route = useRoute()
const router = useRouter()
const code = ref(route.params.code || '')
const result = ref(null)
const error = ref('')
const loading = ref(false)
const activeCategory = ref(0)
const openFaq = ref(0)


const serviceCatalog = [
  {
    icon: Laptop,
    name: 'Ноутбуки',
    desc: 'Чистка систем охолодження, заміна матриць і клавіатур, ремонт материнських плат та апгрейд ОЗП і SSD.',
    jobs: [
      { title: 'Чистка системи охолодження та заміна термоінтерфейсу', time: '2–3 год', warranty: '90 днів', price: '850 ₴' },
      { title: 'Модернізація ОЗП або встановлення NVMe SSD', time: '1 год', warranty: '180 днів', price: '450 ₴' },
      { title: 'Заміна пошкодженої матриці екрана (IPS / OLED)', time: '1 день', warranty: '180 днів', price: 'від 950 ₴' },
      { title: 'Ремонт ланцюгів живлення материнської плати', time: '2–4 дні', warranty: '120 днів', price: 'від 1 600 ₴' },
    ],
  },
  {
    icon: Cpu,
    name: 'Стаціонарні ПК',
    desc: 'Стендова діагностика комплектуючих, ремонт блоків живлення, оновлення BIOS та модернізація робочих і геймерських ПК.',
    jobs: [
      { title: 'Повна апаратна діагностика ПК зі стрес-тестом', time: '3–5 год', warranty: '30 днів', price: '500 ₴' },
      { title: 'Апгрейд відеокарти, процесора або материнської плати', time: '2–4 год', warranty: '180 днів', price: '750 ₴' },
      { title: 'Обслуговування відеокарти (заміна термопрокладок і кулерів)', time: '2–3 год', warranty: '90 днів', price: '900 ₴' },
      { title: 'Ремонт або заміна блока живлення', time: '1 день', warranty: '120 днів', price: 'від 650 ₴' },
    ],
  },
  {
    icon: Smartphone,
    name: 'Смартфони і планшети',
    desc: 'Заміна дисплейних модулів, акумуляторів із фіксацією нової ємності в паспорті, роз’ємів зарядки та відновлення після вологи.',
    jobs: [
      { title: 'Заміна акумулятора з оновленням стану в паспорті', time: '1–2 год', warranty: '120 днів', price: 'від 600 ₴' },
      { title: 'Заміна дисплейного модуля (OLED / IPS)', time: '2–4 год', warranty: '180 днів', price: 'від 900 ₴' },
      { title: 'Заміна роз’єму зарядки USB Type-C / Lightning', time: '2 год', warranty: '90 днів', price: '650 ₴' },
      { title: 'Чистка та відновлення плати після потрапляння вологи', time: '1–3 дні', warranty: '60 днів', price: 'від 1 100 ₴' },
    ],
  },
  {
    icon: Monitor,
    name: 'Моноблоки і монітори',
    desc: 'Ремонт вбудованих блоків живлення, відновлення LED-підсвітки, скалерів та профілактика моноблоків.',
    jobs: [
      { title: 'Ремонт вбудованого блока живлення монітора', time: '1–2 дні', warranty: '120 днів', price: 'від 850 ₴' },
      { title: 'Заміна лінійок LED-підсвітки матриці', time: '1–2 дні', warranty: '120 днів', price: 'від 1 100 ₴' },
      { title: 'Чистка системи охолодження моноблока', time: '3–5 год', warranty: '90 днів', price: '1 200 ₴' },
      { title: 'Модернізація SSD та ОЗП у моноблоках', time: '1 день', warranty: '180 днів', price: '1 350 ₴' },
    ],
  },
  {
    icon: Watch,
    name: 'Смарт-годинники',
    desc: 'Заміна пошкодженого скла та екранів, встановлення нових акумуляторів і відновлення герметичності корпусу.',
    jobs: [
      { title: 'Заміна акумулятора з відновленням герметичності', time: '2–3 год', warranty: '120 днів', price: '750 ₴' },
      { title: 'Заміна дисплейного модуля або захисного скла', time: '1 день', warranty: '120 днів', price: 'від 950 ₴' },
      { title: 'Ремонт кнопок керування та контактів зарядки', time: '1 день', warranty: '90 днів', price: '700 ₴' },
    ],
  },
  {
    icon: Gamepad2,
    name: 'Консолі та ДБЖ',
    desc: 'Чистка PlayStation і Xbox із заміною рідкого металу, перепайка HDMI, ремонт геймпадів та заміна батарей у безперебійниках.',
    jobs: [
      { title: 'Чистка консолі + заміна рідкого металу / термопрокладок', time: '2–3 год', warranty: '90 днів', price: '1 100 ₴' },
      { title: 'Заміна порту HDMI або контролера відеовиходу', time: '1 день', warranty: '120 днів', price: '1 250 ₴' },
      { title: 'Усунення дрифту стіків геймпада', time: '1–2 год', warranty: '120 днів', price: '650 ₴' },
      { title: 'Заміна силових акумуляторів у ДБЖ (UPS) із калібруванням', time: '1–2 год', warranty: '180 днів', price: '550 ₴' },
    ],
  },
]

const currentService = computed(() => serviceCatalog[activeCategory.value])

const advantages = [
  {
    icon: HardDrive,
    title: 'Цифровий паспорт за серійним номером',
    text: 'Уся історія ремонтів, виявлених дефектів і оновлених під час апгрейду характеристик зберігається в єдиній картці пристрою за його S/N або IMEI.',
  },
  {
    icon: CheckCircle2,
    title: 'Погодження вартості онлайн',
    text: 'Майстер не розпочинає платний ремонт без вашого рішення. Після діагностики ви бачите перелік робіт і запчастин у кабінеті та погоджуєте суму в один клік.',
  },
  {
    icon: Wrench,
    title: 'Фіксована ціна запчастин зі складу',
    text: 'Необхідні деталі одразу резервуються під вашу заявку за поточною ціною складу, тому підсумкова сума не зміниться під час ремонту.',
  },
  {
    icon: FileCheck2,
    title: 'Квитанція та гарантія у PDF',
    text: 'Приймальна квитанція і гарантійний талон із QR-кодом формуються автоматично. При повторному зверненні система сама нагадає про чинну гарантію.',
  },
]

const faqs = [
  {
    q: 'Що таке «Цифровий паспорт пристрою» і чим він зручний?',
    a: 'Під час першого звернення ми прив’язуємо ваш пристрій за серійним номером (S/N або IMEI) і записуємо його характеристики та стан. Усі наступні звернення, замінені запчастини й апгрейди зберігаються в цій картці, тому вам не потрібно тримати паперові квитанції.',
  },
  {
    q: 'Що буде, якщо після діагностики мені не підійде вартість ремонту?',
    a: 'Ви можете натиснути «Відхилити вартість» в особистому кабінеті. Жодні ремонтні роботи без вашого підтвердження не виконуються — ви зможете узгодити інший варіант ремонту або забрати пристрій.',
  },
  {
    q: 'Як перевіряється гарантія при повторному зверненні?',
    a: 'У кожній завершеній заявці зберігається кінцева дата гарантії. Коли пристрій приносять повторно, працівник за серійним номером одразу бачить, що техніка на гарантії. Щоб попросити гарантійний ремонт самостійно, позначте «Гарантійне звернення» в новій заявці в кабінеті.',
  },
]

async function lookup() {
  if (!code.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await api('/track' + query({ code: code.value.trim() }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!code.value) return
  // QR із квитанції відкрив увійшлий працівник або власник — ведемо одразу в заявку
  if (session.user) {
    const id = await orderIdByNumber(code.value)
    if (id) return router.replace('/orders/' + id)
  }
  lookup()
})
</script>

<template>
  <div class="landing">
    <header class="public-topbar">
      <div class="wrap public-nav">
        <RouterLink class="brand" to="/">
          <img src="/mark.svg" alt="" width="28" height="28" />
          TechDesk
        </RouterLink>
        <nav class="public-links" aria-label="Розділи сайту">
          <a href="#services">Послуги та ціни</a>
          <a href="#advantages">Переваги</a>
          <a href="#workflow">Етапи роботи</a>
          <a href="#contacts">Контакти</a>
        </nav>
        <div class="actions">
          <ThemeToggle />
          <RouterLink v-if="!session.user" to="/quick" class="button">Швидка заявка</RouterLink>
          <RouterLink :to="session.user ? session.home : '/login'" class="button primary">
            {{ session.user ? 'Робочий простір' : 'Увійти в кабінет' }}
            <ArrowUpRight :size="15" />
          </RouterLink>
        </div>
      </div>
    </header>

    <main>
      <!-- 1. Перший екран -->
      <section class="hero-clean wrap" aria-labelledby="portal-title">
        <div class="hero-clean-head">
          <h1 id="portal-title">Сервісний центр комп’ютерної та цифрової техніки TechDesk</h1>
          <p>
            Ремонт і модернізація ноутбуків, ПК, смартфонів, моніторів, смарт-годинників та консолей. Зберігаємо історію кожного пристрою за серійним
            номером і погоджуємо кошторис онлайн до початку робіт.
          </p>
        </div>

        <div class="hero-cta">
          <RouterLink :to="session.user ? (session.staff ? session.home : '/orders/new') : '/quick'" class="button primary">
            Залишити заявку на ремонт
            <ArrowRight :size="17" />
          </RouterLink>
          <RouterLink v-if="!session.user" to="/login" class="button">Увійти в кабінет</RouterLink>
          <a href="#services" class="button">Послуги та ціни</a>
        </div>

        <ul class="hero-facts">
          <li><MapPin :size="16" /> м. Київ, вул. Політехнічна, 14</li>
          <li><Clock :size="16" /> Пн–Пт 09:00–19:00, Сб 10:00–17:00</li>
          <li><Phone :size="16" /> <span class="mono">+380 (44) 290-45-18</span></li>
          <li><Truck :size="16" /> Повертаємо техніку Новою Поштою</li>
        </ul>

        <!-- Статус за QR-кодом із квитанції: /track/TD-2026-0004 -->
        <div v-if="code" id="tracking" class="card tracker-card">
          <p v-if="loading" class="muted">Завантаження статусу…</p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div v-if="result" class="tracking-result" aria-live="polite">
            <div class="section-head">
              <h3>
                Статус заявки
                <span class="mono">{{ code }}</span>
              </h3>
              <Stage :status="result.status" />
            </div>
            <Timeline :status="result.status" />
          </div>
        </div>

        <div class="hero-highlights">
          <div>
            <strong>Діагностика від 1 дня</strong>
            <span>точне виявлення несправності</span>
          </div>
          <div>
            <strong>Паспорт за S/N та IMEI</strong>
            <span>вся історія ремонтів і апгрейдів</span>
          </div>
          <div>
            <strong>Онлайн-погодження</strong>
            <span>жодних робіт без вашої згоди</span>
          </div>
          <div>
            <strong>Гарантія до 180 днів</strong>
            <span>офіційний талон та акт у PDF</span>
          </div>
        </div>
      </section>

      <!-- 2. Послуги та прейскурант -->
      <section id="services" class="landing-section wrap" aria-labelledby="services-title">
        <div class="landing-section-head">
          <div>
            <h2 id="services-title">Послуги та орієнтовний прайс</h2>
            <p>Оберіть тип пристрою, щоб переглянути основні види робіт, терміни виконання та гарантію.</p>
          </div>
          <RouterLink :to="session.user ? '/orders/new' : '/quick'" class="button">
            Оформити заявку
            <ArrowRight :size="15" />
          </RouterLink>
        </div>

        <div class="service-tabs" role="tablist" aria-label="Категорії пристроїв">
          <button
            v-for="(cat, idx) in serviceCatalog"
            :key="cat.name"
            type="button"
            role="tab"
            class="service-tab-btn"
            :class="{ active: activeCategory === idx }"
            :aria-selected="activeCategory === idx"
            @click="activeCategory = idx"
          >
            <component :is="cat.icon" :size="16" />
            <span>{{ cat.name }}</span>
          </button>
        </div>

        <div class="card service-table-card" role="tabpanel">
          <div class="service-table-intro">
            <h3>{{ currentService.name }}</h3>
            <p>{{ currentService.desc }}</p>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Послуга</th>
                  <th>Орієнтовний час</th>
                  <th>Гарантія</th>
                  <th class="align-right">Вартість</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in currentService.jobs" :key="job.title">
                  <td>
                    <strong>{{ job.title }}</strong>
                  </td>
                  <td class="nowrap">{{ job.time }}</td>
                  <td class="nowrap">{{ job.warranty }}</td>
                  <td class="align-right mono nowrap">
                    <strong>{{ job.price }}</strong>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- 3. Як ми працюємо з клієнтом -->
      <section id="advantages" class="landing-section landing-band" aria-labelledby="advantages-title">
        <div class="wrap">
          <div class="landing-section-head">
            <div>
              <h2 id="advantages-title">Чому клієнти обирають наш сервіс</h2>
              <p>Прозорий облік пристроїв, запчастин і вартості на кожному етапі обслуговування.</p>
            </div>
          </div>

          <div class="grid-2">
            <article v-for="adv in advantages" :key="adv.title" class="card simple-feature-card">
              <div class="simple-feature-head">
                <span class="simple-feature-icon"><component :is="adv.icon" :size="18" /></span>
                <h3>{{ adv.title }}</h3>
              </div>
              <p>{{ adv.text }}</p>
            </article>
          </div>
        </div>
      </section>

      <!-- 4. Етапи ремонту та часті питання -->
      <section id="workflow" class="landing-section wrap" aria-labelledby="workflow-title">
        <div class="landing-section-head">
          <div>
            <h2 id="workflow-title">Як відбувається ремонт</h2>
            <p>Чотири послідовні кроки від приймання техніки до видачі готового замовлення.</p>
          </div>
        </div>

        <ol class="workflow-grid workflow-4">
          <li>
            <span class="mono step-num">01</span>
            <h3>Приймання та паспорт</h3>
            <p>Реєструємо пристрій за серійним номером, фіксуємо стан і комплектацію та формуємо PDF-квитанцію.</p>
          </li>
          <li>
            <span class="mono step-num">02</span>
            <h3>Діагностика й кошторис</h3>
            <p>Майстер визначає несправність, додає потрібні роботи та резервує запчастини зі складу.</p>
          </li>
          <li>
            <span class="mono step-num">03</span>
            <h3>Погодження вартості</h3>
            <p>Ви переглядаєте детальний кошторис в особистому кабінеті та підтверджуєте початок ремонту онлайн.</p>
          </li>
          <li>
            <span class="mono step-num">04</span>
            <h3>Ремонт і гарантія</h3>
            <p>Виконуємо ремонт, оновлюємо характеристики в паспорті та надаємо гарантійний талон у PDF.</p>
          </li>
        </ol>

        <div class="faq-block">
          <h3>Часті запитання</h3>
          <div class="faq-list">
            <div v-for="(item, idx) in faqs" :key="item.q" class="faq-item" :class="{ open: openFaq === idx }">
              <button type="button" class="faq-question" :aria-expanded="openFaq === idx" @click="openFaq = openFaq === idx ? -1 : idx">
                <span>{{ item.q }}</span>
                <ChevronDown :size="17" class="faq-chevron" />
              </button>
              <div v-if="openFaq === idx" class="faq-answer">
                <p>{{ item.a }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer id="contacts" class="site-footer">
      <div class="wrap footer-grid">
        <div class="footer-col">
          <RouterLink class="brand footer-brand" to="/">
            <img src="/mark.svg" alt="" width="26" height="26" />
            TechDesk
          </RouterLink>
          <p class="footer-desc">
            Сервісний центр комп’ютерної та цифрової техніки з підсистемами електронної паспортизації пристроїв та обліку ремонтних робіт.
          </p>
        </div>

        <div class="footer-col">
          <h3>Навігація</h3>
          <ul class="footer-links">
            <li><a href="#services">Послуги та ціни</a></li>
            <li><a href="#advantages">Переваги сервісу</a></li>
            <li><a href="#workflow">Етапи роботи та FAQ</a></li>
            <li><RouterLink to="/login">Особистий кабінет</RouterLink></li>
          </ul>
        </div>

        <div class="footer-col">
          <h3>Техніка</h3>
          <ul class="footer-links">
            <li>Ноутбуки та ультрабуки</li>
            <li>Стаціонарні ПК і станції</li>
            <li>Смартфони та планшети</li>
            <li>Моноблоки та монітори</li>
            <li>Смарт-годинники та консолі</li>
          </ul>
        </div>

        <div class="footer-col">
          <h3>Контакти</h3>
          <ul class="footer-contacts">
            <li>
              <MapPin :size="15" />
              <span>м. Київ, вул. Політехнічна, 14</span>
            </li>
            <li>
              <Phone :size="15" />
              <span class="mono">+380 (44) 290-45-18</span>
            </li>
            <li>
              <Phone :size="15" />
              <span class="mono">+380 (67) 510-22-90</span>
            </li>
            <li>
              <Clock :size="15" />
              <span>Пн–Пт: 09:00–19:00, Сб: 10:00–17:00</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="wrap footer-bottom">
        <span>© 2026 Сервісний центр TechDesk.</span>
        <span class="mono">Паспортизація техніки · Облік робіт · Склад · PDF-документи</span>
      </div>
    </footer>
  </div>
</template>
