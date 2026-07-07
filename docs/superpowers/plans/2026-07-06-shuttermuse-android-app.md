# ShutterMuse Android 构图 App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 Android MVP：相机预览 → 点「分析」→ 远端 GPU 跑 ShutterMuse → 显示 keep/refine/reject 与构图框。

**Architecture:** Kotlin Android 客户端 + Python FastAPI 服务。服务端复用 `evaluation/photographer-side/` 推理逻辑；App 仅上传 JPEG 并渲染归一化 bbox。

**Tech Stack:** FastAPI, uvicorn, pytest, httpx | Kotlin, CameraX, OkHttp, Android View overlay

**Spec:** `docs/superpowers/specs/2026-07-06-shuttermuse-android-app-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `server/app/schemas.py` | Pydantic 请求/响应与错误模型 |
| `server/app/response_mapper.py` | 模型输出 → `{decision, bbox}`（纯函数，可单测） |
| `server/app/inference.py` | 加载模型、串行锁、调用 ShutterMuse |
| `server/app/main.py` | FastAPI 路由 `/health`, `/v1/composition` |
| `server/tests/test_response_mapper.py` | decision/bbox 映射单元测试 |
| `server/tests/test_api.py` | API 集成测试（mock 推理） |
| `server/requirements-server.txt` | fastapi, uvicorn, httpx, pytest |
| `server/README.md` | 启动与环境变量说明 |
| `android-app/...` | CameraX + 网络 + 叠加层 UI |

---

## Phase A — Inference Server

### Task 1: Server 依赖与包结构

**Files:**
- Create: `server/requirements-server.txt`
- Create: `server/app/__init__.py`
- Create: `server/app/schemas.py`

- [ ] **Step 1: 创建 requirements-server.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-multipart>=0.0.9
pydantic>=2.0.0
pytest>=8.0.0
httpx>=0.27.0
```

- [ ] **Step 2: 创建空 `server/app/__init__.py`**

- [ ] **Step 3: 创建 schemas.py**

```python
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)


Decision = Literal["keep", "refine", "reject"]


class CompositionResponse(BaseModel):
    decision: Decision
    bbox: Optional[BBox] = None
    message: Optional[str] = None
    latency_ms: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
```

- [ ] **Step 4: 安装依赖**

```bash
cd server
pip install -r requirements-server.txt
```

Expected: 安装成功，无报错。

---

### Task 2: 响应映射（decision + 归一化 bbox）

**Files:**
- Create: `server/app/response_mapper.py`
- Create: `server/tests/test_response_mapper.py`
- Test: `server/tests/test_response_mapper.py`

逻辑对齐 `evaluation/photographer-side/evaluate_benchmark.py` 中 `_pred_decision_type`：`crop` → API 的 `refine`。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_response_mapper.py
import pytest

from app.response_mapper import map_inference_to_response


def test_reject_when_non_marker():
    result = map_inference_to_response(
        output_text='{"instance_info":[{"composition_xy":""}]}<non>',
        pred_bbox_px=None,
        image_width=1000,
        image_height=800,
    )
    assert result["decision"] == "reject"
    assert result["bbox"] is None


def test_keep_when_full_image_bbox():
    result = map_inference_to_response(
        output_text="ok",
        pred_bbox_px=[0.0, 0.0, 1000.0, 800.0],
        image_width=1000,
        image_height=800,
    )
    assert result["decision"] == "keep"
    assert result["bbox"] is not None
    assert result["bbox"]["x1"] == pytest.approx(0.0)
    assert result["bbox"]["x2"] == pytest.approx(1.0)


def test_refine_when_partial_bbox():
    result = map_inference_to_response(
        output_text="ok",
        pred_bbox_px=[100.0, 80.0, 900.0, 720.0],
        image_width=1000,
        image_height=800,
    )
    assert result["decision"] == "refine"
    assert result["bbox"]["x1"] == pytest.approx(0.1)
    assert result["bbox"]["y1"] == pytest.approx(0.1)


def test_reject_when_no_bbox():
    result = map_inference_to_response(
        output_text="no box",
        pred_bbox_px=None,
        image_width=640,
        image_height=480,
    )
    assert result["decision"] == "reject"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server && pytest tests/test_response_mapper.py -v
```

Expected: FAIL — `ModuleNotFoundError: app.response_mapper`

- [ ] **Step 3: 实现 response_mapper.py**

```python
# server/app/response_mapper.py
from typing import Any, Dict, List, Optional


def _has_non_reject_marker(output_text: str) -> bool:
    return "<non>" in str(output_text or "").lower()


def _is_full_image_bbox(
    bbox: List[float], image_width: int, image_height: int, tolerance: float = 0.02
) -> bool:
    if not bbox or len(bbox) != 4:
        return False
    x1, y1, x2, y2 = [float(v) for v in bbox]
    w, h = float(image_width), float(image_height)
    if w <= 0 or h <= 0:
        return False
    return (
        abs(x1) <= w * tolerance
        and abs(y1) <= h * tolerance
        and abs(x2 - w) <= w * tolerance
        and abs(y2 - h) <= h * tolerance
    )


def _px_bbox_to_normalized(
    bbox: List[float], image_width: int, image_height: int
) -> Optional[Dict[str, float]]:
    if not bbox or len(bbox) != 4 or image_width <= 0 or image_height <= 0:
        return None
    x1, y1, x2, y2 = [float(v) for v in bbox]
    if x2 <= x1 or y2 <= y1:
        return None
    return {
        "x1": max(0.0, min(1.0, x1 / image_width)),
        "y1": max(0.0, min(1.0, y1 / image_height)),
        "x2": max(0.0, min(1.0, x2 / image_width)),
        "y2": max(0.0, min(1.0, y2 / image_height)),
    }


def map_inference_to_response(
    output_text: str,
    pred_bbox_px: Optional[List[float]],
    image_width: int,
    image_height: int,
) -> Dict[str, Any]:
    if _has_non_reject_marker(output_text) or not pred_bbox_px:
        return {"decision": "reject", "bbox": None, "message": "当前画面不适合拍摄"}

    if _is_full_image_bbox(pred_bbox_px, image_width, image_height):
        norm = _px_bbox_to_normalized(pred_bbox_px, image_width, image_height)
        return {"decision": "keep", "bbox": norm, "message": "当前构图良好"}

    norm = _px_bbox_to_normalized(pred_bbox_px, image_width, image_height)
    if norm is None:
        return {"decision": "reject", "bbox": None, "message": "无法解析构图结果"}
    return {"decision": "refine", "bbox": norm, "message": "建议按红框裁剪"}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd server && pytest tests/test_response_mapper.py -v
```

Expected: 4 passed

---

### Task 3: FastAPI 路由（mock 推理）

**Files:**
- Create: `server/app/main.py`
- Create: `server/tests/test_api.py`

- [ ] **Step 1: 写 API 失败测试（mock 推理，不加载 GPU 模型）**

```python
# server/tests/test_api.py
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app, set_inference_handler_for_tests


@pytest.fixture
def client():
    return TestClient(app)


def test_health_not_loaded_by_default(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is False


def test_composition_returns_503_when_model_not_ready(client):
    resp = client.post(
        "/v1/composition",
        files={"image": ("test.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODEL_NOT_READY"


def test_composition_success_with_mock_handler(client):
    def fake_handler(image_bytes: bytes):
        return {
            "output_text": "ok",
            "pred_bbox_px": [10.0, 10.0, 90.0, 90.0],
            "image_width": 100,
            "image_height": 100,
        }

    set_inference_handler_for_tests(fake_handler, model_loaded=True)
    resp = client.post(
        "/v1/composition",
        files={"image": ("test.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "refine"
    assert "latency_ms" in body
    set_inference_handler_for_tests(None, model_loaded=False)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd server && pytest tests/test_api.py -v
```

Expected: FAIL — `ModuleNotFoundError: app.main`

- [ ] **Step 3: 实现 main.py（含测试 hook，MVP 串行锁占位）**

```python
# server/app/main.py
import io
import os
import threading
import time
from typing import Callable, Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from app.response_mapper import map_inference_to_response
from app.schemas import CompositionResponse, ErrorResponse, HealthResponse

app = FastAPI(title="ShutterMuse Composition API", version="0.1.0")

_inference_lock = threading.Lock()
_model_loaded = False
_test_handler: Optional[Callable[[bytes], dict]] = None

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))


def set_inference_handler_for_tests(handler, model_loaded: bool):
    global _test_handler, _model_loaded
    _test_handler = handler
    _model_loaded = model_loaded


def mark_model_loaded(loaded: bool):
    global _model_loaded
    _model_loaded = loaded


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", model_loaded=_model_loaded)


def _error(status: int, code: str, message: str):
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(error={"code": code, "message": message}).model_dump(),
    )


@app.post("/v1/composition")
async def composition(image: UploadFile = File(...)):
    if not _model_loaded:
        return _error(503, "MODEL_NOT_READY", "模型尚未加载完成")

    raw = await image.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        return _error(400, "PAYLOAD_TOO_LARGE", "图片超过大小上限")
    if not raw:
        return _error(400, "INVALID_IMAGE", "空文件")

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            width, height = img.size
    except UnidentifiedImageError:
        return _error(400, "INVALID_IMAGE", "无法识别的图片格式")

    if not _inference_lock.acquire(blocking=False):
        return _error(503, "MODEL_BUSY", "推理服务忙，请稍后重试")

    started = time.perf_counter()
    try:
        if _test_handler is not None:
            payload = _test_handler(raw)
        else:
            from app.inference import run_photographer_inference

            payload = run_photographer_inference(raw)
        mapped = map_inference_to_response(
            output_text=payload["output_text"],
            pred_bbox_px=payload.get("pred_bbox_px"),
            image_width=payload["image_width"],
            image_height=payload["image_height"],
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return CompositionResponse(
            decision=mapped["decision"],
            bbox=mapped.get("bbox"),
            message=mapped.get("message"),
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return _error(500, "INFERENCE_FAILED", f"推理失败: {exc}")
    finally:
        _inference_lock.release()
```

- [ ] **Step 4: 运行测试**

```bash
cd server && pytest tests/test_api.py -v
```

Expected: 3 passed

---

### Task 4: 推理适配层（复用 ShutterMuse 脚本）

**Files:**
- Create: `server/app/inference.py`
- Modify: `server/app/main.py`（startup 加载模型）

- [ ] **Step 1: 实现 inference.py**

```python
# server/app/inference.py
import io
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageOps

# 将 evaluation/photographer-side 加入 import 路径
REPO_ROOT = Path(__file__).resolve().parents[2]
PHOTOGRAPHER_DIR = REPO_ROOT / "evaluation" / "photographer-side"
if str(PHOTOGRAPHER_DIR) not in sys.path:
    sys.path.insert(0, str(PHOTOGRAPHER_DIR))

from infer_single_qwen_lora import (  # noqa: E402
    build_default_instruction,
    load_qwen_model,
    run_inference,
)
from utils import parse_qwen_bbox  # noqa: E402

_model = None
_processor = None


def load_model_on_startup() -> None:
    global _model, _processor
    model_path = os.environ["SHUTTERMUSE_MODEL_PATH"]
    lora_path = os.environ.get("SHUTTERMUSE_LORA_PATH", "")
    _model, _processor = load_qwen_model(
        model_path=model_path,
        lora_path=lora_path,
        trust_remote_code=True,
        merge_lora=True,
    )


def run_photographer_inference(image_bytes: bytes) -> Dict:
    if _model is None or _processor is None:
        raise RuntimeError("Model not loaded")

    with Image.open(io.BytesIO(image_bytes)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
    width, height = image.size
    instruction = build_default_instruction("photographer", image)
    output_text = run_inference(
        model=_model,
        processor=_processor,
        image=image,
        instruction=instruction,
        max_new_tokens=512,
        device="cuda",
        side="photographer",
    )
    pred_bbox_px: Optional[List[float]] = parse_qwen_bbox(output_text, width, height)
    return {
        "output_text": output_text,
        "pred_bbox_px": pred_bbox_px,
        "image_width": width,
        "image_height": height,
    }
```

- [ ] **Step 2: 在 main.py 添加 lifespan 加载模型**

在 `main.py` 顶部增加：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("SKIP_MODEL_LOAD") == "1":
        mark_model_loaded(False)
    else:
        from app.inference import load_model_on_startup
        load_model_on_startup()
        mark_model_loaded(True)
    yield

app = FastAPI(..., lifespan=lifespan)
```

- [ ] **Step 3: 写 server/README.md**

包含：

```bash
export SHUTTERMUSE_MODEL_PATH=/path/to/Qwen3-VL-8B-Instruct
export SHUTTERMUSE_LORA_PATH=/path/to/shuttermuse-lora
export SKIP_MODEL_LOAD=1   # 仅跑 pytest 时使用
cd server
pip install -r requirements-server.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

curl 验证：

```bash
curl -s http://127.0.0.1:8000/health
curl -s -F "image=@../test/401128801616615964.webp" http://127.0.0.1:8000/v1/composition
```

- [ ] **Step 4: GPU 环境手动验证**

Expected: `/health` → `model_loaded: true`；POST 返回 `decision` + 可选 `bbox`。

---

## Phase B — Android App

### Task 5: Android 工程脚手架

**Files:**
- Create: `android-app/`（Android Studio 新建 Empty Activity 项目）
- Package: `com.shuttermuse.app`
- minSdk: 24, targetSdk: 34

- [ ] **Step 1: Android Studio → New Project → Empty Activity**

  - Name: `ShutterMuse`
  - Package: `com.shuttermuse.app`
  - Language: Kotlin
  - Minimum SDK: API 24

- [ ] **Step 2: `app/build.gradle.kts` 添加依赖**

```kotlin
dependencies {
    implementation("androidx.camera:camera-camera2:1.4.1")
    implementation("androidx.camera:camera-lifecycle:1.4.1")
    implementation("androidx.camera:camera-view:1.4.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
```

- [ ] **Step 3: `AndroidManifest.xml` 添加权限与 cleartext**

```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.INTERNET" />

<application
    android:usesCleartextTraffic="true"
    ...>
```

局域网 HTTP 调试需要 `usesCleartextTraffic="true"`。

- [ ] **Step 4: 创建 `app/src/main/res/values/strings.xml` 条目**

```xml
<string name="base_url">http://192.168.1.100:8000</string>
```

开发时改成 GPU 机器局域网 IP。

---

### Task 6: 数据模型与 bbox 换算（JUnit）

**Files:**
- Create: `android-app/app/src/main/java/com/shuttermuse/app/network/CompositionModels.kt`
- Create: `android-app/app/src/main/java/com/shuttermuse/app/ui/BboxMapper.kt`
- Create: `android-app/app/src/test/java/com/shuttermuse/app/ui/BboxMapperTest.kt`

- [ ] **Step 1: CompositionModels.kt**

```kotlin
package com.shuttermuse.app.network

data class NormBBox(val x1: Float, val y1: Float, val x2: Float, val y2: Float)

data class CompositionResult(
    val decision: String,
    val bbox: NormBBox?,
    val message: String?,
    val latencyMs: Int?
)

data class ApiError(val code: String, val message: String)
```

- [ ] **Step 2: BboxMapperTest（先写测试）**

```kotlin
package com.shuttermuse.app.ui

import com.shuttermuse.app.network.NormBBox
import org.junit.Assert.assertEquals
import org.junit.Test

class BboxMapperTest {
    @Test
    fun mapsNormalizedToViewPixels() {
        val rect = BboxMapper.toViewRect(
            bbox = NormBBox(0.1f, 0.2f, 0.9f, 0.8f),
            viewWidth = 1000,
            viewHeight = 500
        )
        assertEquals(100f, rect.left, 0.01f)
        assertEquals(100f, rect.top, 0.01f)
        assertEquals(900f, rect.right, 0.01f)
        assertEquals(400f, rect.bottom, 0.01f)
    }
}
```

- [ ] **Step 3: BboxMapper.kt**

```kotlin
package com.shuttermuse.app.ui

import android.graphics.RectF
import com.shuttermuse.app.network.NormBBox

object BboxMapper {
    fun toViewRect(bbox: NormBBox, viewWidth: Int, viewHeight: Int): RectF {
        return RectF(
            bbox.x1 * viewWidth,
            bbox.y1 * viewHeight,
            bbox.x2 * viewWidth,
            bbox.y2 * viewHeight
        )
    }
}
```

- [ ] **Step 4: 运行单元测试**

Android Studio: Run `BboxMapperTest`

Expected: PASS

---

### Task 7: 网络客户端

**Files:**
- Create: `android-app/app/src/main/java/com/shuttermuse/app/network/CompositionApi.kt`

- [ ] **Step 1: 实现 OkHttp multipart 上传**

```kotlin
package com.shuttermuse.app.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class CompositionApi(private val baseUrl: String) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    fun analyzeJpeg(jpegBytes: ByteArray): Result<CompositionResult> {
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                "image",
                "frame.jpg",
                jpegBytes.toRequestBody("image/jpeg".toMediaType())
            )
            .build()

        val request = Request.Builder()
            .url("$baseUrl/v1/composition")
            .post(body)
            .build()

        client.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val err = runCatching {
                    JSONObject(text).getJSONObject("error").let {
                        ApiError(it.getString("code"), it.getString("message"))
                    }
                }.getOrElse { ApiError("HTTP_${response.code}", text) }
                return Result.failure(IllegalStateException("${err.code}: ${err.message}"))
            }
            val json = JSONObject(text)
            val bboxObj = json.optJSONObject("bbox")
            val bbox = bboxObj?.let {
                NormBBox(
                    x1 = it.getDouble("x1").toFloat(),
                    y1 = it.getDouble("y1").toFloat(),
                    x2 = it.getDouble("x2").toFloat(),
                    y2 = it.getDouble("y2").toFloat()
                )
            }
            return Result.success(
                CompositionResult(
                    decision = json.getString("decision"),
                    bbox = bbox,
                    message = json.optString("message", null),
                    latencyMs = json.optInt("latency_ms")
                )
            )
        }
    }
}
```

---

### Task 8: CameraX 预览与抓帧

**Files:**
- Create: `android-app/app/src/main/java/com/shuttermuse/app/camera/CameraController.kt`
- Modify: `android-app/app/src/main/res/layout/activity_main.xml`

- [ ] **Step 1: activity_main.xml 布局**

```xml
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <androidx.camera.view.PreviewView
        android:id="@+id/previewView"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />

    <com.shuttermuse.app.ui.CompositionOverlayView
        android:id="@+id/overlayView"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />

    <TextView
        android:id="@+id/statusText"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_gravity="top"
        android:padding="12dp"
        android:textColor="@android:color/white"
        android:background="#66000000"
        android:text="就绪" />

    <Button
        android:id="@+id/analyzeButton"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="bottom|center_horizontal"
        android:layout_marginBottom="32dp"
        android:text="分析构图" />
</FrameLayout>
```

- [ ] **Step 2: CameraController.kt — 启动 Preview + ImageCapture**

使用 CameraX `Preview` + `ImageCapture`；`captureJpeg(maxLongEdge=1280, quality=85)` 返回 `ByteArray`。

- [ ] **Step 3: 权限请求**

`MainActivity` 使用 `ActivityResultContracts.RequestPermission` 请求 `CAMERA`。

---

### Task 9: 叠加层与 UI 状态机

**Files:**
- Create: `android-app/app/src/main/java/com/shuttermuse/app/ui/CompositionOverlayView.kt`
- Modify: `android-app/app/src/main/java/com/shuttermuse/app/MainActivity.kt`

- [ ] **Step 1: CompositionOverlayView 画红框**

自定义 `View`，持有 `RectF?`；`refine` 时红色描边，`keep`/`reject` 时可清空或画满幅淡绿框。

- [ ] **Step 2: MainActivity 状态机**

```text
idle → 点击分析 → loading（禁用按钮）
loading → success（更新 overlay + statusText）
loading → error（Toast + statusText）
```

后台线程调用 `CompositionApi.analyzeJpeg`；UI 更新切回主线程。

decision 文案：

| decision | statusText |
|----------|------------|
| keep | 当前构图良好 |
| refine | 建议按红框裁剪 |
| reject | 建议换角度或重拍 |

---

### Task 10: 端到端联调与验收

**Files:**
- Create: `android-app/README.md`

- [ ] **Step 1: 同一 Wi-Fi 下启动 server（GPU 机器）**

```bash
export SHUTTERMUSE_MODEL_PATH=...
export SHUTTERMUSE_LORA_PATH=...
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: 修改 App `base_url` 为 GPU 局域网 IP**

- [ ] **Step 3: 真机安装 APK，验收 MVP 清单**

- [ ] 打开 App 看到相机预览
- [ ] 点「分析构图」→ loading → 3–15 秒内出结果
- [ ] 至少一次看到红框（refine）或「构图良好」（keep）

- [ ] **Step 4: 写 android-app/README.md**

包含：改 IP、装 APK、常见问题（连不上 / 超时 / 模型未加载）。

---

## Spec Coverage Self-Review

| Spec 章节 | 对应 Task |
|-----------|-----------|
| 总体架构 | Task 3–4, 7–9 |
| Android 组件 | Task 5–9 |
| Server 组件 | Task 1–4 |
| API 规格 | Task 2–3 |
| decision 语义 | Task 2 |
| 错误处理 | Task 3, 7, 9 |
| 坐标归一化 | Task 2, 6 |
| 测试策略 | Task 2, 6, 10 |
| 项目结构 | File Map |
| README 交付 | Task 4, 10 |

无 TBD / 占位符。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-shuttermuse-android-app.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派一个全新 subagent，任务间做 spec + 质量两轮 review，迭代快。
2. **Inline Execution** — 在本会话用 `executing-plans` 批量执行，每 2–3 个 Task 设人工检查点。

**Which approach?**
