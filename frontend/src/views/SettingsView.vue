<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import {
  getFieldConfig, getImportSettings, getSettings, saveFieldConfig, saveImportSettings,
  saveSettings, testSettings,
} from '../api'

const form = ref({ api_key: '', model: 'kimi-k3' })
const testing = ref(false)

onMounted(async () => {
  form.value = await getSettings()
  loadImportSettings()
  loadFieldConfig()
})

async function save() {
  try {
    await saveSettings(form.value)
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  }
}

async function test() {
  testing.value = true
  try {
    const r = await testSettings({ api_key: form.value.api_key, model: form.value.model })
    r.ok ? ElMessage.success(r.message) : ElMessage.error(r.message)
  } finally {
    testing.value = false
  }
}

// ---------- 资料导入配置 ----------
const DEFAULT_PERSON_MAPPING = {
  姓名: 'name', 部门: '部门', 职称: '职称', 联系方式: '联系方式',
  类型: '类型', 编号: '编号', 专业: '专业', 执业时间: '执业时间', 有效期至: '有效期至',
}
const DEFAULT_CONTRACT_MAPPING = {
  项目名称: '项目名称', 项目经理: '项目经理', 合同金额: '合同金额', 年份: '年份', 甲方: '甲方',
}

const importForm = ref({ shared_folder: '', llm_extract_enabled: false })
const personRows = ref([])
const contractRows = ref([])
const importSaving = ref(false)

function mappingToRows(mapping, defaults) {
  const source = mapping && Object.keys(mapping).length ? mapping : defaults
  return Object.entries(source).map(([excel, field]) => ({ excel, field }))
}

function rowsToMapping(rows) {
  const mapping = {}
  for (const r of rows) {
    if (r.excel && r.field) mapping[r.excel] = r.field
  }
  return mapping
}

async function loadImportSettings() {
  try {
    const r = await getImportSettings()
    importForm.value = {
      shared_folder: r?.shared_folder || '',
      llm_extract_enabled: !!r?.llm_extract_enabled,
    }
    personRows.value = mappingToRows(r?.person_mapping, DEFAULT_PERSON_MAPPING)
    contractRows.value = mappingToRows(r?.contract_mapping, DEFAULT_CONTRACT_MAPPING)
  } catch {
    // 后端未就绪时也给一份默认映射，方便直接编辑
    personRows.value = mappingToRows(null, DEFAULT_PERSON_MAPPING)
    contractRows.value = mappingToRows(null, DEFAULT_CONTRACT_MAPPING)
  }
}

async function saveImport() {
  importSaving.value = true
  try {
    await saveImportSettings({
      shared_folder: importForm.value.shared_folder,
      person_mapping: rowsToMapping(personRows.value),
      contract_mapping: rowsToMapping(contractRows.value),
      llm_extract_enabled: importForm.value.llm_extract_enabled,
    })
    ElMessage.success('导入配置已保存')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    importSaving.value = false
  }
}

// ---------- 资产字段配置 ----------
const FIELD_TYPES = [
  { value: 'text', label: '文本' },
  { value: 'date', label: '日期' },
  { value: 'dropdown', label: '下拉' },
]

const fieldTab = ref('person')
const personFields = ref([])
const contractFields = ref([])
const fieldSaving = ref(false)

const fieldRows = computed(() => fieldTab.value === 'person' ? personFields.value : contractFields.value)

function normalizeFieldRows(list) {
  return (list || []).map(f => ({
    key: f.key || '',
    type: ['text', 'date', 'dropdown'].includes(f.type) ? f.type : 'text',
    options: Array.isArray(f.options) ? [...f.options] : [],
    optionInput: '',
  }))
}

async function loadFieldConfig() {
  try {
    const r = await getFieldConfig()
    personFields.value = normalizeFieldRows(r?.person)
    contractFields.value = normalizeFieldRows(r?.contract)
  } catch {
    // 后端未就绪时留空，可从零开始配置
  }
}

function moveFieldRow(index, dir) {
  const rows = fieldRows.value
  const j = index + dir
  if (j < 0 || j >= rows.length) return
  const [row] = rows.splice(index, 1)
  rows.splice(j, 0, row)
}

function addFieldOption(row) {
  const v = (row.optionInput || '').trim()
  if (!v) return
  if (!row.options.includes(v)) row.options.push(v)
  row.optionInput = ''
}

async function saveFields() {
  fieldSaving.value = true
  try {
    const clean = rows => rows
      .filter(r => r.key.trim())
      .map(r => ({ key: r.key.trim(), type: r.type, options: r.type === 'dropdown' ? r.options : [] }))
    await saveFieldConfig({ person: clean(personFields.value), contract: clean(contractFields.value) })
    // 标记字段配置已更新，资产库进入时据此重新拉取（见 AssetsView）
    localStorage.setItem('fieldConfigUpdatedAt', String(Date.now()))
    ElMessage.success('字段配置已保存')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    fieldSaving.value = false
  }
}
</script>

<template>
  <h2>设置</h2>
  <el-card style="max-width: 720px; margin-bottom: 16px">
    <template #header>模型设置</template>
    <el-form :model="form" label-width="120px">
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
  </el-card>

  <el-card style="max-width: 720px; margin-bottom: 16px">
    <template #header>资料导入配置</template>
    <el-form label-width="120px">
      <el-form-item label="共享文件夹路径">
        <el-input v-model="importForm.shared_folder"
                  placeholder="例如 \\server\shared\投标资料 或 D:\投标资料" />
      </el-form-item>
      <el-form-item label="人员资质列名">
        <div class="mapping-table">
          <div class="mapping-tip">Excel 列名 → 入库字段名</div>
          <el-table :data="personRows" size="small">
            <el-table-column label="Excel 列名">
              <template #default="{ row }">
                <el-input v-model="row.excel" size="small" placeholder="如：姓名" />
              </template>
            </el-table-column>
            <el-table-column label="字段名">
              <template #default="{ row }">
                <el-input v-model="row.field" size="small" placeholder="如：name" />
              </template>
            </el-table-column>
            <el-table-column label="" width="70">
              <template #default="{ $index }">
                <el-button size="small" type="danger" link
                           @click="personRows.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button size="small" style="margin-top: 8px"
                     @click="personRows.push({ excel: '', field: '' })">添加一行</el-button>
        </div>
      </el-form-item>
      <el-form-item label="合同业绩列名">
        <div class="mapping-table">
          <div class="mapping-tip">Excel 列名 → 入库字段名</div>
          <el-table :data="contractRows" size="small">
            <el-table-column label="Excel 列名">
              <template #default="{ row }">
                <el-input v-model="row.excel" size="small" placeholder="如：项目名称" />
              </template>
            </el-table-column>
            <el-table-column label="字段名">
              <template #default="{ row }">
                <el-input v-model="row.field" size="small" placeholder="如：项目名称" />
              </template>
            </el-table-column>
            <el-table-column label="" width="70">
              <template #default="{ $index }">
                <el-button size="small" type="danger" link
                           @click="contractRows.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button size="small" style="margin-top: 8px"
                     @click="contractRows.push({ excel: '', field: '' })">添加一行</el-button>
        </div>
      </el-form-item>
      <el-form-item label="LLM 智能抽取">
        <div>
          <el-switch v-model="importForm.llm_extract_enabled" />
          <div class="mapping-tip">开启后用大模型从证件、合同中抽取字段（需配置 LLM API，内网可能不可用）</div>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="importSaving" @click="saveImport">保存导入配置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card style="max-width: 920px">
    <template #header>资产字段配置</template>
    <div class="mapping-tip" style="margin-bottom: 10px">
      配置资产库中「常用人员」表格列与表单字段，以及人员业绩的展示字段；字段顺序即表格列顺序。
    </div>
    <el-tabs v-model="fieldTab">
      <el-tab-pane label="人员字段" name="person" />
      <el-tab-pane label="合同字段" name="contract" />
    </el-tabs>
    <el-table :data="fieldRows" size="small">
      <el-table-column label="排序" width="90" align="center">
        <template #default="{ $index }">
          <el-button size="small" link :icon="ArrowUp" :disabled="$index === 0"
                     @click="moveFieldRow($index, -1)" />
          <el-button size="small" link :icon="ArrowDown" :disabled="$index === fieldRows.length - 1"
                     @click="moveFieldRow($index, 1)" />
        </template>
      </el-table-column>
      <el-table-column label="字段名" width="180">
        <template #default="{ row }">
          <el-input v-model="row.key" size="small" placeholder="如：职称" />
        </template>
      </el-table-column>
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-select v-model="row.type" size="small">
            <el-option v-for="t in FIELD_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="选项">
        <template #default="{ row }">
          <div v-if="row.type === 'dropdown'" class="option-editor">
            <el-tag v-for="(opt, i) in row.options" :key="opt" size="small" closable
                    style="margin: 2px 6px 2px 0"
                    @close="row.options.splice(i, 1)">{{ opt }}</el-tag>
            <el-input v-model="row.optionInput" size="small" placeholder="输入后回车添加"
                      style="width: 140px"
                      @keyup.enter="addFieldOption(row)" />
            <el-button size="small" link type="primary" @click="addFieldOption(row)">添加</el-button>
          </div>
          <span v-else style="color: #c0c4cc; font-size: 12px">仅下拉类型需要选项</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="70">
        <template #default="{ $index }">
          <el-button size="small" type="danger" link
                     @click="fieldRows.splice($index, 1)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-button size="small" style="margin-top: 8px"
               @click="fieldRows.push({ key: '', type: 'text', options: [], optionInput: '' })">添加一行</el-button>
    <div style="margin-top: 16px">
      <el-button type="primary" :loading="fieldSaving" @click="saveFields">保存字段配置</el-button>
    </div>
  </el-card>
</template>

<style scoped>
.mapping-table { width: 100%; }
.mapping-tip { margin-bottom: 6px; color: #909399; font-size: 12px; }
.option-editor { display: flex; flex-wrap: wrap; align-items: center; }
</style>
