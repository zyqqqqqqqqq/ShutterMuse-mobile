# ShutterMuse 移动端项目 — 完整实现历程

**文档日期：** 2026-07-07  
**范围：** 基于官方 [ShutterMuse](https://github.com/lijayuTnT/ShutterMuse) 仓库，从零搭建 **uni-app 客户端 + FastAPI 推理服务 + AutoDL 云端部署** 的全流程记录。

---

## 1. 项目目标

在官方论文模型（Qwen3-VL-8B + CaptureGuide 训练）之上，实现可演示的 **拍摄时摄影指导** 移动端闭环：

| 模式 | 能力 | 用户操作 |
|------|------|----------|
| **构图（摄影师侧）** | keep / refine / reject + 构图框 | 拍照 → 分析构图 |
| **摆姿（被摄者侧）** | 场景条件摆姿推荐 + COCO-17 关键点 | 拍照 → 分析摆姿 |

官方仓库原本只有 Python 训练/评测/CLI 推理脚本，**没有** `server/` 与 `uni-app/`。本扩展是在官方代码之上新增的端到端应用层。

---

## 2. 总体架构

```text
┌─────────────────────┐     HTTPS/HTTP      ┌──────────────────────────────┐
│  uni-app (Android)  │ ── POST multipart ─►│  FastAPI Server (server/)   │
│  HBuilderX 真机调试  │ ◄── JSON ───────────│  uvicorn + 推理锁            │
│                     │                     │                              │
│  Tab: 构图 / 摆姿    │  /v1/composition    │  inference.py               │
│  Canvas 人形叠加     │  /v1/pose           │  ├─ local: Qwen3-VL + LoRA  │
│  config.js BASE_URL │  /health            │  └─ api: DashScope Qwen-VL    │
└─────────────────────┘                     └──────────────────────────────┘
                                                        │
                                                        ▼
                                            HuggingFace ShutterMuse/ShutterMuse
                                            (AutoDL RTX 4090 24GB)
```

**设计原则：**

1. 手机不跑大模型，只负责拍照、上传、渲染。
2. Server 薄封装，复用 `evaluation/photographer-side/infer_single_qwen_lora.py` 的 prompt 与推理逻辑。
3. 无账号、无数据库，MVP 级演示闭环。

---

## 3. 实现阶段（按时间线）

### 阶段 A：构图 MVP（2026-07-06）

**设计文档：** `docs/superpowers/specs/2026-07-06-shuttermuse-android-app-design.md`

**后端 `server/`：**

| 文件 | 作用 |
|------|------|
| `app/main.py` | FastAPI：`/health`、`/v1/composition`、`/v1/pose`；单线程推理锁 |
| `app/inference.py` | 双后端：API（DashScope）/ 本地 GPU |
| `app/response_mapper.py` | 构图输出 → `decision` + `bbox` |
| `app/schemas.py` | Pydantic 响应模型 |
| `tests/` | pytest 覆盖 API 与 mapper |

**客户端 `uni-app/`：**

| 文件 | 作用 |
|------|------|
| `pages/index/index.vue` | 构图页：拍照、分析、红框叠加 |
| `utils/api.js` | `uploadFile` + 健康检查 |
| `utils/bbox.js` | 归一化 bbox → CSS  overlay |
| `config.js` | `BASE_URL` 指向 Server |
| `pages.json` | TabBar 路由 |

**首次联调路径：** 手机与电脑同一 Wi-Fi → `http://<局域网IP>:8000`

---

### 阶段 B：推理后端选型试错

| 尝试 | 结果 | 结论 |
|------|------|------|
| DeepSeek 官方 API | `unknown variant image_url` | **不支持图片**，不可用 |
| DashScope `qwen-vl-plus` API | 能返回 JSON | **通用 VL，非 ShutterMuse 微调权重**，摆姿质量差 |
| 本地 RTX 4060 8GB | OOM | 8B 模型放不下 |
| **AutoDL RTX 4090 24GB** | 成功 | 最终生产方案 |

**关键认知：** 要与 [官网 Demo](https://lijayutnt.github.io/ShutterMuse/) 质量接近，必须用 **HuggingFace 发布的 ShutterMuse 权重** 做本地推理，不能只调 DashScope 通用 API。

---

### 阶段 C：摆姿模式（2026-07-06）

**设计文档：** `docs/superpowers/specs/2026-07-06-shuttermuse-pose-mode-design.md`

**新增/扩展：**

- `POST /v1/pose`：上传图片 → 17 个 COCO 关键点 + 中文说明 + `parse_ok`
- `app/pose_mapper.py`、`app/subject_parse.py`：解析 subject-side JSON
- `pages/pose/index.vue`：摆姿 Tab
- `utils/pose.js`：骨架/人形绘制

**摆姿语义澄清：** 这是 **场景条件摆姿推荐**（画面中可以没有人），绿线/人形表示「建议站在这里、摆这个姿势」，不是对已有人的检测。

---

### 阶段 D：AutoDL 云端部署

**动机：** 本地 8GB 显卡不够；手机需公网 HTTPS 访问。

**环境：**

- 平台：AutoDL（SeetaCloud 代理域名）
- GPU：RTX 4090 24GB
- 内网端口：**6006** → 公网 **8443** HTTPS

**部署步骤摘要：**

```bash
# 1. 克隆官方仓库（GitHub zip 不含 server/，需单独上传 server-bundle）
cd /root/autodl-tmp
git clone https://github.com/lijayuTnT/ShutterMuse.git

# 2. 下载模型权重 (~18GB)
huggingface-cli download ShutterMuse/ShutterMuse --local-dir /root/autodl-tmp/ShutterMuse-model

# 3. 安装依赖
pip install -r server/requirements-server.txt
pip install torch transformers peft accelerate qwen-vl-utils

# 4. 启动（本地真实 ShutterMuse 模型）
export INFERENCE_BACKEND=local
export SHUTTERMUSE_MODEL_PATH=/root/autodl-tmp/ShutterMuse-model
export SUBJECT_MAX_NEW_TOKENS=2048
cd server
python -m uvicorn app.main:app --host 0.0.0.0 --port 6006
```

**辅助脚本：** `server/deploy-autodl.sh`（一键部署模板）

**验证：**

```bash
curl -s http://127.0.0.1:6006/health
# → "model_loaded": true, "backend": "local-qwen"

curl -s -F "image=@test.png" http://127.0.0.1:6006/v1/pose
# → "parse_ok": true, 17 keypoints
```

---

### 阶段 E：摆姿解析失败 → inference.py 修复

**现象：** CLI（`infer_single_qwen_lora.py --side subject`）成功，Server `/v1/pose` 失败（`parse_ok: false`，关键点全 null，~7s 返回）。

**根因：** AutoDL 上的 `server/app/inference.py` 是旧版，缺少：

- 官方 `SUBJECT_PROMPT`（来自 `infer_single_qwen_lora.py`）
- `build_subject_record` + `subject_parse` 双重解析兜底
- 本地模式失败重试
- `SUBJECT_MAX_NEW_TOKENS=2048`（4090 上 10240 易 OOM）

**修复后：** 银杏测试图 `parse_ok: true`，latency ~16s，17 个有效关键点。

**文件同步方式：** Windows JupyterLab 上传 / Windows PowerShell `scp`（**不能在 AutoDL 终端里 scp Windows 路径**）。

---

### 阶段 F：客户端体验优化

| 优化项 | 文件 | 说明 |
|--------|------|------|
| 云端超时 | `utils/api.js` | 上传超时 1 小时；健康检查 30s + 重试 |
| 云端错误提示 | `utils/api.js` | 区分 AutoDL 与局域网 Wi-Fi 提示 |
| 人形框架 | `utils/pose.js` + `pages/pose/index.vue` | Canvas 绘制官网风格半透明人形（凸包躯干/头部 + 粗肢体） |
| Tab 切换 | `pages.json` | 构图 / 摆姿 |

---

## 4. API 契约

### `GET /health`

```json
{
  "status": "ok",
  "model_loaded": true,
  "backend": "local-qwen",
  "detail": null
}
```

`backend` 取值：`local-qwen` | `qwen-vl-api` | `none`

### `POST /v1/composition`

- 请求：`multipart/form-data`，字段 `image`
- 响应：`decision`（keep/refine/reject）、`bbox`（归一化）、`message`、`latency_ms`

### `POST /v1/pose`

- 请求：同上
- 响应：`keypoints[17]`、`message`、`parse_ok`、`latency_ms`

---

## 5. 推理参数对比（当前 vs 官方）

| 任务 | 当前 Server 默认 | 官方 CLI / 评测默认 |
|------|------------------|---------------------|
| 构图 max tokens | 512 | 512 |
| 摆姿 max tokens | **2048**（环境变量可调） | **10240** |
| Prompt | 官方 SUBJECT_PROMPT | 相同 |
| 模型 | ShutterMuse HF 权重 | 相同 |

2048 是 4090 24GB 上为避免 OOM 的折中；实测足够输出 JSON + 中文说明。若要完全对齐官方评测，可设 `SUBJECT_MAX_NEW_TOKENS=10240`（需监控显存）。

---

## 6. 目录结构（本扩展部分）

```text
ShutterMuse/
├── server/                    # ★ 新增：FastAPI 推理服务
│   ├── app/
│   │   ├── main.py
│   │   ├── inference.py
│   │   ├── pose_mapper.py
│   │   ├── response_mapper.py
│   │   ├── subject_parse.py
│   │   └── schemas.py
│   ├── tests/
│   ├── deploy-autodl.sh
│   ├── start-api.ps1
│   └── README.md
├── uni-app/                   # ★ 新增：HBuilderX 客户端
│   ├── config.js              # BASE_URL
│   ├── pages/index/           # 构图
│   ├── pages/pose/            # 摆姿
│   └── utils/
├── docs/
│   ├── PROJECT_IMPLEMENTATION.md   # 本文档
│   ├── GITHUB_PUBLISH_CHECKLIST.md # 发布前脱敏清单
│   └── superpowers/           # 设计与实现计划
├── evaluation/                # 官方：评测与 CLI 推理
└── training/                  # 官方：SFT + GRPO
```

---

## 7. 本地开发快速开始

### 7.1 无 GPU（API 模式，质量有限）

```powershell
cd server
$env:DASHSCOPE_API_KEY="您的API_Key"
$env:INFERENCE_BACKEND="api"
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7.2 有 GPU（推荐，需 ShutterMuse 权重）

```powershell
$env:INFERENCE_BACKEND="local"
$env:SHUTTERMUSE_MODEL_PATH="路径/ShutterMuse-model"
$env:SUBJECT_MAX_NEW_TOKENS="2048"
cd server
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7.3 客户端

1. 复制 `uni-app/config.example.js` → `uni-app/config.js`，填入 Server 地址
2. HBuilderX 打开 `uni-app/`
3. 运行到 Android 真机

---

## 8. 已知限制与差异

| 项目 | 说明 |
|------|------|
| 官网 Demo 真人渲染 | 官网有时用 GPT-Image 等生成真人图；App 仅显示骨架/人形叠加 |
| CaptureGuide-Dataset | 未公开，只能用已发布 HF 权重 |
| 推理延迟 | 云端单次摆姿约 15–60s，取决于 GPU 与排队 |
| 单请求锁 | Server 同一时刻只处理一个推理（防 OOM） |
| GitHub 主仓库 zip | 不含 `server/`，需自行保留或 fork 上传 |

---

## 9. 问题排查速查

| 症状 | 可能原因 | 处理 |
|------|----------|------|
| 无法解析摆姿 | API 模式 / 旧 inference.py | 切 local + 更新 inference.py |
| 手机连接失败 | BASE_URL 错误 / AutoDL 实例关机 | 检查 `/health`、HTTPS 端口 |
| OOM | max_tokens=10240 或双进程加载模型 | 降到 2048；停掉多余 uvicorn |
| scp 报错 `Could not resolve hostname d:` | 在 Linux 上用了 Windows 路径 | 在 **Windows** 执行 scp |
| 骨架位置不对 | 解析失败或坐标全 0 | curl 本地 `/v1/pose` 看 `parse_ok` |

---

## 10. 参考链接

- 论文 & 官方仓库：https://github.com/lijayuTnT/ShutterMuse
- 官网 Demo：https://lijayutnt.github.io/ShutterMuse/
- 模型权重：https://huggingface.co/ShutterMuse/ShutterMuse
- 百炼 API（无 GPU 备用）：https://dashscope.console.aliyun.com

---

*本文档根据 2026-07-06 ~ 2026-07-07 的实现与调试会话整理，供后续维护、Fork 与开源发布参考。*
