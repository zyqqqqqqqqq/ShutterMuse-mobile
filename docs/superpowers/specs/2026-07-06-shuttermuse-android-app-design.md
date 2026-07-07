# ShutterMuse 摄影构图 App — 设计规格

**日期：** 2026-07-06  
**状态：** 已通过（2026-07-06）；**修订** 2026-07-06 — 客户端改为 HBuilderX / uni-app  
**方法论：** Superpowers brainstorming（用户已逐块确认）

---

## 1. 背景与目标

ShutterMuse 是基于 Qwen3-VL-8B 的多模态摄影指导模型，仓库当前仅提供 Python 训练/评测/单图推理脚本，无官方手机 App。本设计定义一个 **移动端 MVP**，实现摄影师侧构图指导的端到端闭环。

### 1.1 用户决策摘要

| 维度 | 选择 |
|------|------|
| 核心能力 | 摄影师侧构图（keep / refine / reject + 构图框） |
| 平台 | Android 优先（HBuilderX 云打包）；同一套 uni-app 可扩展 iOS |
| 客户端技术 | **HBuilderX + uni-app（Vue 3）** |
| 推理部署 | 远端 GPU（本机或云服务器），端上推理留待后续 |
| 触发方式 | 用户拍照（或选图）后点击「分析构图」 |
| MVP 成功标准 | 拍照 → 点分析 → 数秒内看到构图框/文案（演示级闭环） |
| 架构方案 | uni-app 客户端 + Python FastAPI 推理服务（`server/` 已完成） |

### 1.2 MVP 范围外

- 被摄者摆姿（COCO-17 关键点）
- 实时周期性分析（取景连续刷新）
- 用户账号、历史同步、配额管理
- 端侧大模型推理
- iOS 正式上架（uni-app 代码可复用，仅需云打包配置）

---

## 2. 总体架构

```text
┌──────────────────┐         HTTPS / HTTP          ┌─────────────────────────┐
│  uni-app App     │  ── POST /v1/composition ──►  │  Inference Server       │
│  (HBuilderX)     │  ◄── JSON (决策 + bbox) ───   │  (FastAPI + ShutterMuse) │
│                  │                               │  GPU 机器                │
│  拍照/选图       │                               │                         │
│  「分析构图」    │                               │  加载 Qwen3-VL + LoRA   │
│  结果页画框/文案 │                               │  复用现有推理逻辑        │
└──────────────────┘                               └─────────────────────────┘
```

### 2.1 架构原则

1. **手机不跑大模型** — 仅负责取景、上传、渲染 UI。
2. **服务端薄封装** — API 层调用现有 `evaluation/photographer-side/infer_single_qwen_lora.py` 等价逻辑，不重造训练链路。
3. **部署灵活** — 开发期用局域网 `http://<GPU机器IP>:8000`；生产可换公网域名，App 只改 `BASE_URL`。
4. **无状态 MVP** — 无账号、无数据库；请求不入库，图片推理后不持久化。

---

## 3. 组件与职责

### 3.1 uni-app 客户端（HBuilderX）

| 组件 | 职责 |
|------|------|
| **影像获取** | `uni.chooseImage`（`sourceType: ['camera']`）拍照；MVP 不做复杂实时预览叠框 |
| **网络模块** | `uni.uploadFile` 上传至 `POST /v1/composition`；超时 60s；`config.js` 配置 `BASE_URL` |
| **结果渲染** | 解析 `decision` + `bbox`；在图片上用绝对定位 `view` 画红框（归一化坐标 × 图片显示宽高） |
| **UI 状态机** | `idle` → `loading` → `success` / `error`；loading 时禁用按钮 |

**MVP 不做：** 本地模型、登录、历史同步、复杂设置页（服务器地址写在 `config.js` 即可）。

**HBuilderX 配置要点：**
- `manifest.json`：相机、网络权限；Android `usesCleartextTraffic: true`（局域网 HTTP 调试）
- 真机运行：HBuilderX → 运行到 Android 基座；正式包用云打包 APK

### 3.2 Inference Server（Python / FastAPI）

| 组件 | 职责 |
|------|------|
| **API 层** | 路由、请求校验、统一错误响应 |
| **推理适配层** | 封装 photographer-side 推理，输出标准化 JSON |
| **模型生命周期** | 服务启动时加载模型至 GPU；请求内不冷启动 |
| **健康检查** | `GET /health` 报告服务与模型就绪状态 |

### 3.3 决策语义（对齐 ShutterMuse）

| `decision` | 含义 | UI 表现 |
|------------|------|---------|
| `keep` | 当前取景已合适 | 绿色提示「构图良好」；可不画框 |
| `refine` | 建议裁剪 | 红色构图框 + 「建议按框裁剪」 |
| `reject` | 当前帧不适合 | 提示换角度/重拍；`bbox` 为 null |

`bbox` 使用 **归一化坐标**（0–1，原点左上），相对上传图像尺寸。

---

## 4. 数据流与 API

### 4.1 请求链路

```text
用户拍照（或选图）→ 点「分析构图」
  → uni.uploadFile 上传 JPEG（系统/chooseImage 已压缩）
  → POST /v1/composition（multipart: image）
  → Server 校验类型与大小
  → 推理适配层调用 ShutterMuse photographer-side
  → 解析为 { decision, bbox?, message? }
  → App 在结果图片上按归一化 bbox 画框并更新文案
```

### 4.2 API 规格

#### `GET /health`

```json
{
  "status": "ok",
  "model_loaded": true
}
```

#### `POST /v1/composition`

- **请求：** `multipart/form-data`，字段 `image`（必填）
- **成功 200：**

```json
{
  "decision": "refine",
  "bbox": { "x1": 0.12, "y1": 0.08, "x2": 0.88, "y2": 0.92 },
  "message": "建议按红框裁剪",
  "latency_ms": 1840
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `decision` | string | `keep` \| `refine` \| `reject` |
| `bbox` | object \| null | 归一化矩形；`reject` 时为 null |
| `message` | string \| null | 可选展示文案 |
| `latency_ms` | int | 可选，调试用 |

#### 错误响应

```json
{
  "error": {
    "code": "INVALID_IMAGE | PAYLOAD_TOO_LARGE | MODEL_BUSY | INFERENCE_FAILED | MODEL_NOT_READY",
    "message": "人类可读说明"
  }
}
```

| HTTP | 场景 |
|------|------|
| 400 | 无效图片、超过大小上限 |
| 503 | 模型未就绪、推理忙 |
| 500 | 推理内部错误 |

### 4.3 坐标约定

- `bbox`：`0 ≤ x1 < x2 ≤ 1`，`0 ≤ y1 < y2 ≤ 1`，相对上传图像。
- App 按**结果页 `<image>` 实际显示区域**等比映射；MVP 使用 `mode="widthFix"`，bbox 百分比基于图片 intrinsic 比例。

### 4.4 配置

| 侧 | 配置项 |
|----|--------|
| App | `uni-app/config.js` → `BASE_URL`（默认 `http://<局域网IP>:8000`） |
| Server | 模型路径、LoRA 路径、端口、最大上传字节（环境变量） |

---

## 5. 错误处理与边界

### 5.1 uni-app 客户端

| 场景 | 处理 |
|------|------|
| 无网络 / 连接失败 | `uni.showToast` 提示检查 Wi-Fi 与 `BASE_URL` |
| 超时（60s） | `uni.uploadFile` timeout + 「分析超时，请重试」 |
| HTTP 非 200 | 解析 `error.message` 或展示 statusCode |
| JSON 解析失败 | 「结果异常，请重试」+ `console.error` |
| 分析中重复点击 | `:disabled="loading"` |
| 相机权限被拒 | 提示在系统设置中开启相机权限 |
| 图片未选 | 「请先拍照」 |

### 5.2 Server

| 场景 | 处理 |
|------|------|
| 模型未加载 | `/health` → `model_loaded: false`；POST → 503 |
| 坏图 / 超限 | 400 |
| GPU OOM / 推理异常 | 500 + 日志 |
| 并发请求 | MVP 串行；第二请求 503 `MODEL_BUSY` |
| 模型输出无法解析 | 记日志；兜底 `reject` + `bbox: null` |

### 5.3 安全与隐私（MVP 底线）

- 公网部署使用 HTTPS；局域网调试可用 HTTP。
- 图片仅在内存中处理，推理后不持久化。
- 无鉴权（自用/演示）；公网需 v2 增加 API Key。

### 5.4 性能预期

- 单次分析约 **3–10 秒**（GPU + 网络）。
- 上传前压缩目标 **< 500KB–1MB**。

---

## 6. 测试策略

| 层级 | 内容 | 方法 |
|------|------|------|
| Server 单元 | 输出解析、decision 映射 | pytest + mock / 固定样例 |
| Server 集成 | `POST /v1/composition` | curl / pytest + `test/` 示例图 |
| Health | 模型加载状态 | 启动后断言 `model_loaded: true` |
| 客户端单元 | bbox 换算纯函数 | `utils/bbox.js` 可在 Node 下简单断言 |
| 联调 | HBuilderX 真机运行 + 局域网 GPU | 拍照 → 点分析 |
| 验收 | keep / refine / reject 各 1 例 | 对照 MVP 成功标准 |

**MVP 不做：** UI 自动化、压力测试、多机型矩阵。

---

## 7. 项目结构

```text
ShutterMuse/
├── evaluation/              # 现有
├── training/                # 现有
├── server/                  # 新增
│   ├── app/
│   │   ├── main.py
│   │   ├── inference.py     # 复用 evaluation/photographer-side 逻辑
│   │   └── schemas.py
│   ├── tests/
│   └── requirements-server.txt
├── uni-app/                 # 新增（HBuilderX 打开此目录）
│   ├── pages/index/index.vue
│   ├── utils/api.js
│   ├── utils/bbox.js
│   ├── config.js
│   ├── manifest.json
│   ├── pages.json
│   └── README.md
└── docs/superpowers/specs/
    └── 2026-07-06-shuttermuse-android-app-design.md
```

`server/inference.py` 应 import 或调用 `evaluation/photographer-side/` 现有模块，避免复制模型逻辑。

---

## 8. 实现顺序（供 writing-plans 使用）

1. **Server：** `/health` + `/v1/composition`（**已完成**）
2. **uni-app：** HBuilderX 建工程、`config.js`、`manifest` 权限
3. **uni-app：** 拍照页 + `uni.uploadFile` + 结果画框
4. **联调：** HBuilderX 真机运行 + 局域网 GPU
5. **（可选）** 云打包 APK / 公网 HTTPS

---

## 9. 环境与交付

| 依赖 | 说明 |
|------|------|
| GPU 机器 | Qwen3-VL-8B + ShutterMuse LoRA 已下载 |
| Android 真机 | 与 GPU 同网段；安装 HBuilderX 调试基座或云打包 APK |
| HBuilderX | 打开 `uni-app/` 目录，运行到 Android 设备 |
| 文档 | `server/README.md` + `uni-app/README.md` |

---

## 10. 后续版本（非 MVP）

- iOS（同一 uni-app 云打包即可）
- 画幅比例选择（16:9、1:1 等，对齐 ShutterMuse photographer prompt）
- 分析历史本地保存
- 账号、配额、HTTPS 鉴权
- ~~被摄者摆姿模式~~（已实现：见 `docs/superpowers/specs/2026-07-06-shuttermuse-pose-mode-design.md`）
- 端侧轻量模型 + 云端混合推理
