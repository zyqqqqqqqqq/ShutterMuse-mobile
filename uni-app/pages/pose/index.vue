<template>
  <view class="page">
    <view class="header">
      <text class="title">ShutterMuse</text>
      <text class="subtitle">场景摆姿推荐 · 被摄者模式</text>
    </view>

    <view v-if="imagePath" class="preview-wrap">
      <view class="image-box">
        <image
          class="preview-image"
          :src="imagePath"
          mode="widthFix"
          @load="onImageLoad"
        />
        <canvas
          v-if="showPoseOverlay"
          canvas-id="poseOverlay"
          id="poseOverlay"
          class="pose-overlay"
          :style="overlayCanvasStyle"
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
        {{ loading ? '分析中…' : '分析摆姿' }}
      </button>
    </view>

    <view class="actions">
      <button class="btn btn-test" :disabled="testing" @click="testConnection">
        {{ testing ? '测试中…' : '测试服务器连接' }}
      </button>
    </view>

    <view class="hint">
      <text>服务器：{{ baseUrl }}</text>
      <text class="hint-warn">绿色人形=推荐摆姿位置（场景推荐，不要求画面里已有人）</text>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { BASE_URL } from '../../config.js'
import { analyzePose, checkHealth } from '../../utils/api.js'
import { drawBodySilhouette, visibleKeypointCount } from '../../utils/pose.js'
import { chooseImageFromCamera, chooseImageFromAlbum } from '../../utils/image.js'

const baseUrl = BASE_URL
const imagePath = ref('')
const loading = ref(false)
const testing = ref(false)
const result = ref(null)
const latencyMs = ref(null)
const overlaySize = ref({ width: 0, height: 0 })

const statusText = computed(() => {
  if (loading.value) return '正在分析摆姿，云端可能需数分钟，请勿退出或连点…'
  if (result.value) return result.value.message || '摆姿分析完成'
  return ''
})

const statusColor = computed(() => {
  if (!result.value) return '#64748b'
  return result.value.parse_ok ? '#22c55e' : '#f59e0b'
})

const showPoseOverlay = computed(() => {
  return Boolean(
    result.value?.parse_ok
    && result.value.keypoints
    && overlaySize.value.width > 0
    && overlaySize.value.height > 0
  )
})

const overlayCanvasStyle = computed(() => ({
  width: `${overlaySize.value.width}px`,
  height: `${overlaySize.value.height}px`
}))

function measureOverlaySize() {
  return new Promise((resolve) => {
    uni.createSelectorQuery()
      .select('.preview-image')
      .boundingClientRect((rect) => {
        if (rect && rect.width > 0 && rect.height > 0) {
          overlaySize.value = {
            width: Math.round(rect.width),
            height: Math.round(rect.height)
          }
        }
        resolve()
      })
      .exec()
  })
}

function redrawPoseOverlay() {
  if (!showPoseOverlay.value) return
  const { width, height } = overlaySize.value
  const ctx = uni.createCanvasContext('poseOverlay')
  drawBodySilhouette(ctx, width, height, result.value.keypoints)
  ctx.draw(false, () => {})
}

function clearPoseOverlay() {
  const { width, height } = overlaySize.value
  if (width <= 0 || height <= 0) return
  const ctx = uni.createCanvasContext('poseOverlay')
  ctx.clearRect(0, 0, width, height)
  ctx.draw(false, () => {})
}

watch(
  () => [result.value, overlaySize.value.width, overlaySize.value.height],
  () => {
    schedulePoseRedraw()
  },
  { deep: true }
)

async function schedulePoseRedraw() {
  await nextTick()
  await measureOverlaySize()
  await nextTick()
  if (result.value?.parse_ok && result.value.keypoints) {
    redrawPoseOverlay()
  } else {
    clearPoseOverlay()
  }
}

function resetImage(path) {
  imagePath.value = path
  result.value = null
  latencyMs.value = null
}

function takePhoto() {
  chooseImageFromCamera(resetImage)
}

function chooseAlbum() {
  chooseImageFromAlbum(resetImage)
}

async function onImageLoad() {
  await schedulePoseRedraw()
}

async function testConnection() {
  testing.value = true
  try {
    const data = await checkHealth()
    if (!data.model_loaded) {
      uni.showModal({
        title: 'Server 已连接',
        content: `模型尚未加载完成（backend: ${data.backend || 'unknown'}）。请在 AutoDL 终端确认 uvicorn 已启动且加载完成，约 1–3 分钟后再试。`,
        showCancel: false
      })
      return
    }
    uni.showModal({
      title: '连接成功',
      content: `推理服务就绪（${data.backend || 'api'}）`,
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
  latencyMs.value = null

  try {
    const data = await analyzePose(imagePath.value)
    result.value = data
    latencyMs.value = data.latency_ms ?? null
    if (!data.parse_ok) {
      uni.showToast({ title: '未能识别摆姿关键点', icon: 'none' })
    } else if (visibleKeypointCount(data.keypoints) === 0) {
      uni.showToast({ title: '未检测到可见关键点', icon: 'none' })
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

.pose-overlay {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  z-index: 2;
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
  color: #86efac !important;
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
