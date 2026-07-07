import io

import os

import threading

import time

from contextlib import asynccontextmanager

from typing import Callable, Optional



from fastapi import FastAPI, File, UploadFile

from fastapi.responses import JSONResponse

from PIL import Image, UnidentifiedImageError



from app.pose_mapper import map_subject_record_to_response

from app.response_mapper import map_inference_to_response

from app.schemas import CompositionResponse, ErrorResponse, HealthResponse, PoseResponse





@asynccontextmanager

async def lifespan(app: FastAPI):

    if os.environ.get("SKIP_MODEL_LOAD") == "1":

        mark_model_loaded(False)

    else:

        from app.inference import load_model_on_startup



        load_model_on_startup()

        mark_model_loaded(True)

    yield





app = FastAPI(

    title="ShutterMuse Composition API",

    version="0.2.0",

    lifespan=lifespan,

)



_inference_lock = threading.Lock()

_model_loaded = False

_test_composition_handler: Optional[Callable[[bytes], dict]] = None

_test_pose_handler: Optional[Callable[[bytes], dict]] = None



MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))





def set_inference_handler_for_tests(handler, model_loaded: bool):

    global _test_composition_handler, _model_loaded

    _test_composition_handler = handler

    _model_loaded = model_loaded





def set_pose_handler_for_tests(handler, model_loaded: bool):

    global _test_pose_handler, _model_loaded

    _test_pose_handler = handler

    _model_loaded = model_loaded





def mark_model_loaded(loaded: bool):

    global _model_loaded

    _model_loaded = loaded





def _health_detail() -> tuple[Optional[str], Optional[str]]:

    if os.environ.get("SKIP_MODEL_LOAD") == "1":

        return "none", "推理服务未配置，请设置 DASHSCOPE_API_KEY 后重启 Server"

    try:

        from app.inference import get_inference_backend



        backend = get_inference_backend()

    except Exception as exc:

        return "unknown", f"配置错误: {exc}"

    if backend == "api":

        return "qwen-vl-api", None

    return "local-qwen", None





@app.get("/health", response_model=HealthResponse)

def health():

    backend, detail = _health_detail()

    if _model_loaded:

        detail = None

    return HealthResponse(

        status="ok",

        model_loaded=_model_loaded,

        backend=backend,

        detail=detail,

    )





def _error(status: int, code: str, message: str):

    return JSONResponse(

        status_code=status,

        content=ErrorResponse(error={"code": code, "message": message}).model_dump(),

    )





def _read_upload_image(raw: bytes):

    if len(raw) > MAX_UPLOAD_BYTES:

        return None, _error(400, "PAYLOAD_TOO_LARGE", "图片超过大小上限")

    if not raw:

        return None, _error(400, "INVALID_IMAGE", "空文件")

    try:

        with Image.open(io.BytesIO(raw)) as img:

            img.convert("RGB")

    except UnidentifiedImageError:

        return None, _error(400, "INVALID_IMAGE", "无法识别的图片格式")

    return raw, None





@app.post("/v1/composition")

async def composition(image: UploadFile = File(...)):

    if not _model_loaded:

        return _error(503, "MODEL_NOT_READY", "模型尚未加载完成")



    raw = await image.read()

    raw, err = _read_upload_image(raw)

    if err is not None:

        return err



    if not _inference_lock.acquire(blocking=False):

        return _error(503, "MODEL_BUSY", "推理服务忙，请稍后重试")



    started = time.perf_counter()

    try:

        if _test_composition_handler is not None:

            payload = _test_composition_handler(raw)

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





@app.post("/v1/pose")

async def pose(image: UploadFile = File(...)):

    if not _model_loaded:

        return _error(503, "MODEL_NOT_READY", "模型尚未加载完成")



    raw = await image.read()

    raw, err = _read_upload_image(raw)

    if err is not None:

        return err



    if not _inference_lock.acquire(blocking=False):

        return _error(503, "MODEL_BUSY", "推理服务忙，请稍后重试")



    started = time.perf_counter()

    try:

        if _test_pose_handler is not None:

            payload = _test_pose_handler(raw)

        else:

            from app.inference import run_subject_inference



            payload = run_subject_inference(raw)

        mapped = map_subject_record_to_response(payload["record"])

        latency_ms = int((time.perf_counter() - started) * 1000)

        return PoseResponse(

            keypoints=mapped["keypoints"],

            message=mapped["message"],

            parse_ok=mapped["parse_ok"],

            latency_ms=latency_ms,

        )

    except Exception as exc:

        return _error(500, "INFERENCE_FAILED", f"推理失败: {exc}")

    finally:

        _inference_lock.release()


