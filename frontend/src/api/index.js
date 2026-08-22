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

// 废标核对
export const getCompliance = (pid) => api.get(`/projects/${pid}/compliance`).then(r => r.data)
export const setCompliance = (rid, checked) => api.put(`/compliance/${rid}`, { checked }).then(r => r.data)

// 设置
export const getSettings = () => api.get('/settings').then(r => r.data)
export const saveSettings = (data) => api.put('/settings', data).then(r => r.data)
export const testSettings = (data) => api.post('/settings/test', data).then(r => r.data)

// 模板
export const listTemplates = () => api.get('/templates').then(r => r.data)
export const uploadTemplate = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/templates', fd, { params: { name: file.name } }).then(r => r.data)
}
export const analyzeTemplate = (id) => api.post(`/templates/${id}/analyze`).then(r => r.data)
export const deleteTemplate = (id) => api.delete(`/templates/${id}`).then(r => r.data)

// 资料
export const listMaterials = (pid) => api.get(`/projects/${pid}/materials`).then(r => r.data)
export const uploadMaterial = (pid, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/projects/${pid}/materials`, fd).then(r => r.data)
}
export const deleteMaterial = (id) => api.delete(`/materials/${id}`).then(r => r.data)

// 章节与编写
export const getSections = (pid) => api.get(`/projects/${pid}/sections`).then(r => r.data)
export const createSection = (pid, data) => api.post(`/projects/${pid}/sections`, data).then(r => r.data)
export const updateSection = (id, data) => api.put(`/sections/${id}`, data).then(r => r.data)
export const deleteSection = (id) => api.delete(`/sections/${id}`).then(r => r.data)
export const generateOutline = (pid) => api.post(`/projects/${pid}/outline`).then(r => r.data)
export const sectionGenerateUrl = (pid, sid, { assetIds, materialIds, reqIds }) => {
  const qs = new URLSearchParams()
  if (assetIds.length) qs.set('asset_ids', assetIds.join(','))
  if (materialIds.length) qs.set('material_ids', materialIds.join(','))
  if (reqIds.length) qs.set('req_ids', reqIds.join(','))
  return `/api/projects/${pid}/sections/${sid}/generate?${qs.toString()}`
}
export const exportWordUrl = (pid, templateId) =>
  `/api/projects/${pid}/export${templateId ? `?template_id=${templateId}` : ''}`
