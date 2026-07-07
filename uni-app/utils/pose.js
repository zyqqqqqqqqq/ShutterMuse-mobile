/** COCO-17 skeleton edges (same as infer_single_qwen_lora.py) */
export const COCO17_EDGES = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10], [5, 11], [6, 12],
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [0, 1],
  [0, 2], [1, 3], [2, 4]
]

/** Body part chains for thick-limb silhouette (matches 03_qwen3vl_draw17.py) */
const LIMB_CHAINS = [
  { indices: [5, 7, 9], widthRatio: 0.018 },
  { indices: [6, 8, 10], widthRatio: 0.018 },
  { indices: [11, 13, 15], widthRatio: 0.024 },
  { indices: [12, 14, 16], widthRatio: 0.024 }
]

const HEAD_INDICES = [3, 1, 0, 2, 4]
const TORSO_INDICES = [5, 6, 12, 11]
const HEAD_SET = new Set(HEAD_INDICES)

const BODY_GREEN = '#22c55e'
const BODY_GREEN_FILL = 'rgba(34, 197, 94, 0.55)'

/**
 * @param {Array<{x:number,y:number,visible?:boolean}|null>} keypoints
 */
export function normalizePosePoints(keypoints) {
  if (!Array.isArray(keypoints)) return null
  const pts = keypoints.map((kp) => {
    if (!kp || kp.visible === false) return null
    const x = Number(kp.x)
    const y = Number(kp.y)
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null
    return { x, y }
  })
  return pts.some(Boolean) ? pts : null
}

export function visibleKeypointCount(keypoints) {
  if (!Array.isArray(keypoints)) return 0
  return keypoints.filter((kp) => kp && kp.visible !== false).length
}

export function convexHull(points) {
  const pts = (points || []).filter(Boolean)
  if (pts.length <= 1) return pts

  const sorted = [...pts].sort((a, b) => a.x - b.x || a.y - b.y)
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)

  const lower = []
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop()
    }
    lower.push(p)
  }

  const upper = []
  for (let i = sorted.length - 1; i >= 0; i -= 1) {
    const p = sorted[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop()
    }
    upper.push(p)
  }

  upper.pop()
  lower.pop()
  return lower.concat(upper)
}

function toAbs(point, width, height) {
  return { x: point.x * width, y: point.y * height }
}

function pickAbsPoints(pts, indices, width, height) {
  return indices
    .map((idx) => (pts[idx] ? toAbs(pts[idx], width, height) : null))
    .filter(Boolean)
}

function fillHull(ctx, points) {
  const hull = convexHull(points)
  if (hull.length < 3) return
  ctx.beginPath()
  ctx.moveTo(hull[0].x, hull[0].y)
  for (let i = 1; i < hull.length; i += 1) {
    ctx.lineTo(hull[i].x, hull[i].y)
  }
  ctx.closePath()
  ctx.fill()
}

function strokeSegment(ctx, start, end, thickness) {
  ctx.beginPath()
  ctx.moveTo(start.x, start.y)
  ctx.lineTo(end.x, end.y)
  ctx.lineWidth = thickness
  ctx.lineCap = 'round'
  ctx.stroke()
}

function drawLimbChain(ctx, absPts, thickness) {
  for (let i = 0; i < absPts.length - 1; i += 1) {
    strokeSegment(ctx, absPts[i], absPts[i + 1], thickness)
    ctx.beginPath()
    ctx.arc(absPts[i].x, absPts[i].y, thickness / 2, 0, Math.PI * 2)
    ctx.fill()
  }
  const last = absPts[absPts.length - 1]
  ctx.beginPath()
  ctx.arc(last.x, last.y, thickness / 2, 0, Math.PI * 2)
  ctx.fill()
}

function drawKeypointDot(ctx, x, y, radius, { head = false } = {}) {
  if (head) {
    ctx.beginPath()
    ctx.arc(x, y, radius + 1.5, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.fill()
    ctx.beginPath()
    ctx.arc(x, y, radius - 0.5, 0, Math.PI * 2)
    ctx.fillStyle = '#111827'
    ctx.fill()
    return
  }

  ctx.beginPath()
  ctx.arc(x, y, radius + 1.5, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.fillStyle = BODY_GREEN
  ctx.fill()
}

/**
 * Draw official-style body silhouette on a 2D canvas context.
 * Coordinates are normalized 0–1 relative to image width/height.
 *
 * @param {object} ctx uni-app / browser canvas context
 * @param {number} width display width in px
 * @param {number} height display height in px
 * @param {Array<{x:number,y:number,visible?:boolean}|null>} keypoints
 */
export function drawBodySilhouette(ctx, width, height, keypoints) {
  const pts = normalizePosePoints(keypoints)
  if (!ctx || width <= 0 || height <= 0 || !pts) return

  const minDim = Math.min(width, height)
  const dotRadius = Math.max(3, Math.round(minDim * 0.006))
  const thinLine = Math.max(2, Math.round(minDim * 0.003))

  ctx.clearRect(0, 0, width, height)

  // Pass 1: semi-transparent torso/head + thick limbs
  ctx.save()
  ctx.globalAlpha = 0.55
  ctx.fillStyle = BODY_GREEN_FILL
  ctx.strokeStyle = BODY_GREEN
  fillHull(ctx, pickAbsPoints(pts, TORSO_INDICES, width, height))
  fillHull(ctx, pickAbsPoints(pts, HEAD_INDICES, width, height))

  for (const chain of LIMB_CHAINS) {
    const absPts = pickAbsPoints(pts, chain.indices, width, height)
    if (absPts.length >= 2) {
      const thickness = Math.max(8, Math.round(minDim * chain.widthRatio))
      drawLimbChain(ctx, absPts, thickness)
    }
  }
  ctx.restore()

  // Pass 2: opaque limbs (avoid washed-out green from alpha blend)
  ctx.save()
  ctx.globalAlpha = 1
  ctx.strokeStyle = BODY_GREEN
  ctx.fillStyle = BODY_GREEN
  for (const chain of LIMB_CHAINS) {
    const absPts = pickAbsPoints(pts, chain.indices, width, height)
    if (absPts.length >= 2) {
      const thickness = Math.max(8, Math.round(minDim * chain.widthRatio))
      drawLimbChain(ctx, absPts, thickness)
    }
  }
  ctx.restore()

  // Pass 3: thin skeleton wireframe
  ctx.save()
  ctx.strokeStyle = BODY_GREEN
  ctx.lineWidth = thinLine
  ctx.lineCap = 'round'
  for (const [a, b] of COCO17_EDGES) {
    const pa = pts[a]
    const pb = pts[b]
    if (!pa || !pb) continue
    const start = toAbs(pa, width, height)
    const end = toAbs(pb, width, height)
    strokeSegment(ctx, start, end, thinLine)
  }
  ctx.restore()

  // Pass 4: keypoints
  pts.forEach((kp, idx) => {
    if (!kp) return
    const { x, y } = toAbs(kp, width, height)
    drawKeypointDot(ctx, x, y, dotRadius, { head: HEAD_SET.has(idx) })
  })
}

/**
 * @deprecated CSS overlay helper; kept for compatibility.
 */
export function buildSkeletonOverlays(keypoints, aspect = 1) {
  const safeAspect = aspect > 0 ? aspect : 1
  const pts = (keypoints || []).map((kp) => (kp && kp.visible !== false ? kp : null))
  const dots = []
  const lines = []

  pts.forEach((kp) => {
    if (!kp) return
    dots.push({
      left: `${kp.x * 100}%`,
      top: `${kp.y * 100}%`
    })
  })

  COCO17_EDGES.forEach(([a, b]) => {
    const pa = pts[a]
    const pb = pts[b]
    if (!pa || !pb) return
    const dx = pb.x - pa.x
    const dy = pb.y - pa.y
    const widthPct = Math.hypot(dx, dy / safeAspect) * 100
    const angle = (Math.atan2(dy, dx * safeAspect) * 180) / Math.PI
    lines.push({
      left: `${pa.x * 100}%`,
      top: `${pa.y * 100}%`,
      width: `${widthPct}%`,
      transform: `rotate(${angle}deg)`
    })
  })

  return { dots, lines }
}
