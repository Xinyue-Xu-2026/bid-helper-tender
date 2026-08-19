<script setup>
import { computed, onMounted, ref } from 'vue'
import { getCompliance, setCompliance } from '../api'

const props = defineProps({ projectId: Number })
const data = ref({ items: [], total: 0, checked: 0 })

const percent = computed(() =>
  data.value.total ? Math.round((data.value.checked / data.value.total) * 100) : 0)

async function load() { data.value = await getCompliance(props.projectId) }

async function onCheck(row, val) { await setCompliance(row.id, val); load() }

onMounted(load)
</script>

<template>
  <el-progress :percentage="percent" style="margin-bottom: 16px; max-width: 400px" />
  <p>已核对 {{ data.checked }} / {{ data.total }} 项（废标项与资质门槛）</p>
  <el-table :data="data.items" max-height="55vh">
    <el-table-column label="核对" width="70">
      <template #default="{ row }">
        <el-checkbox :model-value="row.checked" @change="v => onCheck(row, v)" />
      </template>
    </el-table-column>
    <el-table-column prop="category" label="分类" width="100">
      <template #default="{ row }">
        <el-tag :type="row.category === '废标项' ? 'danger' : 'warning'">{{ row.category }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="content" label="内容" show-overflow-tooltip />
    <el-table-column prop="source" label="来源" width="110" />
    <el-table-column prop="checked_at" label="核对时间" width="170">
      <template #default="{ row }">{{ row.checked_at ? row.checked_at.slice(0, 16).replace('T', ' ') : '' }}</template>
    </el-table-column>
  </el-table>
</template>
