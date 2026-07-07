from app.subject_parse import parse_subject_record, try_parse_obj

NAMED_SAMPLE = """```json
{
  "nose": {"x": 0.5, "y": 0.2, "visible": true},
  "left_eye": {"x": 0.4, "y": 0.25, "visible": true},
  "right_eye": {"x": 0.6, "y": 0.25, "visible": true},
  "left_ear": {"x": 0.35, "y": 0.3, "visible": true},
  "right_ear": {"x": 0.65, "y": 0.3, "visible": true},
  "left_shoulder": {"x": 0.3, "y": 0.4, "visible": true},
  "right_shoulder": {"x": 0.7, "y": 0.4, "visible": true},
  "left_elbow": {"x": 0.25, "y": 0.55, "visible": true},
  "right_elbow": {"x": 0.75, "y": 0.55, "visible": true},
  "left_wrist": {"x": 0.2, "y": 0.7, "visible": true},
  "right_wrist": {"x": 0.8, "y": 0.7, "visible": true},
  "left_hip": {"x": 0.25, "y": 0.85, "visible": true},
  "right_hip": {"x": 0.75, "y": 0.85, "visible": true},
  "left_knee": {"x": 0.25, "y": 1.0, "visible": true},
  "right_knee": {"x": 0.75, "y": 1.0, "visible": true},
  "left_ankle": {"x": 0.25, "y": 1.15, "visible": true},
  "right_ankle": {"x": 0.75, "y": 1.15, "visible": true}
}
```"""


def test_parse_named_keypoint_format():
    record = parse_subject_record(NAMED_SAMPLE)
    assert record["instance_info"]
    assert len(record["instance_info"][0]["keypoints_xyn"]) == 17


def test_try_parse_obj_from_json_block():
    text = '说明文字 {"instance_info": [{"keypoints_xyn": [[0.5, 0.3]], "visibility": [1]}]}'
    obj = try_parse_obj(text)
    assert obj is not None
    assert "instance_info" in obj


def test_parse_subject_record_returns_empty_on_bad_json():
    record = parse_subject_record("not json at all")
    assert record["instance_info"] == []
    assert "parse_error" in record["meta"]
