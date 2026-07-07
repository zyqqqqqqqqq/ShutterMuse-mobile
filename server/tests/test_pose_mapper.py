from app.pose_mapper import map_subject_record_to_response


def test_map_subject_record_pads_to_17_keypoints():
    record = {
        "instance_info": [
            {
                "keypoints_xyn": [[0.5, 0.3], [0.4, 0.2]],
                "visibility": [1, 1],
            }
        ]
    }
    mapped = map_subject_record_to_response(record)
    assert len(mapped["keypoints"]) == 17
    assert mapped["parse_ok"] is True
    assert mapped["keypoints"][0]["x"] == 0.5


def test_map_subject_record_empty_fails_gracefully():
    mapped = map_subject_record_to_response({"instance_info": []})
    assert mapped["parse_ok"] is False
    assert len(mapped["keypoints"]) == 17
