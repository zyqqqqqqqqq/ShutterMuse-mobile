/**
 * 归一化 bbox (0-1) → 用于 overlay view 的百分比样式
 */
export function toOverlayStyle(bbox) {
  if (!bbox) return null
  const { x1, y1, x2, y2 } = bbox
  return {
    left: `${x1 * 100}%`,
    top: `${y1 * 100}%`,
    width: `${(x2 - x1) * 100}%`,
    height: `${(y2 - y1) * 100}%`
  }
}

export function decisionLabel(decision) {
  switch (decision) {
    case 'keep':
      return '当前构图良好'
    case 'refine':
      return '建议按红框裁剪'
    case 'reject':
      return '建议换角度或重拍'
    default:
      return '未知结果'
  }
}

export function decisionColor(decision) {
  switch (decision) {
    case 'keep':
      return '#22c55e'
    case 'refine':
      return '#ef4444'
    case 'reject':
      return '#f59e0b'
    default:
      return '#64748b'
  }
}
