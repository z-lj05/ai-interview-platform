import api from './request'

// 简历接口：上传简历 + 查询解析详情（轮询用）
// （getResumes 列表无页面用，不搭）

export function uploadResume(file, targetPosition) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('target_position', targetPosition)
  return api.post('/resumes/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

export function getResume(resumeId) {
  return api.get(`/resumes/${resumeId}`)
}
