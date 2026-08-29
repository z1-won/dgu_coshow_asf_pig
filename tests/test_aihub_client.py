import json

from pigproject import aihub_client


def test_recommended_downloads_handles_pending_filekeys(tmp_path, monkeypatch) -> None:
    manifest = {
        "71471": {
            "name": "소(한우, 젖소) 및 돼지 발정행동 데이터",
            "track": "pig_behavior_auxiliary",
            "note": "라벨 먼저 확인",
            "recommended_first_downloads": [
                {
                    "split": "Training",
                    "modality": "pig_behavior_label",
                    "filename": "TBD",
                    "size": "TBD",
                    "file_key": None,
                    "reason": "스키마 확인",
                }
            ],
        }
    }
    manifest_path = tmp_path / "aihub_datasets.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(aihub_client, "DATASET_MANIFEST", manifest_path)

    output = aihub_client.recommended_downloads("71471")

    assert "71471" in output
    assert "라벨 먼저 확인" in output
    assert "filekey=TBD after `pig-aihub files`" in output
