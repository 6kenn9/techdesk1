<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { Columns3, FileSpreadsheet, List, Plus, Search } from "lucide-vue-next";
import { api, download, query } from "../api";
import {
  ageLabel,
  byClosed,
  byUrgency,
  categories,
  date,
  isLate,
  money,
  statuses,
  workState,
} from "../domain";
import { useSession } from "../state";
import Stage from "../components/Stage.vue";
import OrderCard from "../components/OrderCard.vue";
const session = useSession();
const route = useRoute();
const isMaster = session.user.role === "master";
const filters = reactive({
  q: "",
  status: "",
  category: "",
  master_id: "",
  warranty_only: false,
  ...session.filters.orders,
});
if (isMaster) filters.master_id = "";
const items = ref([]),
  masters = ref([]),
  error = ref(""),
  board = ref(false);
const scope = ref(isMaster ? session.filters.ordersScope || "mine" : "all");
let request = 0;
async function exportCsv() {
  try {
    await download(
      "/orders/export.xlsx" + query(filters),
      `techdesk-заявки-${new Date().toISOString().slice(0, 10)}.xlsx`,
    );
  } catch (e) {
    session.notify(e.message, "error");
  }
}
const tabs = [
  [
    "work",
    "У роботі",
    (o) => workState(o) === "todo" && o.status !== "ready_for_pickup",
    "Заявки, у яких наступний крок за майстром.",
  ],
  [
    "client",
    "Чекають клієнта",
    (o) => workState(o) === "client",
    "Кошторис надіслано, потрібне рішення клієнта.",
  ],
  [
    "pickup",
    "До видачі",
    (o) => o.status === "ready_for_pickup" || o.status === "cancelled",
    "Пристрій чекає видачі або відправки: відремонтований чи повернення після скасування.",
  ],
  ["free", "Вільні", (o) => workState(o) === "free", "Заявки без майстра."],
  ["late", "Затримані", isLate, "Стоять на етапі довше за норму."],
  [
    "active",
    "Усі активні",
    (o) => workState(o) !== "archive",
    "Усе, що ще не закрито.",
  ],
  [
    "archive",
    "Архів",
    (o) => workState(o) === "archive",
    "Завершені заявки та пристрої, повернуті клієнту.",
  ],
];
const tabKeys = tabs.map(([key]) => key);
const defaultTab = isMaster ? "work" : "active";
const pick = (value) => (tabKeys.includes(value) ? value : null);
const quick = ref(
  pick(route.query.tab) || pick(session.filters.ordersQuick) || defaultTab,
);
watch(quick, (value) => {
  session.filters.ordersQuick = value;
});
watch(scope, (value) => {
  session.filters.ordersScope = value;
});
const inScope = (o) =>
  scope.value === "all" ||
  o.master_id === session.user.id ||
  workState(o) === "free";
const scoped = computed(() => items.value.filter(inScope));
const counts = computed(() =>
  Object.fromEntries(
    tabs.map(([key, , test]) => [key, scoped.value.filter(test).length]),
  ),
);
const tab = computed(() => tabs.find(([key]) => key === quick.value));
const shown = computed(() =>
  scoped.value
    .filter(tab.value[2])
    .sort(quick.value === "archive" ? byClosed : byUrgency),
);
const ageHead = computed(
  () =>
    ({ client: "Чекає рішення", pickup: "Чекає видачі", archive: "Закрито" })[
      quick.value
    ] || "На етапі",
);
function resetFilters() {
  Object.assign(filters, {
    q: "",
    status: "",
    category: "",
    master_id: "",
    warranty_only: false,
  });
  quick.value = defaultTab;
}
async function load() {
  const seq = ++request;
  try {
    const result = await api("/orders" + query(filters));
    if (seq === request) {
      items.value = result;
      error.value = "";
    }
  } catch (e) {
    if (seq === request) error.value = e.message;
  }
}
watch(filters, () => {
  session.filters.orders = { ...filters };
  load();
});
watch(
  () => route.query.tab,
  (value) => {
    if (pick(value)) quick.value = value;
  },
);
onMounted(async () => {
  load();
  if (isMaster) return;
  try {
    masters.value = await api("/users?role=master");
  } catch (e) {
    error.value = e.message;
  }
});
</script>
<template>
  <div class="page-head">
    <div class="page-title">
      <h1>Журнал заявок</h1>
      <span class="count">{{ shown.length }}</span>
    </div>
    <div class="actions">
      <div class="segmented" aria-label="Вигляд журналу">
        <button
          class="button small"
          :aria-pressed="!board"
          @click="board = false"
        >
          <List :size="16" />
          Таблиця
        </button>
        <button
          class="button small"
          :aria-pressed="board"
          @click="board = true"
        >
          <Columns3 :size="16" />
          Дошка
        </button>
      </div>
      <button
        class="button"
        type="button"
        title="Завантажити журнал з поточними фільтрами для Excel"
        @click="exportCsv"
      >
        <FileSpreadsheet :size="16" />
        Експорт
      </button>
      <RouterLink class="button primary" to="/orders/intake">
        <Plus :size="16" />
        Швидке приймання
      </RouterLink>
    </div>
  </div>
  <section>
    <div class="filters">
      <label class="input-icon">
        <Search :size="18" />
        <input
          v-model.trim="filters.q"
          aria-label="Пошук заявок"
          placeholder="Номер, пристрій або клієнт"
        />
      </label>
      <select v-model="filters.status" aria-label="Етап">
        <option value="">Усі етапи</option>
        <option v-for="(name, key) in statuses" :key="key" :value="key">
          {{ name }}
        </option>
      </select>
      <select v-model="filters.category" aria-label="Категорія пристрою">
        <option value="">Усі категорії</option>
        <option v-for="item in categories" :key="item">{{ item }}</option>
      </select>
      <select v-if="!isMaster" v-model="filters.master_id" aria-label="Майстер">
        <option value="">Усі майстри</option>
        <option v-for="item in masters" :key="item.id" :value="item.id">
          {{ item.full_name }}
        </option>
      </select>
      <label class="check">
        <input v-model="filters.warranty_only" type="checkbox" />
        Гарантійні
      </label>
      <div
        v-if="isMaster"
        class="segmented"
        role="group"
        aria-label="Чиї заявки показувати"
      >
        <button
          class="button small"
          type="button"
          :aria-pressed="scope === 'mine'"
          @click="scope = 'mine'"
        >
          Мої
        </button>
        <button
          class="button small"
          type="button"
          :aria-pressed="scope === 'all'"
          @click="scope = 'all'"
        >
          Усі майстри
        </button>
      </div>
    </div>
    <div class="quick-filters" role="group" aria-label="Розділи журналу">
      <button
        v-for="[key, label] in tabs"
        :key="key"
        type="button"
        class="quick-chip"
        :class="[key, { selected: quick === key }]"
        :aria-pressed="quick === key"
        :disabled="!counts[key] && quick !== key"
        @click="quick = key"
      >
        {{ label }}
        <span>{{ counts[key] }}</span>
      </button>
    </div>
    <p class="tab-hint">{{ tab[3] }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-else-if="!shown.length" class="empty">
      <p>У розділі «{{ tab[1] }}» заявок немає.</p>
      <button class="button" type="button" @click="resetFilters">
        Скинути фільтри й розділ
      </button>
    </div>
    <div v-else-if="board" class="kanban">
      <template v-for="(name, key) in statuses" :key="key">
        <section
          v-if="
            !['completed', 'returned'].includes(key) ||
            quick === 'archive' ||
            filters.status === key
          "
          class="kanban-col"
        >
          <h3>
            {{ name }}
            <span class="count">{{
              shown.filter((o) => o.status === key).length
            }}</span>
          </h3>
          <OrderCard
            v-for="item in shown.filter((o) => o.status === key)"
            :key="item.id"
            :item="item"
            show-master
          />
        </section>
      </template>
    </div>
    <div v-else class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Заявка</th>
            <th>Пристрій</th>
            <th>Клієнт</th>
            <th>Етап</th>
            <th>{{ ageHead }}</th>
            <th>Майстер</th>
            <th class="align-right">Сума</th>
            <th v-if="quick === 'archive'" class="align-right">Оцінка</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in shown" :key="item.id">
            <td>
              <RouterLink class="mono nowrap" :to="'/orders/' + item.id">{{
                item.order_number
              }}</RouterLink>
              <small>{{ date(item.created_at) }}</small>
            </td>
            <td>
              <strong>{{ item.device }}</strong>
              <small class="mono">{{
                item.serial_number || "S/N не вказано"
              }}</small>
            </td>
            <td>{{ item.client }}</td>
            <td>
              <Stage :status="item.status" />
              <small v-if="item.is_warranty_case">Гарантійний випадок</small>
            </td>
            <td class="nowrap" :class="{ 'stale-cell': isLate(item) }">
              {{
                workState(item) === "archive"
                  ? date(item.completed_at || item.updated_at)
                  : ageLabel(item.stage_since)
              }}
            </td>
            <td>{{ item.master || "Не призначено" }}</td>
            <td class="align-right mono nowrap">
              {{ money(item.total_cost) }}
            </td>
            <td v-if="quick === 'archive'" class="align-right mono nowrap">
              {{ item.rating ? item.rating + " / 5" : "—" }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
