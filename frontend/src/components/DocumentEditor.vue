<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getBidDocument, saveBidDocument } from '../api'

const props = defineProps({ projectId: Number })
const emit = defineEmits(['close'])

const loading = ref(false)
const saving = ref(false)
const noDraft = ref(false)
const blocks = ref([])

async function load() {
  loading.value = true
  try {
    const data = await getBidDocument(props.projectId)
    blocks.value = data.blocks || []
    noDraft.value = false
  } catch (e) {
    noDraft.value = true
    blocks.value = []
  } finally {
    loading.value = false
  }
}

function buildSnapshot() {
  const paragraphs = {}
  const tables = {}
  for (const b of blocks.value) {
    if (b.kind === 'paragraph') {
      paragraphs[b.index] = b.text ?? ''
    } else {
      tables[b.index] = b.rows.map(row =>
        row.map(c => (c.origin ? (c.text ?? '') : '')))
    }
  }
  return { paragraphs, tables }
}

async function save() {
  saving.value = true
  try {
    const res = await saveBidDocument(props.projectId, buildSnapshot())
    blocks.value = res.blocks || blocks.value
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

async function cloneTable(tableIndex) {
  saving.value = true
  try {
    const res = await saveBidDocument(props.projectId, {
      ...buildSnapshot(),
      clones: [{ table_index: tableIndex, count: 1 }],
    })
    blocks.value = res.blocks || blocks.value
    ElMessage.success('已复制本表')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-dialog title="编辑底稿内容" width="920px" top="4vh"
             :model-value="true" @update:model-value="v => { if (!v) emit('close') }">
    <div v-loading="loading">
      <el-alert v-if="noDraft" type="info" :closable="false"
                title="尚无底稿，请先生成或上传底稿" />
      <div v-else class="editor-blocks">
        <div v-for="b in blocks" :key="b.kind + '-' + b.index" class="editor-block">
          <div v-if="b.kind === 'paragraph'" class="editor-para">
            <el-input v-model="b.text" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }"
                      placeholder="（空段落）" />
          </div>
          <div v-else class="editor-table">
            <div class="editor-table-bar">
              <span class="editor-table-title">表格 #{{ b.index }}（{{ b.ncols }} 列）</span>
              <el-button size="small" @click="cloneTable(b.index)">复制本表</el-button>
            </div>
            <table class="editor-grid">
              <tbody>
                <tr v-for="(row, ri) in b.rows" :key="ri">
                  <td v-for="(cell, ci) in row" :key="ci"
                      :colspan="cell.colspan" :rowspan="cell.rowspan"
                      :class="{ 'cell-origin': cell.origin }">
                    <el-input v-if="cell.origin" v-model="cell.text" type="textarea"
                              :autosize="{ minRows: 1, maxRows: 4 }" />
                    <span v-else class="cell-continue">{{ cell.text }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="emit('close')">关闭</el-button>
      <el-button type="primary" :loading="saving" :disabled="noDraft" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.editor-blocks { max-height: 65vh; overflow-y: auto; }
.editor-block { margin-bottom: 12px; }
.editor-para { border-left: 3px solid #d9ecff; padding-left: 8px; }
.editor-table-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.editor-table-title { font-size: 13px; font-weight: 600; color: #303133; }
.editor-grid { border-collapse: collapse; width: 100%; }
.editor-grid td { border: 1px solid #dcdfe6; padding: 2px; vertical-align: top; min-width: 60px; }
.editor-grid td.cell-origin { background: #fff; }
.editor-grid .cell-continue { color: #909399; font-size: 12px; }
</style>
