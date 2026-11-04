<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import Chart from 'chart.js/auto'
const props=defineProps({ type:String, data:Object, label:String, tall:Boolean })
const canvas=ref(null)
let chart
function render(){
  chart?.destroy()
  if(!canvas.value)return
  chart=new Chart(canvas.value,{
    type:props.type,data:props.data,
    options:{
      responsive:true,maintainAspectRatio:false,locale:'uk-UA',animation:false,
      plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:8,color:'#516078',padding:12}}},
      ...(props.type!=='doughnut'?{scales:{x:{grid:{display:false},ticks:{color:'#64748b'}},y:{beginAtZero:true,ticks:{color:'#64748b'},grid:{color:'#edf1f8'}}}}:{cutout:'65%'}),
    },
  })
}
onMounted(render)
watch(()=>props.data,()=>nextTick(render),{deep:true})
onUnmounted(()=>chart?.destroy())
</script>
<template><div class="chart-box" :class="{tall}"><canvas ref="canvas" role="img" :aria-label="label"></canvas></div></template>
