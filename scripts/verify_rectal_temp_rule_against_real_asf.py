"""Check domain_rules' rectal_temp_high threshold against a real ASF challenge dataset.

Every rectal_temp_high hit seen in the AI Hub bio-energy data has been on
"assumed normal" data with no confirmed disease, so the rule's actual
sensitivity/specificity against real African Swine Fever has never been
measured. This uses Lotonin et al.'s published ASF vaccine-challenge dataset
(Dryad 10.5061/dryad.cnp5hqcm5): 10 pigs challenged with virulent ASFV
(Armenia 2008 genotype II), daily rectal temperature AND a validated clinical
score from day -3 to day 25 post-challenge. clinical_score > 0 is real,
published ground truth for "this animal is symptomatic on this day" -- not
an assumption.

Download the dataset zip manually from
https://datadryad.org/dataset/doi:10.5061/dryad.cnp5hqcm5 (Dryad's file
download API requires an authenticated bearer token, so this can't be
scripted) and extract it to data/raw/asf_dryad/ before running this.

Run: python scripts/verify_rectal_temp_rule_against_real_asf.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "asf_dryad"
RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "domain_rules.json"


def current_rule_threshold() -> float:
    config = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    for rule in config["rules"]:
        if rule["id"] == "rectal_temp_high":
            return rule["threshold"]
    raise KeyError("rectal_temp_high rule not found in config/domain_rules.json")


def load_long(path: Path, value_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    day_col = df.columns[0]
    return df.melt(id_vars=[day_col], var_name="pig", value_name=value_name).dropna()


def main() -> None:
    threshold = current_rule_threshold()
    temp = load_long(DATA_DIR / "Fig._1F_-_Temperature.csv", "rectal_temp")
    score = load_long(DATA_DIR / "Fig._1F_-_Clinical_scores.csv", "clinical_score")
    day_col = temp.columns[0]
    merged = temp.merge(score, on=[day_col, "pig"])
    merged["rule_fires"] = merged["rectal_temp"] >= threshold
    merged["symptomatic"] = merged["clinical_score"] > 0

    tp = int((merged.symptomatic & merged.rule_fires).sum())
    fn = int((merged.symptomatic & ~merged.rule_fires).sum())
    fp = int((~merged.symptomatic & merged.rule_fires).sum())
    tn = int((~merged.symptomatic & ~merged.rule_fires).sum())

    print(f"rectal_temp_high threshold (from config/domain_rules.json): {threshold}")
    print(f"total pig-days: {len(merged)} ({merged.symptomatic.sum()} symptomatic, {(~merged.symptomatic).sum()} asymptomatic)")
    print(f"TP={tp} FN={fn} FP={fp} TN={tn}")
    print(f"sensitivity = {tp / (tp + fn):.3f}")
    print(f"specificity = {tn / (tn + fp):.3f}")
    print(f"precision   = {tp / (tp + fp) if (tp + fp) else float('nan'):.3f}")
    print()

    print("per-pig onset lag (rule-fire day minus first-symptom day):")
    for pig, g in merged.groupby("pig"):
        g = g.sort_values(day_col)
        first_symptom = g.loc[g.clinical_score > 0, day_col].min()
        first_rule = g.loc[g.rectal_temp >= threshold, day_col].min()
        max_score = g.clinical_score.max()
        lag = (first_rule - first_symptom) if pd.notna(first_symptom) and pd.notna(first_rule) else None
        print(f"  {pig}: first_symptom_day={first_symptom}, first_rule_fire_day={first_rule}, lag={lag}, max_score={max_score}")


if __name__ == "__main__":
    main()
