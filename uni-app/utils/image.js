/**
 * 从相机拍照
 */
export function chooseImageFromCamera(onSelected) {
  uni.chooseImage({
    count: 1,
    sourceType: ['camera'],
    sizeType: ['compressed'],
    success: (res) => onSelected(res.tempFilePaths[0]),
    fail: () => {
      uni.showToast({ title: '无法打开相机', icon: 'none' })
    }
  })
}

/**
 * 从相册选择图片
 */
export function chooseImageFromAlbum(onSelected) {
  uni.chooseImage({
    count: 1,
    sourceType: ['album'],
    sizeType: ['compressed'],
    success: (res) => onSelected(res.tempFilePaths[0]),
    fail: () => {
      uni.showToast({ title: '无法打开相册', icon: 'none' })
    }
  })
}
