<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import Chart from 'chart.js/auto'
import { cssVar, resolved } from '../theme'
const props = defineProps({ type: String, data: Object, label: String, tall: Boolean })
const canvas = ref(null)
let chart
function render() {
  chart?.destroy()
  if (!canvas.value) return
  const text = cssVar('--chart-text'),
    grid = cssVar('--chart-grid')
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily
  chart = new Chart(canvas.value, {
    type: props.type,
    data: props.data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      locale: 'uk-UA',
      animation: false,
      plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, color: text, padding: 12 } } },
      ...(props.type !== 'doughnut'
        ? {
            scales: {
              x: { grid: { display: false }, ticks: { color: text } },
              y: { beginAtZero: true, ticks: { color: text }, grid: { color: grid }, border: { color: grid } },
            },
          }
        : { cutout: '65%' }),
    },
  })
}
onMounted(render)
watch(
  () => props.data,
  () => nextTick(render),
  { deep: true },
)
watch(resolved, () => nextTick(render))
onUnmounted(() => chart?.destroy())
</script>
<template>
  <div class="chart-box" :class="{ tall }"><canvas ref="canvas" role="img" :aria-label="label"></canvas></div>
</template>
