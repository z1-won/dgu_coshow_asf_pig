"""Simple accelerometer-only baseline classifier for the Pig Multimodal
Wearable Dataset's 4-class behavior labels (lying/eating/walking/drinking).

This is NOT part of the main disease/management/environment pipeline -- the
dataset has no pen/farm mapping (see
docs/01_data_understanding/BEHAVIOR_TAXONOMY_COMPARISON.md). It exists so a
future CV/YOLO behavior model has a reference accuracy number to compare
against, and to sanity-check that the released accelerometer features
separate the four classes at all before anyone invests more time in them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from pigproject.activity_model_dataset import dataframe_to_markdown

FEATURE_COLUMNS = [
    "ax_mean", "ax_std", "ax_min", "ax_max",
    "ay_mean", "ay_std", "ay_min", "ay_max",
    "az_mean", "az_std", "az_min", "az_max",
    "mag_mean", "mag_std", "mag_min", "mag_max",
]

# Held out entirely from training. Chosen to give a ~22% test split while
# keeping the held-out group heterogeneous in size (animal 3 is mid-sized,
# 7 and 8 are small) -- fixed rather than random so the report is reproducible.
DEFAULT_TEST_IDS = ["3", "7", "8"]


def build_window_features(long_path: Path) -> pd.DataFrame:
    """Aggregate the 100-row-per-window long-format accelerometer CSV into one row per window."""
    df = pd.read_csv(long_path)
    df["mag"] = np.sqrt(df["AX"] ** 2 + df["AY"] ** 2 + df["AZ"] ** 2)
    grouped = df.groupby(["ID", "janela"], as_index=False).agg(
        label=("label_artigo", "first"),
        ax_mean=("AX", "mean"), ax_std=("AX", "std"), ax_min=("AX", "min"), ax_max=("AX", "max"),
        ay_mean=("AY", "mean"), ay_std=("AY", "std"), ay_min=("AY", "min"), ay_max=("AY", "max"),
        az_mean=("AZ", "mean"), az_std=("AZ", "std"), az_min=("AZ", "min"), az_max=("AZ", "max"),
        mag_mean=("mag", "mean"), mag_std=("mag", "std"), mag_min=("mag", "min"), mag_max=("mag", "max"),
        n_rows=("AX", "size"),
    )
    grouped["ID"] = grouped["ID"].astype(str)
    grouped[FEATURE_COLUMNS] = grouped[FEATURE_COLUMNS].fillna(0.0)
    return grouped


def group_split(features: pd.DataFrame, test_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by animal ID (group), not by window -- windows from the same animal
    are correlated, so a random window-level split would leak individual identity
    into the test score."""
    test_mask = features["ID"].isin(test_ids)
    train = features.loc[~test_mask].reset_index(drop=True)
    test = features.loc[test_mask].reset_index(drop=True)
    return train, test


def train_and_evaluate(
    train: pd.DataFrame, test: pd.DataFrame, seed: int = 0
) -> tuple[RandomForestClassifier, np.ndarray, dict, np.ndarray, float]:
    clf = RandomForestClassifier(n_estimators=300, max_depth=12, random_state=seed, class_weight="balanced")
    clf.fit(train[FEATURE_COLUMNS], train["label"])
    pred = clf.predict(test[FEATURE_COLUMNS])
    labels = sorted(test["label"].unique())
    report_dict = classification_report(test["label"], pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(test["label"], pred, labels=labels)
    macro_f1 = f1_score(test["label"], pred, average="macro", zero_division=0)
    return clf, pred, report_dict, cm, macro_f1


def write_report(
    out_dir: Path,
    train: pd.DataFrame,
    test: pd.DataFrame,
    report_dict: dict,
    cm: np.ndarray,
    macro_f1: float,
    test_ids: list[str],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = sorted(test["label"].unique())

    per_class = pd.DataFrame(
        [
            {
                "label": label,
                "precision": round(report_dict[label]["precision"], 3),
                "recall": round(report_dict[label]["recall"], 3),
                "f1": round(report_dict[label]["f1-score"], 3),
                "support": int(report_dict[label]["support"]),
            }
            for label in labels
        ]
    )
    cm_df = pd.DataFrame(cm, index=[f"true_{l}" for l in labels], columns=[f"pred_{l}" for l in labels])

    train_counts = train["label"].value_counts().to_dict()
    test_counts = test["label"].value_counts().to_dict()

    lines = [
        "# Multimodal Wearable 4-class 행동 분류 베이스라인",
        "",
        "가속도계 window(5초, 100 rows) 통계 feature(mean/std/min/max of AX/AY/AZ + 벡터 크기)만으로 "
        "lying/eating/walking/drinking 4-class를 분류하는 RandomForest 베이스라인입니다. "
        "오디오/log-Mel spectrogram은 쓰지 않았습니다(가속도 단독으로 얼마나 구분되는지 먼저 확인).",
        "",
        "## 데이터 분할",
        "",
        f"개체(ID) 단위로 분할했습니다 — 같은 개체의 window를 train/test에 나눠 넣으면 "
        f"'같은 개체 특성'을 외운 것과 '행동 자체'를 구분한 것을 혼동하게 되기 때문입니다.",
        "",
        f"- test 개체: `{', '.join(test_ids)}` (총 {len(test)} windows, {len(test)/(len(train)+len(test))*100:.1f}%)",
        f"- train 개체: 나머지 5개체 (총 {len(train)} windows)",
        "",
        "### train 라벨 분포",
        "",
        dataframe_to_markdown(pd.DataFrame([train_counts])),
        "",
        "### test 라벨 분포",
        "",
        dataframe_to_markdown(pd.DataFrame([test_counts])),
        "",
        "## 결과",
        "",
        f"**macro F1: {macro_f1:.3f}**",
        "",
        dataframe_to_markdown(per_class),
        "",
        "### Confusion matrix (행: 실제, 열: 예측)",
        "",
        dataframe_to_markdown(cm_df.reset_index().rename(columns={"index": "label"})),
        "",
        "## 해석",
        "",
        "- 개체를 통째로 떼어낸(held-out) 평가이므로, 이 macro F1은 \"본 적 없는 개체에 대한 일반화\" 기준입니다. "
        "같은 개체를 train/test에 섞는 window-level split보다 훨씬 보수적(더 낮게 나오는 게 정상)입니다.",
        "- eating/lying처럼 오래 지속되는 상태는 가속도 패턴이 안정적이라 분류가 쉽고, "
        "walking/drinking처럼 짧고 순간적인 행동은 개체별 움직임 편차에 더 민감할 수 있습니다 "
        "(정확한 원인은 confusion matrix로 직접 확인).",
        "- 이 결과는 622(카메라 키포인트) 모델과 직접 비교할 수 없습니다 — 센서와 라벨 체계가 다릅니다 "
        "(`docs/01_data_understanding/BEHAVIOR_TAXONOMY_COMPARISON.md`). "
        "\"가속도계 신호만으로 행동 분류가 이 정도 성능까지는 나온다\"는 참고 벤치마크로만 쓰세요.",
        "",
        "## 한계",
        "",
        "- 개체 5(train)+3(test)=8마리뿐이라 개체 단위 split의 통계적 신뢰도가 낮습니다 — "
        "다른 3개체를 test로 바꾸면 결과가 달라질 수 있습니다.",
        "- 오디오/log-Mel spectrogram feature는 쓰지 않았습니다. 추가하면 성능이 달라질 수 있습니다.",
    ]
    report = out_dir / "multimodal_behavior_baseline_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train/evaluate an accelerometer-only 4-class behavior baseline.")
    parser.add_argument(
        "--accel-path",
        default="data/raw/external/pig_multimodal_behavior/zenodo_dataset_v1/accelerometer/accelerometer_windows_long_4classes.csv",
    )
    parser.add_argument("--out-dir", default="artifacts/external/pig_multimodal_behavior")
    parser.add_argument("--test-ids", nargs="+", default=DEFAULT_TEST_IDS)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = build_window_features(Path(args.accel_path))
    train, test = group_split(features, args.test_ids)
    _, _, report_dict, cm, macro_f1 = train_and_evaluate(train, test, seed=args.seed)
    report = write_report(Path(args.out_dir), train, test, report_dict, cm, macro_f1, args.test_ids)
    print(f"Wrote {report}")
    print(f"macro F1: {macro_f1:.3f}")


if __name__ == "__main__":
    main()
