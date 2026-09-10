import axios from 'axios'
import { ElMessage } from 'element-plus'

export const api = axios.create({ baseURL: '/api' })

// 全局响应拦截器：统一错误提示（覆盖各页无错误处理的情况）
api.interceptors.response.use(
  r => r,
  err => {
    const detail = err?.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : (err?.message || '请求失败')
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

// 项目
export const listProjects = () => api.get('/projects').then(r => r.data)
export const createProject = (data) => api.post('/projects', data).then(r => r.data)
export const getProject = (id) => api.get(`/projects/${id}`).then(r => r.data)
export const updateProject = (id, data) => api.put(`/projects/${id}`, data).then(r => r.data)
export const deleteProject = (id) => api.delete(`/projects/${id}`).then(r => r.data)
export const uploadTender = (id, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/projects/${id}/tender`, fd).then(r => r.data)
}

// 要求
export const getRequirements = (pid, params = {}) =>
  api.get(`/projects/${pid}/requirements`, { params }).then(r => r.data)
export const updateRequirement = (id, data) => api.put(`/requirements/${id}`, data).then(r => r.data)
export const deleteRequirement = (id) => api.delete(`/requirements/${id}`).then(r => r.data)
export const exportUrl = (pid) => `/api/projects/${pid}/requirements/export`

// 资产
export const listAssets = (type) => api.get('/assets', { params: { type } }).then(r => r.data)
export const createAsset = (data) => api.post('/assets', data).then(r => r.data)
export const updateAsset = (id, data) => api.put(`/assets/${id}`, data).then(r => r.data)
export const deleteAsset = (id) => api.delete(`/assets/${id}`).then(r => r.data)
export const uploadAssetFile = (id, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/assets/${id}/file`, fd).then(r => r.data)
}
// 人员分类图片（职称证书/社保缴纳证明/身份证）
export const uploadPersonImage = (id, category, file) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('category', category)
  return api.post(`/assets/${id}/person-image`, fd).then(r => r.data)
}
// 每本证书扫描件
export const uploadCertImage = (id, certIndex, file) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('cert_index', certIndex)
  return api.post(`/assets/${id}/cert-image`, fd).then(r => r.data)
}
// 图片预览 URL（带缓存戳避免上传后不刷新）
export const personImageUrl = (id, category) => `/api/assets/${id}/image/${category}`
export const certImageUrl = (id, certIndex) => `/api/assets/${id}/cert-image/${certIndex}`
export const importAssets = (type, file, subtype) => {
  const fd = new FormData()
  fd.append('file', file)
  const params = { type }
  if (subtype) params.subtype = subtype
  return api.post(`/assets/import`, fd, { params }).then(r => r.data)
}
export const getExpiring = (days = 30) => api.get('/assets/expiring', { params: { days } }).then(r => r.data)

// 资产字段配置：{ person: [{ key, type, options }], contract: [...] }
export const getFieldConfig = () => api.get('/assets/field-config').then(r => r.data)
export const saveFieldConfig = (data) => api.put('/assets/field-config', data).then(r => r.data)
// 下载 Excel 导入模板（type: person | contract；contract 需带 subtype 子类型，如 ?type=contract&subtype=编标）
export const downloadImportTemplate = (type, subtype) =>
  window.open(`/api/assets/import-template?type=${type}${subtype ? `&subtype=${encodeURIComponent(subtype)}` : ''}`, '_blank')

// 废标核对
export const getCompliance = (pid) => api.get(`/projects/${pid}/compliance`).then(r => r.data)
export const setCompliance = (rid, checked) => api.put(`/compliance/${rid}`, { checked }).then(r => r.data)
// AI 判定：requirement_ids 为空数组表示判定所有「需人工确认」项
export const aiCheckCompliance = (pid, requirementIds = []) =>
  api.post(`/projects/${pid}/compliance/ai-check`, { requirement_ids: requirementIds }).then(r => r.data)

// 设置
export const getSettings = () => api.get('/settings').then(r => r.data)
export const saveSettings = (data) => api.put('/settings', data).then(r => r.data)
export const testSettings = (data) => api.post('/settings/test', data).then(r => r.data)

// 模板
export const listTemplates = () => api.get('/templates').then(r => r.data)
// 多文件上传：字段名 files，返回 { items: [...], errors: [{ filename, reason }] }
export const uploadTemplates = (files) => {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  return api.post('/templates', fd).then(r => r.data)
}
export const analyzeTemplate = (id) => api.post(`/templates/${id}/analyze`).then(r => r.data)
export const deleteTemplate = (id) => api.delete(`/templates/${id}`).then(r => r.data)

// 资料
export const listMaterials = (pid) => api.get(`/projects/${pid}/materials`).then(r => r.data)
export const uploadMaterials = (pid, files) => {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  return api.post(`/projects/${pid}/materials`, fd).then(r => r.data)
}
export const deleteMaterial = (id) => api.delete(`/materials/${id}`).then(r => r.data)

// 共享文件夹导入
export const getImportSettings = () => api.get('/import/settings').then(r => r.data)
export const saveImportSettings = (data) => api.put('/import/settings', data).then(r => r.data)
export const scanImport = () => api.post('/import/scan').then(r => r.data)
export const confirmImport = (items) => api.post('/import/confirm', { items }).then(r => r.data)

// 章节与编写
export const getSections = (pid) => api.get(`/projects/${pid}/sections`).then(r => r.data)
export const createSection = (pid, data) => api.post(`/projects/${pid}/sections`, data).then(r => r.data)
export const updateSection = (id, data) => api.put(`/sections/${id}`, data).then(r => r.data)
export const deleteSection = (id) => api.delete(`/sections/${id}`).then(r => r.data)
export const generateOutline = (pid) => api.post(`/projects/${pid}/outline`).then(r => r.data)
// 按模板标题结构生成章节；422 表示模板无标题结构
export const sectionsFromTemplate = (pid, templateId) =>
  api.post(`/projects/${pid}/sections/from-template`, { template_id: templateId }).then(r => r.data)
// AI 将模板章节标题改写为贴合本项目的标题；502 表示改写失败
export const sectionsAdaptTitles = (pid) =>
  api.post(`/projects/${pid}/sections/adapt-titles`).then(r => r.data)
export const sectionGenerateUrl = (pid, sid, { assetIds, materialIds, templateId }) => {
  const qs = new URLSearchParams()
  if (assetIds.length) qs.set('asset_ids', assetIds.join(','))
  if (materialIds.length) qs.set('material_ids', materialIds.join(','))
  if (templateId) qs.set('templateId', templateId)
  return `/api/projects/${pid}/sections/${sid}/generate?${qs.toString()}`
}
export const exportWordUrl = (pid, templateId) =>
  `/api/projects/${pid}/export${templateId ? `?template_id=${templateId}` : ''}`

// 保格式仿写
export const mimicPlan = (pid, templateId) =>
  api.post(`/projects/${pid}/mimic/plan`, { template_id: templateId }).then(r => r.data)
export const mimicApply = (pid, templateId, ops) =>
  api.post(`/projects/${pid}/mimic/apply`, { template_id: templateId, ops }).then(r => r.data)
export const mimicDownloadUrl = (pid, file) =>
  `/api/projects/${pid}/mimic/download?file=${encodeURIComponent(file)}`

// 商务标
export const getBidAssets = (pid) => api.get(`/projects/${pid}/bid-assets`).then(r => r.data)
export const saveBidAssets = (pid, data) => api.put(`/projects/${pid}/bid-assets`, data).then(r => r.data)
export const bidExportUrl = (pid, format) => `/api/projects/${pid}/bid-assets/export?format=${format}`
// 商务标模板导出：payload { persons: [{asset_id, is_lead}], contracts: [{asset_id, section}],
//   project_no, project_name, doc_date, tenderer, bidder_name, legal_rep_id, agent_id,
//   section_name, section_no }（标段名称/标段编号可选，用于占位符填充）
// 返回完整响应（blob + headers），调用方从 Content-Disposition 取文件名；
// 有底稿时响应头带 X-Fill-Report（URL 编码的 fill_report JSON），旧模板路径无此头
export const exportBidTemplate = (pid, payload) =>
  api.post(`/projects/${pid}/bid-assets/export-template`, payload, { responseType: 'blob' })
// 占位符预览：body {project_no, project_name, doc_date, tenderer, bidder_name, section_name, section_no}（均可空）
// 返回 { matched: [{label, value, count, kind}], suspicious: [{text}] }；无底稿时后端报错，调用方需优雅降级
export const previewBidPlaceholders = (pid, payload) =>
  api.post(`/projects/${pid}/bid-draft/placeholders`, payload).then(r => r.data)
// 商务标底稿：headings 供手动选择裁切起止（suggested 为自动定位建议，可能为 null）
export const getBidDraftHeadings = (pid) => api.get(`/projects/${pid}/bid-draft/headings`).then(r => r.data)
// 生成底稿：body {start_heading, end_heading}，空=自动定位/到末尾；422=未识别格式章节需手动起止
export const generateBidDraft = (pid, data) => api.post(`/projects/${pid}/bid-draft/generate`, data).then(r => r.data)
export const uploadBidDraft = (pid, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/projects/${pid}/bid-draft/upload`, fd).then(r => r.data)
}
// 有底稿返回预览对象；无底稿返回 { draft: null }
export const getBidDraft = (pid) => api.get(`/projects/${pid}/bid-draft`).then(r => r.data)
// 绑定保存：tables 每行 { table_index, role, columns, person_scope, perf_scope, label_kind,
//   person, confirmed, header_rows(1..4 表头行数), mode('' 或 'per_person'，简历表每人一张) }
export const saveBidDraftBindings = (pid, data) => api.put(`/projects/${pid}/bid-draft/bindings`, data).then(r => r.data)
// 占位符同义词映射（设置页用）：{ 别名: 标准标签 }
export const getPlaceholderSynonyms = () => api.get('/settings/placeholder-synonyms').then(r => r.data)
export const savePlaceholderSynonyms = (mapping) => api.put('/settings/placeholder-synonyms', mapping).then(r => r.data)
// 证书级到期明细（首页提醒条）：[{ type, asset_name, cert_type, cert_name, expiry_date, days_left }]
export const getExpiringDetail = (days = 30) => api.get('/assets/expiring-detail', { params: { days } }).then(r => r.data)
