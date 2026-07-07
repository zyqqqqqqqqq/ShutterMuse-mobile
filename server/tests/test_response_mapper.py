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
