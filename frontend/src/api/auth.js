import api from './request'

// 每个函数 = 一个后端接口的薄封装：只写"打哪个门牌、带什么货"
export function register(data) {
  return api.post('/auth/register', data)
}

export function login(email, password) {
  return api.post('/auth/login', { email, password })
}
