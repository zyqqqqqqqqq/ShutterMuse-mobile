# ShutterMuse 摆姿模式 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 摆姿 Tab：拍照 → `POST /v1/pose` → Canvas 绘制 COCO-17 骨架。

**Architecture:** 扩展 `server/` 与 `uni-app/`；复用 subject-side 解析逻辑。

**Spec:** `docs/superpowers/specs/2026-07-06-shuttermuse-pose-mode-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `server/app/pose_mapper.py` | subject record → API JSON |
| `server/app/inference.py` | `run_subject_inference` |
| `server/app/schemas.py` | `PoseResponse`, `Keypoint` |
| `server/app/main.py` | `POST /v1/pose` |
| `server/tests/test_api.py` | pose 端点测试 |
| `uni-app/utils/pose.js` | COCO-17 边 + canvas 绘制 |
| `uni-app/utils/api.js` | `analyzePose` |
| `uni-app/pages/pose/index.vue` | 摆姿主页面 |
| `uni-app/pages.json` | tabBar 构图/摆姿 |

---

## Task 1: Server pose endpoint

- [ ] `pose_mapper.py` + schemas
- [ ] `run_subject_inference` in inference.py
- [ ] `POST /v1/pose` in main.py
- [ ] pytest mock 测试

## Task 2: uni-app 摆姿页

- [ ] `utils/pose.js` + `api.js`
- [ ] `pages/pose/index.vue`
- [ ] `pages.json` tabBar

## Task 3: 文档

- [ ] 更新 `server/README.md`、`uni-app/README.md`
