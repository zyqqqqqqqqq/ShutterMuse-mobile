import logging
import base64
import io
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[2]
PHOTOGRAPHER_DIR = REPO_ROOT / "evaluation" / "photographer-side"
if str(PHOTOGRAPHER_DIR) not in sys.path:
    sys.path.insert(0, str(PHOTOGRAPHER_DIR))

from utils import get_closest_ratio, parse_qwen_bbox, resize_image_for_inference  # noqa: E402

logger = logging.getLogger(__name__)

_model = None
_processor = None

DEEPSEEK_VISION_ERROR = (
    "DeepSeek 官方 API 不支持图片输入（仅文本模型）。"
    "请改用阿里云百炼 DashScope 的 Qwen-VL：设置 DASHSCOPE_API_KEY，"
    "申请地址 https://dashscope.console.aliyun.com"
)


def get_vision_api_key() -> Optional[str]:
    return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("VISION_API_KEY")


def get_inference_backend() -> str:
    backend = os.environ.get("INFERENCE_BACKEND", "").strip().lower()
    if backend in ("api", "dashscope", "qwen-vl", "deepseek"):
        return "api"
    if backend in ("local", "qwen"):
        return "local"
    if get_vision_api_key():
        return "api"
    return "local"


def validate_api_config() -> None:
    if get_vision_api_key():
        return
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError(DEEPSEEK_VISION_ERROR)
    raise RuntimeError(
        "DASHSCOPE_API_KEY is required for API inference backend. "
        "Get one at https://dashscope.console.aliyun.com"
    )


def build_photographer_instruction(image: Image.Image) -> str:
    image_resize = resize_image_for_inference(image)
    prompt_ratio = get_closest_ratio(image_resize.size[0], image_resize.size[1])
    return (
        f"请找出图片中构图最好的区域，请按照{prompt_ratio}的比例输出bounding box，"
        f"并按照(x1,y1),(x2,y2)的格式返回一个bounding box，其中(x1,y1)是左上角的顶点，"
        f"(x2,y2)是右下角的顶点。"
    )


def _image_to_data_url(image: Image.Image) -> str:
    resized = resize_image_for_inference(image)
    buf = io.BytesIO()
    resized.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_vision_api(
    image: Image.Image,
    instruction: str,
    *,
    system_prompt: str,
    max_tokens: int,
) -> str:
    from openai import OpenAI

    api_key = get_vision_api_key()
    if not api_key:
        raise RuntimeError(DEEPSEEK_VISION_ERROR)

    data_url = _image_to_data_url(image)
    client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get(
            "VISION_API_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )
    model = os.environ.get("VISION_API_MODEL", "qwen-vl-plus")
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    max_retries = int(os.environ.get("VISION_API_MAX_RETRIES", "3"))
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                continue
    raise RuntimeError(f"Vision API call failed after {max_retries} retries: {last_err}")


def load_model_on_startup() -> None:
    if get_inference_backend() == "api":
        validate_api_config()
        return

    global _model, _processor
    from infer_single_qwen_lora import load_qwen_model  # noqa: E402

    model_path = os.environ["SHUTTERMUSE_MODEL_PATH"]
    lora_path = os.environ.get("SHUTTERMUSE_LORA_PATH", "")
    _model, _processor = load_qwen_model(
        model_path=model_path,
        lora_path=lora_path,
        trust_remote_code=True,
        merge_lora=True,
    )


def _run_local_inference(image: Image.Image, instruction: str, side: str) -> str:
    if _model is None or _processor is None:
        raise RuntimeError("Model not loaded")

    from infer_single_qwen_lora import run_inference  # noqa: E402

    max_new_tokens = _local_subject_max_tokens() if side == "subject" else 512
    return run_inference(
        model=_model,
        processor=_processor,
        image=image,
        instruction=instruction,
        max_new_tokens=max_new_tokens,
        device="cuda",
        side=side,
    )


def run_photographer_inference(image_bytes: bytes) -> Dict:
    with Image.open(io.BytesIO(image_bytes)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
    width, height = image.size
    instruction = build_photographer_instruction(image)

    if get_inference_backend() == "api":
        output_text = _call_vision_api(
            image,
            instruction,
            system_prompt="你是严格的摄影构图分析模型，按用户要求输出构图分析和 bounding box。",
            max_tokens=512,
        )
    else:
        output_text = _run_local_inference(image, instruction, side="photographer")

    pred_bbox_px: Optional[List[float]] = parse_qwen_bbox(output_text, width, height)
    return {
        "output_text": output_text,
        "pred_bbox_px": pred_bbox_px,
        "image_width": width,
        "image_height": height,
    }


def build_subject_instruction() -> str:
    if get_inference_backend() == "local":
        from infer_single_qwen_lora import SUBJECT_PROMPT  # noqa: E402

        return SUBJECT_PROMPT
    from app.subject_parse import SUBJECT_PROMPT

    return SUBJECT_PROMPT


def _local_subject_max_tokens() -> int:
    # 4090 24GB: 10240 易 OOM；2048 足够输出 17 点 JSON
    return int(os.environ.get("SUBJECT_MAX_NEW_TOKENS", "2048"))


def _parse_subject_record(output_text: str) -> Dict:
    if get_inference_backend() == "local":
        from infer_single_qwen_lora import build_subject_record  # noqa: E402

        record = build_subject_record(
            output_text=output_text,
            image_path=Path("upload.jpg"),
            image_size=(1, 1),
        )
        if _subject_has_valid_keypoints(record):
            return record
        from app.subject_parse import parse_subject_record

        fallback = parse_subject_record(output_text)
        if _subject_has_valid_keypoints(fallback):
            return fallback
        return record

    from app.subject_parse import parse_subject_record

    return parse_subject_record(output_text)


def _subject_has_valid_keypoints(record: Dict) -> bool:
    instance_info = record.get("instance_info") or []
    if not instance_info or not isinstance(instance_info[0], dict):
        return False
    keypoints = instance_info[0].get("keypoints_xyn") or []
    return bool(keypoints)


def run_subject_inference(image_bytes: bytes) -> Dict:
    with Image.open(io.BytesIO(image_bytes)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
    width, height = image.size
    instruction = build_subject_instruction()

    if get_inference_backend() == "api":
        system_prompt = (
            "你是人像摄影摆姿推荐模型。根据场景与背景推荐被摄者应摆出的姿势，"
            "输出 17 个 COCO 关键点 JSON；画面中可以尚无人，关键点表示建议站位与姿态。"
        )
        output_text = _call_vision_api(
            image,
            instruction,
            system_prompt=system_prompt,
            max_tokens=int(os.environ.get("VISION_API_POSE_MAX_TOKENS", "4096")),
        )
        record = _parse_subject_record(output_text)
        if not _subject_has_valid_keypoints(record):
            retry_instruction = (
                instruction
                + " 上次未输出有效 JSON。请只输出一个 JSON 对象，不要任何解释文字。"
            )
            output_text = _call_vision_api(
                image,
                retry_instruction,
                system_prompt=system_prompt + " 必须只输出 JSON，禁止输出 markdown 或说明文字。",
                max_tokens=int(os.environ.get("VISION_API_POSE_MAX_TOKENS", "4096")),
            )
            record = _parse_subject_record(output_text)
    else:
        output_text = _run_local_inference(image, instruction, side="subject")
        record = _parse_subject_record(output_text)
        if not _subject_has_valid_keypoints(record):
            retry_instruction = (
                instruction + " 请只输出一个 JSON 对象，包含 instance_info 和 17 个关键点，不要其他说明。"
            )
            output_text = _run_local_inference(image, retry_instruction, side="subject")
            record = _parse_subject_record(output_text)

    if not _subject_has_valid_keypoints(record):
        meta = record.get("meta") or {}
        raw_preview = str(meta.get("raw_text") or output_text or "")[:300]
        logger.warning("subject parse failed; output preview: %s", raw_preview)

    return {
        "output_text": output_text,
        "record": record,
        "image_width": width,
        "image_height": height,
    }
