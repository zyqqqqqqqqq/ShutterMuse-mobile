from typing import Any, Dict, List, Optional


COCO17_NAMES = (
    "鼻子", "左眼", "右眼", "左耳", "右耳",
    "左肩", "右肩", "左肘", "右肘", "左腕", "右腕",
    "左髋", "右髋", "左膝", "右膝", "左脚踝", "右脚踝",
)


def _failure_message(record: Dict[str, Any]) -> str:
    meta = record.get("meta") or {}
    parse_error = str(meta.get("parse_error") or "").strip()
    raw_text = str(meta.get("raw_text") or "").strip().lower()

    if any(k in raw_text for k in ("无人", "没有人物", "未检测到人", "no person", "no human")):
        return "模型未给出场景摆姿推荐，请换一张背景更明确的拍摄场景重试"
    if parse_error:
        if "cannot parse" in parse_error.lower() or "json" in parse_error.lower():
            preview = str(meta.get("raw_text") or "")[:120].strip()
            if preview:
                return f"模型未返回有效摆姿 JSON。输出摘要：{preview}…"
            return "模型未返回有效摆姿 JSON，请换一张更适合人像拍摄的场景重试"
    return "无法解析摆姿推荐结果，请换场景重试或检查 Server 配置"


def map_subject_record_to_response(record: Dict[str, Any]) -> Dict[str, Any]:
    instance_info = record.get("instance_info") or []
    if not instance_info or not isinstance(instance_info[0], dict):
        return {
            "keypoints": [None] * 17,
            "message": _failure_message(record),
            "parse_ok": False,
        }

    inst = instance_info[0]
    keypoints_xyn = inst.get("keypoints_xyn") or []
    visibility = inst.get("visibility") or []
    keypoints: List[Optional[Dict[str, float]]] = []

    for idx in range(17):
        if idx >= len(keypoints_xyn):
            keypoints.append(None)
            continue
        point = keypoints_xyn[idx]
        vis = visibility[idx] if idx < len(visibility) else 1
        visible = vis not in (-1, 0, False, None)
        if (
            not visible
            or not isinstance(point, (list, tuple))
            or len(point) < 2
        ):
            keypoints.append(None)
            continue
        keypoints.append(
            {
                "x": max(0.0, min(1.0, float(point[0]))),
                "y": max(0.0, min(1.0, float(point[1]))),
                "visible": True,
            }
        )

    visible_count = sum(1 for kp in keypoints if kp is not None)
    reason = str(record.get("reason") or inst.get("reason") or "").strip()
    if visible_count == 0:
        return {
            "keypoints": keypoints,
            "message": reason or "未生成有效摆姿推荐，请换一张更适合人像拍摄的场景",
            "parse_ok": False,
        }

    message = reason or f"已识别 {visible_count} 个摆姿关键点"
    return {
        "keypoints": keypoints,
        "message": message,
        "parse_ok": True,
    }
