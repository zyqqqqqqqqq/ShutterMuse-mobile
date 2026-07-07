# ShutterMuse Composition API Server

FastAPI inference service for photographer-side composition guidance.

## Inference backends

| Backend | When to use | Requirements |
|---------|-------------|--------------|
| **Qwen-VL API** (recommended for no-GPU) | Set `DASHSCOPE_API_KEY` | 阿里云百炼 API key |
| **Local Qwen + LoRA** | Set `SHUTTERMUSE_MODEL_PATH` | NVIDIA GPU, CUDA, model weights |

> **注意：** DeepSeek 官方 API（`deepseek-v4-flash` / `deepseek-v4-pro`）**不支持图片输入**，无法用于构图分析。请使用 DashScope 的 Qwen-VL。

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DASHSCOPE_API_KEY` | Yes (API mode) | 阿里云百炼 API Key，[申请地址](https://dashscope.console.aliyun.com) |
| `VISION_API_KEY` | No | `DASHSCOPE_API_KEY` 的别名 |
| `INFERENCE_BACKEND` | No | `api` for cloud API; `local` for local GPU |
| `VISION_API_MODEL` | No | Default: `qwen-vl-plus` |
| `VISION_API_BASE_URL` | No | Default: `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `VISION_API_MAX_RETRIES` | No | API retry count (default: 3) |
| `SHUTTERMUSE_MODEL_PATH` | Yes (local mode) | Path to Qwen3-VL base model |
| `SHUTTERMUSE_LORA_PATH` | No | Path to ShutterMuse LoRA adapter |
| `SKIP_MODEL_LOAD` | No | Set to `1` to skip startup (pytest only) |
| `MAX_UPLOAD_BYTES` | No | Max upload size in bytes (default: 5MB) |

## Setup and run (Qwen-VL API — no GPU)

**一键启动（推荐）：**

```powershell
cd server
$env:DASHSCOPE_API_KEY="您的API_Key"
.\start-api.ps1
```

或手动启动：

```powershell
cd server
py -m pip install -r requirements-server.txt
$env:DASHSCOPE_API_KEY="您的API_Key"
$env:INFERENCE_BACKEND="api"
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Setup and run (local GPU)

```powershell
$env:SHUTTERMUSE_MODEL_PATH="您的模型路径"
$env:SHUTTERMUSE_LORA_PATH="您的LoRA路径"
$env:INFERENCE_BACKEND="local"
cd server
py -m pip install -r requirements-server.txt
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Verify with curl

```bash
curl -s http://127.0.0.1:8000/health
curl -s -F "image=@../test/401128801616615964.webp" http://127.0.0.1:8000/v1/composition
curl -s -F "image=@../test/401128801616615964.webp" http://127.0.0.1:8000/v1/pose
```

Expected: `/health` returns `"model_loaded": true`; composition returns `decision` + optional `bbox`; pose returns 17 `keypoints` + `parse_ok`.
