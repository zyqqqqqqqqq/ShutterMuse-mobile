<template>
  <view class="page">
    <view class="header">
      <text class="title">ShutterMuse</text>
      <text class="subtitle">拍摄时构图指导 · 摄影师模式</text>
    </view>

    <view v-if="imagePath" class="preview-wrap">
      <view class="image-box">
        <image
          class="preview-image"
          :src="imagePath"
          mode="widthFix"
          @load="onImageLoad"
        />
        <view
          v-if="overlayStyle && result?.decision === 'refine'"
          class="bbox-overlay"
          :style="overlayStyle"
        />
      </view>
    </view>
    <view v-else class="placeholder">
      <text class="placeholder-text">请拍照或从相册选择图片</text>
    </view>

    <view v-if="statusText" class="status" :style="{ borderColor: statusColor }">
      <text class="status-text">{{ statusText }}</text>
      <text v-if="latencyMs" class="latency">耗时 {{ latencyMs }} ms</text>
    </view>

    <view class="actions">
      <button class="btn btn-secondary" :disabled="loading" @click="takePhoto">
        拍照
      </button>
      <button class="btn btn-secondary" :disabled="loading" @click="chooseAlbum">
        相册
      </button>
      <button class="btn btn-primary" :disabled="loading || !imagePath" @click="analyze">
        {{ loading ? '分析中…' : '分析构图' }}
      </button>
    </view>

    <view class="actions">
      <button class="btn btn-test" :disabled="testing" @click="testConnection">
        {{ testing ? '测试中…' : '测试服务器连接' }}
      </button>
    </view>

    <view class="hint">
      <text>服务器：{{ baseUrl }}</text>
      <text class="hint-warn">手机须与 Server 同一局域网（Wi-Fi），不能用 4G/5G</text>
      <text>在 config.js 中填写电脑局域网 IP，例如 http://192.168.1.100:8000</text>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { BASE_URL } from '../../config.js'
import { analyzeComposition, checkHealth } from '../../utils/api.js'
import { toOverlayStyle, decisionLabel, decisionColor } from '../../utils/bbox.js'
import { chooseImageFromCamera, chooseImageFromAlbum } from '../../utils/image.js'

const baseUrl = BASE_URL
const imagePath = ref('')
const loading = ref(false)
const testing = ref(false)
const result = ref(null)
const latencyMs = ref(null)
const overlayStyle = ref(null)

const statusText = computed(() => {
  if (loading.value) return '正在分析构图，云端可能需数分钟，请耐心等待…'
  if (result.value) return result.value.message || decisionLabel(result.value.decision)
  return ''
})

const statusColor = computed(() => {
  if (result.value) return decisionColor(result.value.decision)
  return '#64748b'
})

function resetImage(path) {
  imagePath.value = path
  result.value = null
  overlayStyle.value = null
  latencyMs.value = null
}

function takePhoto() {
  chooseImageFromCamera(resetImage)
}

function chooseAlbum() {
  chooseImageFromAlbum(resetImage)
}

function onImageLoad() {
  if (result.value?.bbox) {
    overlayStyle.value = toOverlayStyle(result.value.bbox)
  }
}

async function testConnection() {
  testing.value = true
  try {
    const data = await checkHealth()
    const loaded = data.model_loaded
      ? `推理服务就绪（${data.backend || 'api'}）`
      : `推理服务未就绪。${data.detail || '请检查 Server 配置'}`
    uni.showModal({
      title: '连接成功',
      content: `Server 正常。${loaded}`,
      showCancel: false
    })
  } catch (e) {
    uni.showModal({
      title: '连接失败',
      content: e.message || '请检查 Server 与 Wi-Fi',
      showCancel: false
    })
  } finally {
    testing.value = false
  }
}

async function analyze() {
  if (!imagePath.value || loading.value) return
  loading.value = true
  result.value = null
  overlayStyle.value = null
  latencyMs.value = null

  try {
    const data = await analyzeComposition(imagePath.value)
    result.value = data
    latencyMs.value = data.latency_ms ?? null
    if (data.bbox && data.decision === 'refine') {
      overlayStyle.value = toOverlayStyle(data.bbox)
    }
  } catch (e) {
    uni.showToast({
      title: e.message || '分析失败',
      icon: 'none',
      duration: 3000
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.header {
  margin-bottom: 32rpx;
}

.title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
}

.subtitle {
  display: block;
  margin-top: 8rpx;
  font-size: 26rpx;
  color: #94a3b8;
}

.preview-wrap {
  margin-bottom: 24rpx;
}

.image-box {
  position: relative;
  width: 100%;
  border-radius: 16rpx;
  overflow: hidden;
  background: #1e293b;
}

.preview-image {
  width: 100%;
  display: block;
}

.bbox-overlay {
  position: absolute;
  border: 4rpx solid #ef4444;
  box-sizing: border-box;
  pointer-events: none;
}

.placeholder {
  height: 400rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1e293b;
  border-radius: 16rpx;
  margin-bottom: 24rpx;
}

.placeholder-text {
  color: #64748b;
  font-size: 28rpx;
}

.status {
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
  background: #1e293b;
  border-radius: 12rpx;
  border-left: 8rpx solid #64748b;
}

.status-text {
  font-size: 30rpx;
}

.latency {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #94a3b8;
}

.actions {
  display: flex;
  gap: 24rpx;
  margin-bottom: 32rpx;
}

.btn {
  flex: 1;
  font-size: 30rpx;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}

.btn-secondary {
  background: #334155;
  color: #fff;
}

.btn-test {
  width: 100%;
  background: #475569;
  color: #fff;
  font-size: 28rpx;
}

.hint-warn {
  color: #fbbf24 !important;
  margin-top: 8rpx;
}

.hint {
  font-size: 22rpx;
  color: #64748b;
  line-height: 1.6;
}

.hint text {
  display: block;
}
</style>
