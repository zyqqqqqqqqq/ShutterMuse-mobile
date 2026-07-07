"""Torch-free subject-side JSON parsing for API mode."""

import ast
import json
import re
from typing import Any, Dict, List, Optional, Sequence

SUBJECT_PROMPT = (
    "你是一个人像摄影摆姿分析专家。请根据画面中的场景、背景和构图空间，"
    "推荐一个适合在此拍摄的 portrait 摆姿（即使画面里还没有人物）。"
    "以 JSON 输出推荐的人体 17 个关键点相对坐标及可见性，格式："
    '{"instance_info":[{"keypoints_xyn":[[x,y],...共17个],"visibility":[1或0或-1,...共17个]}]} '
    "17 个关键点顺序：鼻子、左眼、右眼、左耳、右耳、左肩、右肩、左肘、右肘、左腕、右腕、"
    "左髋、右髋、左膝、右膝、左脚踝、右脚踝。坐标为 0~1 相对值。只输出 JSON。"
)

KEYPOINT_ALIASES: Sequence[Sequence[str]] = (
    ("nose", "鼻子"),
    ("left_eye", "left_eye", "左眼"),
    ("right_eye", "right_eye", "右眼"),
    ("left_ear", "left_ear", "左耳"),
    ("right_ear", "right_ear", "右耳"),
    ("left_shoulder", "left_shoulder", "左肩"),
    ("right_shoulder", "right_shoulder", "右肩"),
    ("left_elbow", "left_elbow", "左肘", "左手肘"),
    ("right_elbow", "right_elbow", "右肘", "右肘"),
    ("left_wrist", "left_wrist", "左腕", "左手腕"),
    ("right_wrist", "right_wrist", "右腕", "右手腕"),
    ("left_hip", "left_hip", "左髋"),
    ("right_hip", "right_hip", "右髋"),
    ("left_knee", "left_knee", "左膝"),
    ("right_knee", "right_knee", "右膝"),
    ("left_ankle", "left_ankle", "左脚踝"),
    ("right_ankle", "right_ankle", "右脚踝"),
)


def _strip_markdown_fences(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_text(text: str) -> Optional[str]:
    s = _strip_markdown_fences(text)
    start = s.find("{")
    if start == -1:
        start = s.find("[")
    if start == -1:
        return None

    open_ch, close_ch = ("{", "}") if s[start] == "{" else ("[", "]")
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def try_parse_obj(text: str) -> Optional[Any]:
    s = _strip_markdown_fences(text.strip())
    try:
        obj = json.loads(s)
        if isinstance(obj, (dict, list)):
            return obj
    except Exception:
        pass

    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (dict, list)):
            return obj
    except Exception:
        pass

    js = extract_json_text(s)
    if js is not None:
        for fn in (json.loads, ast.literal_eval):
            try:
                obj = fn(js)
                if isinstance(obj, (dict, list)):
                    return obj
            except Exception:
                continue
    return None


def _visibility_from_value(value: Any) -> int:
    if isinstance(value, dict):
        if "visible" in value:
            vis = value["visible"]
            if vis in (True, 1, "1", "true", "True"):
                return 1
            if vis in (False, 0, "0", "false", "False"):
                return 0
            return -1
        if "visibility" in value:
            return _visibility_from_value(value["visibility"])
    try:
        iv = int(float(value))
        if iv > 0:
            return 1
        if iv == 0:
            return 0
        return -1
    except Exception:
        return 1


def _point_from_value(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if isinstance(value, dict):
        x = value.get("x", value.get("X"))
        y = value.get("y", value.get("Y"))
        if x is None or y is None:
            return None
        return [float(x), float(y)]
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    if isinstance(value, str):
        nums = re.findall(r"-?\d+(?:\.\d+)?", value)
        if len(nums) >= 2:
            return [float(nums[0]), float(nums[1])]
    return None


def _normalize_key_name(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", str(name).strip().lower())


def _lookup_named_value(obj: Dict[str, Any], aliases: Sequence[str]) -> Any:
    normalized = {_normalize_key_name(k): v for k, v in obj.items()}
    for alias in aliases:
        key = _normalize_key_name(alias)
        if key in normalized:
            return normalized[key]
    return None


def _coerce_named_dict(obj: Dict[str, Any]) -> Optional[Dict]:
    keypoints: List[List[float]] = []
    visibility: List[int] = []
    found = 0
    for aliases in KEYPOINT_ALIASES:
        value = _lookup_named_value(obj, aliases)
        point = _point_from_value(value)
        if point is None:
            keypoints.append([0.0, 0.0])
            visibility.append(-1)
            continue
        found += 1
        keypoints.append(point)
        visibility.append(_visibility_from_value(value))
    if found == 0:
        return None
    return {"instance_info": [{"keypoints_xyn": keypoints, "visibility": visibility}]}


def _coerce_keypoint_list(items: List[Any]) -> Optional[Dict]:
    keypoints: List[List[float]] = []
    visibility: List[int] = []
    for item in items[:17]:
        point = _point_from_value(item)
        if point is None:
            keypoints.append([0.0, 0.0])
            visibility.append(-1)
        else:
            keypoints.append(point)
            visibility.append(_visibility_from_value(item))
    while len(keypoints) < 17:
        keypoints.append([0.0, 0.0])
        visibility.append(-1)
    if not any(v > 0 for v in visibility):
        return None
    return {"instance_info": [{"keypoints_xyn": keypoints, "visibility": visibility}]}


def _coerce_to_instance_info(obj: Any) -> Dict:
    if isinstance(obj, list):
        coerced = _coerce_keypoint_list(obj)
        if coerced is not None:
            return coerced
        raise ValueError("parsed JSON list has no valid keypoints")

    if not isinstance(obj, dict):
        raise ValueError("parsed JSON is not an object")

    if "instance_info" in obj and isinstance(obj["instance_info"], list) and obj["instance_info"]:
        return obj

    for key in ("keypoints", "keypoints_xyn", "points", "coco17", "keypoint"):
        value = obj.get(key)
        if isinstance(value, list) and value:
            if isinstance(value[0], (list, tuple, dict)):
                coerced = _coerce_keypoint_list(value)
                if coerced is not None:
                    return coerced
            if isinstance(value[0], (int, float)):
                flat = [float(v) for v in value]
                if len(flat) % 2 == 0:
                    pairs = [[flat[i], flat[i + 1]] for i in range(0, len(flat), 2)]
                    coerced = _coerce_keypoint_list(pairs)
                    if coerced is not None:
                        return coerced

    coerced = _coerce_named_dict(obj)
    if coerced is not None:
        return coerced

    return obj


def sanitize_instance_info(obj: Dict) -> Dict:
    obj = _coerce_to_instance_info(obj)
    if "instance_info" in obj and isinstance(obj["instance_info"], list) and obj["instance_info"]:
        inst = obj["instance_info"][0]
    else:
        inst = obj

    keypoints = inst.get("keypoints_xyn", [])
    visibility = inst.get("visibility", [])

    if keypoints and isinstance(keypoints[0], (int, float)):
        if len(keypoints) % 2 == 0:
            keypoints = [
                [float(keypoints[i]), float(keypoints[i + 1])]
                for i in range(0, len(keypoints), 2)
            ]
        else:
            keypoints = []

    cleaned_kpt = []
    for kp in keypoints:
        if isinstance(kp, (list, tuple)) and len(kp) >= 2:
            cleaned_kpt.append([float(kp[0]), float(kp[1])])

    if not cleaned_kpt:
        raise ValueError("parsed JSON has no valid keypoints_xyn")

    if not isinstance(visibility, list) or len(visibility) != len(cleaned_kpt):
        visibility = [1 for _ in cleaned_kpt]
    else:
        visibility = [_visibility_from_value(v) for v in visibility]

    clipped_kpt = [
        [max(0.0, min(1.0, x)), max(0.0, min(1.0, y))]
        for x, y in cleaned_kpt
    ]

    return {
        "instance_info": [
            {
                "visibility": visibility,
                "keypoints_xyn": clipped_kpt,
            }
        ]
    }


def extract_reason_from_obj(obj: Dict) -> str:
    if "instance_info" in obj and isinstance(obj["instance_info"], list) and obj["instance_info"]:
        inst = obj["instance_info"][0]
    else:
        inst = obj
    reason = inst.get("reason", obj.get("reason", ""))
    return "" if reason is None else str(reason)


def parse_subject_record(output_text: str) -> Dict[str, Any]:
    try:
        parsed = try_parse_obj(output_text)
        if parsed is None:
            raise ValueError(f"cannot parse model output as JSON: {output_text[:200]}")
        coerced = _coerce_to_instance_info(parsed)
        result = sanitize_instance_info(coerced)
        reason = extract_reason_from_obj(coerced if isinstance(coerced, dict) else {})
        if reason:
            result["reason"] = reason
        return result
    except Exception as exc:
        return {
            "instance_info": [],
            "meta": {"raw_text": output_text, "parse_error": str(exc)},
        }
