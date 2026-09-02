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
export const importAssets = (type, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/assets/import`, fd, { params: { type } }).then(r => r.data)
}
export const getExpiring = (days = 30) => api.get('/assets/expiring', { params: { days } }).then(r => r.data)

// 资产字段配置：{ person: [{ key, type, options }], contract: [...] }
export const getFieldConfig = () => api.get('/assets/field-config').then(r => r.data)
export const saveFieldConfig = (data) => api.put('/assets/field-config', data).then(r => r.data)
// 下载 Excel 导入模板（type: person | contract），浏览器直接触发下载
export const downloadImportTemplate = (type) =>
  window.open(`/api/assets/import-template?type=${type}`, '_blank')

// 废标核对
export const getCompliance = (pid) => api.get(`/projects/${pid}/compliance`).then(r => r.data)
export const setCompliance = (rid, checked) => api.put(`/compliance/${rid}`, { checked }).then(r => r.data)

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
// 证书级到期明细（首页提醒条）：[{ type, asset_name, cert_type, cert_name, expiry_date, days_left }]
export const getExpiringDetail = (days = 30) => api.get('/assets/expiring-detail', { params: { days } }).then(r => r.data)
