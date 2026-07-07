# ShutterMuse uni-app 客户端 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** HBuilderX 可打开的 uni-app 工程：拍照 → `uni.uploadFile` → 显示 keep/refine/reject 与构图框。

**Architecture:** Vue 3 uni-app；`server/` API 不变（Phase A 已完成）。

**Tech Stack:** HBuilderX, uni-app, Vue 3, uni.uploadFile / uni.chooseImage

**Spec:** `docs/superpowers/specs/2026-07-06-shuttermuse-android-app-design.md`（已修订为 uni-app）

**前置：** `server/` FastAPI 已实现在 `server/app/`。

---

## File Map

| 文件 | 职责 |
|------|------|
| `uni-app/config.js` | `BASE_URL` |
| `uni-app/utils/api.js` | `analyzeComposition(filePath)` |
| `uni-app/utils/bbox.js` | 归一化 bbox → overlay 样式 |
| `uni-app/pages/index/index.vue` | 主页面：拍照、分析、画框 |
| `uni-app/pages.json` | 页面路由 |
| `uni-app/manifest.json` | 权限、Android 明文 HTTP |
| `uni-app/App.vue` | 应用入口样式 |
| `uni-app/main.js` | Vue 3 启动 |
| `uni-app/README.md` | HBuilderX 打开与真机调试 |

---

## Task 5: uni-app 工程脚手架

- [ ] 创建 `uni-app/` 目录与 `manifest.json`、`pages.json`、`main.js`、`App.vue`
- [ ] `manifest.json` 配置 CAMERA、INTERNET；Android `usesCleartextTraffic: true`
- [ ] HBuilderX：文件 → 打开目录 → 选择 `uni-app/`

## Task 6: config + api.js

- [ ] `config.js` 导出 `BASE_URL`
- [ ] `utils/api.js` 封装 `uni.uploadFile` 到 `/v1/composition`，解析 JSON / error

## Task 7: bbox 工具 + 主页面 UI

- [ ] `utils/bbox.js`：`toOverlayStyle(bbox, imageWidth, imageHeight)`
- [ ] `pages/index/index.vue`：拍照、分析按钮、loading、状态文案、红框 overlay

## Task 8: 联调与 README

- [ ] 启动 `server/`（GPU 机器局域网 IP）
- [ ] 修改 `config.js` 中 `BASE_URL`
- [ ] HBuilderX 运行到 Android 真机：拍照 → 分析 → 看到结果
- [ ] 编写 `uni-app/README.md`

---

## 验收清单

- [ ] 真机可拍照
- [ ] 上传成功返回 JSON
- [ ] `refine` 时显示红框
- [ ] `keep` / `reject` 显示对应文案
- [ ] 网络错误有 Toast 提示

---

## Execution

Phase A（Server）已完成。Phase B 用 Subagent-Driven 执行 Task 5–8，或直接在本仓库生成 `uni-app/` 源码后在 HBuilderX 打开。
