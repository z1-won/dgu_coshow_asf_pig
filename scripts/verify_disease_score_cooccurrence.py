"""Verify that co-occurring symptoms actually push disease_score into the 'high' tier.

Every rectal_temp_high hit seen in the real AI Hub data so far has fired alone
(see docs/ASF_DISEASE_SCORE.md section 4), so the co-occurrence bonus added in
domain_rules.evaluate_rules() has never actually been exercised end to end.
This builds three synthetic window-level rows -- normal, fever-only, and
fever+feed_drop+water_spike together -- through the real evaluate_rules() /
disease_tier_for() code path and prints the resulting tiers, so the claim
"co-occurring symptoms score higher" is checked against the actual
implementation rather than just eyeballing the formula.

Run: python scripts/verify_disease_score_cooccurrence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pigproject.domain_rules import MODEL_COMPONENT_WEIGHT, disease_tier_for, evaluate_rules, load_rules  # noqa: E402

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "domain_rules.json"


def make_window_row(dataset_key: str, chamber_number: str, **overrides: float) -> dict:
    base = {
        "dataset_key": dataset_key,
        "chamber_number": chamber_number,
        "start_datetime": pd.Timestamp("2026-01-01 00:00:00"),
        "end_datetime": pd.Timestamp("2026-01-01 04:00:00"),
        "rectal_temperature_mean__wmax": 38.5,
        "neck_temperature_mean__wmax": 34.0,
        "T_mean__wmax": 27.0,
        "feedstuff_volume_mean_zscore_3d__wmean": 0.0,
        "watersupply_mean_zscore_3d__wmean": 0.0,
    }
    base.update(overrides)
    return base


def main() -> None:
    config = load_rules(RULES_PATH)
    rules = config["rules"]

    scenarios = {
        "control (정상)": make_window_row("synthetic", "control"),
        "fever_only (고열 단독)": make_window_row(
            "synthetic", "fever_only", rectal_temperature_mean__wmax=41.0
        ),
        "combined (고열+섭취급감+음수급증 동시)": make_window_row(
            "synthetic",
            "combined",
            rectal_temperature_mean__wmax=41.0,
            feedstuff_volume_mean_zscore_3d__wmean=-2.0,
            watersupply_mean_zscore_3d__wmean=2.0,
        ),
    }

    window_table = pd.DataFrame(scenarios.values())
    rule_table = evaluate_rules(window_table, rules)

    # Same reconstruction_error/threshold ratio for every scenario, so the
    # comparison isolates the rule co-occurrence effect rather than mixing in
    # a difference in model behavior (that side was already checked via the
    # HotPig TN/HS sanity check, docs/HOTPIG_SANITY_CHECK_REPORT.md).
    assumed_ratio = 0.9
    rule_table["model_component"] = MODEL_COMPONENT_WEIGHT * assumed_ratio
    rule_table["disease_score"] = rule_table["model_component"] + rule_table["rule_score"]
    rule_table["disease_tier"] = rule_table["disease_score"].apply(disease_tier_for)

    print(f"(model_component held constant at {MODEL_COMPONENT_WEIGHT * assumed_ratio:.3f} across all scenarios)\n")
    for name, row in zip(scenarios.keys(), rule_table.itertuples()):
        print(f"--- {name} ---")
        print(f"  triggered rules   : {row.rule_reasons or '(none)'}")
        print(f"  rule_triggered_count: {row.rule_triggered_count}")
        print(f"  rule_severity_sum : {row.rule_severity_sum:.2f}")
        print(f"  co_occurrence_bonus: {row.rule_co_occurrence_bonus:.2f}")
        print(f"  disease_score     : {row.disease_score:.2f}")
        print(f"  disease_tier      : {row.disease_tier}")
        print()


if __name__ == "__main__":
    main()
