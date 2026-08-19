<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, saveSettings, testSettings } from '../api'

const form = ref({ api_key: '', model: 'kimi-k2.6' })
const testing = ref(false)

onMounted(async () => { form.value = await getSettings() })

async function save() {
  await saveSettings(form.value)
  ElMessage.success('已保存')
}

async function test() {
  testing.value = true
  try {
    const r = await testSettings()
    r.ok ? ElMessage.success(r.message) : ElMessage.error(r.message)
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <h2>设置</h2>
  <el-form :model="form" label-width="120px" style="max-width: 600px">
    <el-form-item label="Kimi API Key">
      <el-input v-model="form.api_key" type="password" show-password
                placeholder="sk-... 或 sk-kimi-..." />
    </el-form-item>
    <el-form-item label="解析模型">
      <el-input v-model="form.model" />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="save">保存</el-button>
      <el-button :loading="testing" @click="test">测试连接</el-button>
    </el-form-item>
  </el-form>
</template>
