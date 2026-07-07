import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app, set_inference_handler_for_tests, set_pose_handler_for_tests


def _make_test_jpeg(width: int = 100, height: int = 100) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color="red").save(buf, format="JPEG")
    return buf.getvalue()


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
        files={"image": ("test.jpg", io.BytesIO(_make_test_jpeg()), "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "refine"
    assert "latency_ms" in body
    set_inference_handler_for_tests(None, model_loaded=False)


def test_pose_returns_503_when_model_not_ready(client):
    resp = client.post(
        "/v1/pose",
        files={"image": ("test.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODEL_NOT_READY"


def test_pose_success_with_mock_handler(client):
    def fake_pose_handler(image_bytes: bytes):
        keypoints_xyn = [[0.5, 0.3 + i * 0.02] for i in range(3)] + [[0.0, 0.0]] * 14
        visibility = [1, -1, -1, -1, -1, 1, 1] + [-1] * 10
        return {
            "record": {
                "instance_info": [
                    {
                        "keypoints_xyn": keypoints_xyn,
                        "visibility": visibility,
                    }
                ]
            }
        }

    set_pose_handler_for_tests(fake_pose_handler, model_loaded=True)
    resp = client.post(
        "/v1/pose",
        files={"image": ("test.jpg", io.BytesIO(_make_test_jpeg()), "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["keypoints"]) == 17
    assert body["parse_ok"] is True
    assert "latency_ms" in body
    set_pose_handler_for_tests(None, model_loaded=False)
