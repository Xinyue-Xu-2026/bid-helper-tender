import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

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
export const testSettings = () => api.post('/settings/test').then(r => r.data)
