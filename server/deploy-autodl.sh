#!/bin/bash
# ShutterMuse one-shot deploy on AutoDL (RTX 4090 24GB)
set -euo pipefail

WORKDIR="${WORKDIR:-/root/autodl-tmp}"
REPO_DIR="${WORKDIR}/ShutterMuse"
MODEL_DIR="${WORKDIR}/ShutterMuse-model"
PORT="${PORT:-8000}"

echo "==> GPU check"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
df -h "${WORKDIR}"

echo "==> Clone repo (skip if exists)"
if [[ ! -d "${REPO_DIR}/.git" ]]; then
  cd "${WORKDIR}"
  git clone https://github.com/lijayuTnT/ShutterMuse.git
fi

echo "==> Install Python deps (may take several minutes)"
cd "${REPO_DIR}"
pip install -q -r server/requirements-server.txt
# Core inference deps only (lighter than full requirements.txt)
pip install -q torch torchvision transformers peft accelerate qwen-vl-utils safetensors sentencepiece

echo "==> Download ShutterMuse model (~18GB, first time only)"
if [[ ! -f "${MODEL_DIR}/config.json" ]]; then
  pip install -q huggingface_hub
  huggingface-cli download ShutterMuse/ShutterMuse --local-dir "${MODEL_DIR}"
else
  echo "Model already at ${MODEL_DIR}"
fi

echo "==> Start server on 0.0.0.0:${PORT}"
cd "${REPO_DIR}/server"
export INFERENCE_BACKEND=local
export SHUTTERMUSE_MODEL_PATH="${MODEL_DIR}"
export SHUTTERMUSE_LORA_PATH=
unset DASHSCOPE_API_KEY VISION_API_KEY 2>/dev/null || true

echo "Loading model... first request may take 1-3 min"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
