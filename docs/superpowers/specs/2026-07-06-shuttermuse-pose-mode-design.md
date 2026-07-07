# ShutterMuse 被摄者摆姿模式 — 设计规格

**日期：** 2026-07-06  
**状态：** 已通过  
**前置：** `docs/superpowers/specs/2026-07-06-shuttermuse-android-app-design.md`（摄影师构图 MVP 已完成）

---

## 1. 目标

在现有 uni-app + FastAPI 架构上，增加 **被摄者摆姿模式（subject-side）** 端到端闭环：

拍照 → 点「分析摆姿」→ 数秒内看到 COCO-17 骨架叠加与文案。

## 2. 范围

| 包含 | 不包含 |
|------|--------|
| `POST /v1/pose` API | 实时连续摆姿跟踪 |
| 复用 subject-side prompt + JSON 解析 | 端侧推理 |
| uni-app 摆姿页 + Canvas 骨架绘制 | 账号/历史 |
| Tab 切换「构图 / 摆姿」 | 多人同时检测 |

## 3. API 契约

### `POST /v1/pose`

- **请求：** `multipart/form-data`，字段 `image`（JPEG/PNG，≤5MB）
- **响应 200：**

```json
{
  "keypoints": [
    {"x": 0.5, "y": 0.3, "visible": true},
    null,
    ...
  ],
  "message": "摆姿分析完成",
  "parse_ok": true,
  "latency_ms": 3200
}
```

- `keypoints`：长度 17，顺序为 COCO-17（鼻、左眼、右眼…）；不可见点为 `null`
- 错误码与 `/v1/composition` 一致（503/400/500）

## 4. 推理

- **API 模式：** DashScope Qwen-VL，`max_tokens=4096`，subject prompt
- **本地模式：** `infer_single_qwen_lora.run_inference(side="subject")` + `build_subject_record`
- 解析：`evaluation/subject-side/01_run_benchmark_gen.sanitize_instance_info`

## 5. 客户端

- `pages/pose/index.vue`：拍照、分析、Canvas 骨架（绿线 + 红点）
- `utils/pose.js`：COCO-17 边、Canvas 绘制
- `pages.json`：tabBar「构图」「摆姿」

## 6. 验收

- [ ] Tab 可切换构图/摆姿页
- [ ] 摆姿页上传成功返回 17 点 JSON
- [ ] 可见关键点与骨架正确叠加在预览图上
- [ ] 解析失败有友好文案
