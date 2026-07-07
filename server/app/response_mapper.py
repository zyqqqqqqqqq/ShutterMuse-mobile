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
