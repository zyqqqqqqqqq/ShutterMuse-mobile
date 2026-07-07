# ShutterMuse Server — Qwen-VL API 模式（无需 GPU）
# DeepSeek 官方 API 不支持图片，请使用阿里云百炼 DashScope 的 Qwen-VL。
# 用法：
#   $env:DASHSCOPE_API_KEY="您的API_Key"
#   .\start-api.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $env:DASHSCOPE_API_KEY) {
    Write-Host "错误：请先设置 DASHSCOPE_API_KEY" -ForegroundColor Red
    Write-Host '  $env:DASHSCOPE_API_KEY="您的API_Key"' -ForegroundColor Yellow
    Write-Host "  申请地址：https://dashscope.console.aliyun.com" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "注意：DeepSeek 官方 API 不支持图片输入，无法用于构图分析。" -ForegroundColor Yellow
    exit 1
}

$env:INFERENCE_BACKEND = "api"
Remove-Item Env:SKIP_MODEL_LOAD -ErrorAction SilentlyContinue

Write-Host "安装依赖..." -ForegroundColor Cyan
py -m pip install -q -r requirements-server.txt

$modelName = if ($env:VISION_API_MODEL) { $env:VISION_API_MODEL } else { "qwen-vl-plus" }
Write-Host "启动 Server（Qwen-VL API 模式）..." -ForegroundColor Green
Write-Host "  模型: $modelName" -ForegroundColor Gray
Write-Host "  地址: http://0.0.0.0:8000" -ForegroundColor Gray
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
