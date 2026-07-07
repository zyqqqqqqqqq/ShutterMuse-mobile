import { BASE_URL } from '../config.js'

const IS_CLOUD = /^https?:\/\//i.test(BASE_URL) && !/192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\./.test(BASE_URL)
/** 云端推理+上传：1 小时（毫秒） */
const CLOUD_UPLOAD_TIMEOUT_MS = 60 * 60 * 1000
const LOCAL_UPLOAD_TIMEOUT_MS = 90 * 1000

function networkHint() {
  if (IS_CLOUD) {
    return '无法连接云服务器。请检查：① AutoDL 实例是否运行中 ② Server 是否监听 6006 端口 ③ 自定义服务地址是否正确 ④ 稍后重试'
  }
  return '无法连接服务器。请检查：① Server 是否已启动 ② 手机与电脑同一 Wi-Fi（可关 4G/5G）③ IP 是否正确'
}

/**
 * 上传图片到 ShutterMuse API
 * @param {string} path API path e.g. /v1/composition
 * @param {string} filePath 本地临时图片路径
 */
function uploadImage(path, filePath) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE_URL}${path}`,
      filePath,
      name: 'image',
      timeout: IS_CLOUD ? CLOUD_UPLOAD_TIMEOUT_MS : LOCAL_UPLOAD_TIMEOUT_MS,
      success: (res) => {
        const text = res.data || ''
        if (res.statusCode !== 200) {
          try {
            const err = JSON.parse(text)
            const code = err.error?.code || ''
            const message = err.error?.message || `HTTP ${res.statusCode}`
            reject(new Error(code ? `${code}: ${message}` : message))
          } catch {
            reject(new Error(`HTTP ${res.statusCode}: ${text}`))
          }
          return
        }
        try {
          resolve(JSON.parse(text))
        } catch {
          reject(new Error('响应解析失败'))
        }
      },
      fail: (err) => {
        const msg = err.errMsg || '网络请求失败'
        if (msg.includes('statusCode: null') || msg.includes('timeout')) {
          reject(new Error(networkHint()))
        } else {
          reject(new Error(msg))
        }
      }
    })
  })
}

export function analyzeComposition(filePath) {
  return uploadImage('/v1/composition', filePath)
}

export function analyzePose(filePath) {
  return uploadImage('/v1/pose', filePath)
}

export function checkHealth(retries = 2) {
  const attempt = (left) => new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}/health`,
      timeout: IS_CLOUD ? 30000 : 10000,
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.data)
          return
        }
        try {
          const err = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
          const code = err?.error?.code || ''
          const message = err?.error?.message || `HTTP ${res.statusCode}`
          reject(new Error(code ? `${code}: ${message}` : message))
        } catch {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail: (err) => {
        const msg = err.errMsg || '连接失败'
        if (left > 1 && (msg.includes('statusCode: null') || msg.includes('timeout') || msg.includes('fail'))) {
          setTimeout(() => {
            attempt(left - 1).then(resolve).catch(reject)
          }, 1500)
          return
        }
        if (msg.includes('statusCode: null') || msg.includes('timeout') || msg.includes('fail')) {
          reject(new Error(networkHint()))
        } else {
          reject(new Error(msg))
        }
      }
    })
  })
  return attempt(retries)
}
