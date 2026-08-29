import json
import zipfile
from pathlib import Path

from pigproject.aihub_71471_profile import load_71471_profile_rows, summarize_71471


def test_load_71471_profile_rows_from_keypoint_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "TL_3.돼지_01.이미지_002.keypoints.zip"
    payload = {
        "IMAGE": {
            "IMAGE_FILE_NAME": "pigfarmA_ch10_2022071510_025_15443.jpg",
            "IMAGE_URL": "https://example.test/image.jpg",
            "WIDTH": 1920,
            "HEIGHT": 1080,
            "TIMESTAMP": 15443,
            "FARMID": "pigfarmA",
            "FARMSCALE": 1,
            "HEADCOUNT": 500,
            "RECORD_TIME": 22,
        },
        "ANNOTATION_INFO": [
            {
                "ID": 1,
                "KEYPOINTS": [10, 20, 2, 30, 40, 1],
                "NUM_KEYPIONTS": 2,
                "CATEGORY_NAME": "pig",
                "ACTION_NAME": "standing",
                "ESTRUS": "N",
                "INJECTION": "Y",
            }
        ],
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("/pigfarmA_ch10_2022071510_025_15443.json", json.dumps(payload))

    df, errors = load_71471_profile_rows(tmp_path)

    assert len(df) == 1
    assert errors.empty
    assert df.loc[0, "dataset_key"] == "71471"
    assert df.loc[0, "split"] == "training"
    assert df.loc[0, "channel"] == 10
    assert df.loc[0, "action_name"] == "standing"
    assert df.loc[0, "visible_keypoints"] == 2


def test_summarize_71471_counts_actions_and_estrus(tmp_path: Path) -> None:
    zip_path = tmp_path / "VL_3.돼지_01.이미지_002.keypoints.zip"
    payload = {
        "IMAGE": {
            "IMAGE_FILE_NAME": "pigfarmA_ch10_2022071510_025_15443.jpg",
            "TIMESTAMP": 15443,
            "FARMID": "pigfarmA",
        },
        "ANNOTATION_INFO": [
            {"ID": 1, "KEYPOINTS": [10, 20, 2], "ACTION_NAME": "lying", "ESTRUS": "Y"},
            {"ID": 2, "KEYPOINTS": [30, 40, 1], "ACTION_NAME": "standing", "ESTRUS": "N"},
        ],
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("/pigfarmA_ch10_2022071510_025_15443.json", json.dumps(payload))

    df, errors = load_71471_profile_rows(tmp_path)
    summaries = summarize_71471(df)

    assert errors.empty
    split_row = summaries["split_summary"].iloc[0]
    assert split_row["annotations"] == 2
    assert split_row["frames"] == 1
    assert split_row["estrus_positive"] == 1
    assert split_row["estrus_negative"] == 1


def test_load_71471_profile_rows_records_malformed_json(tmp_path: Path) -> None:
    zip_path = tmp_path / "TL_3.돼지_01.이미지_002.keypoints.zip"
    payload = {
        "IMAGE": {
            "IMAGE_FILE_NAME": "pigfarmA_ch10_2022071510_025_15443.jpg",
            "TIMESTAMP": 15443,
            "FARMID": "pigfarmA",
        },
        "ANNOTATION_INFO": [
            {"ID": 1, "KEYPOINTS": [10, 20, 2], "ACTION_NAME": "lying", "ESTRUS": "Y"},
        ],
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("/good.json", json.dumps(payload))
        archive.writestr("/bad.json", '{"IMAGE": ')

    df, errors = load_71471_profile_rows(tmp_path)

    assert len(df) == 1
    assert len(errors) == 1
    assert errors.loc[0, "member_name"] == "/bad.json"
