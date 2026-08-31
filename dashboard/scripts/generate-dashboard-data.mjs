import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const dashboardRoot = path.resolve(path.dirname(__filename), "..");
const projectRoot = path.resolve(dashboardRoot, "..");

const chamberSummaryPath = path.join(projectRoot, "artifacts", "final_chamber_summary.csv");
const incidentQueuePath = path.join(projectRoot, "artifacts", "action_queues", "incident_queue.csv");
const outputPath = path.join(dashboardRoot, "src", "data.generated.js");

const CHAMBER_SOURCE_CSV = "artifacts/final_chamber_summary.csv";
const INCIDENT_SOURCE_CSV = "artifacts/action_queues/incident_queue.csv";
const CLEARFARM_SCORECARD_CSV = "artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_score_threshold_sweep.csv";
const CLEARFARM_RECALL_CANDIDATE_SUMMARY_CSV = "artifacts/clearfarm_rule_scorecard/recall_candidate_config/clearfarm_recall_candidate_summary.csv";
const CLEARFARM_RECALL_CANDIDATE_REASONS_CSV = "artifacts/clearfarm_rule_scorecard/recall_candidate_config/clearfarm_recall_candidate_added_reason_summary.csv";
const CLEARFARM_JAN_MAY_CANDIDATE_COMPARE_CSV = "artifacts/clearfarm_rule_scorecard/jan_may_candidate_config/clearfarm_jan_may_candidate_vs_configs.csv";
const CLEARFARM_JAN_MAY_CANDIDATE_REASONS_CSV = "artifacts/clearfarm_rule_scorecard/jan_may_candidate_config/clearfarm_jan_may_candidate_added_reason_summary.csv";
const CLEARFARM_PRECISION_TUNING_CSV = "artifacts/clearfarm_precision_tuning/full_recall_candidate/clearfarm_precision_policy_metrics.csv";
const CLEARFARM_PRECISION_POLICY_SUMMARY_CSV = "artifacts/clearfarm_alert_policy/precision_tuned_recall_candidate/clearfarm_3level_alert_policy_summary.csv";
const CATEGORY_LEAD_TIME_CSV = "artifacts/category_lead_time_metrics.csv";
const EXTERNAL_VALIDATION_CSV = "artifacts/external_validation_summary/external_validation_summary.csv";
const MANAGEMENT_CANDIDATE_COMPARE_CSV = "artifacts/management_rule_candidates/candidate_management_compare_summary.csv";
const CLEARFARM_ENVIRONMENT_POLICY_CSV = "artifacts/clearfarm_environment_policy_experiment/clearfarm_environment_policy_comparison.csv";

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
      continue;
    }

    field += char;
  }

  if (field.length || row.length) {
    row.push(field);
    if (row.some((value) => value !== "")) rows.push(row);
  }

  if (rows.length === 0) return [];
  const headers = rows[0];
  return rows.slice(1).map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])));
}

function readCsv(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing required CSV: ${filePath}`);
  }
  return parseCsv(fs.readFileSync(filePath, "utf8"));
}

function readOptionalCsv(relativePath) {
  const filePath = path.join(projectRoot, relativePath);
  if (!fs.existsSync(filePath)) return [];
  return parseCsv(fs.readFileSync(filePath, "utf8"));
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function round(value, digits = 4) {
  const factor = 10 ** digits;
  return Math.round(asNumber(value) * factor) / factor;
}

function buildingLabel(row) {
  if (row.track === "bioenergy") {
    const order = { "71408": "1동", "71763": "2동" };
    return order[row.source_dataset] ?? `${row.source_dataset}동`;
  }
  if (row.track === "activity_622") return "3동";
  return row.source_dataset ? `${row.source_dataset}` : "기타";
}

function chamberRoom(chamberId) {
  const bioenergyMatch = chamberId.match(/^bioenergy:([^:]+):(\d+)$/);
  if (bioenergyMatch) return `${bioenergyMatch[2]}번 돈방`;

  const activityMatch = chamberId.match(/^activity622:facility(\d+):pen(\d+)$/);
  if (activityMatch) return `${activityMatch[1]}구역 ${activityMatch[2]}번방`;

  return chamberId;
}

function trackLabel(track) {
  return {
    bioenergy: "체온·환경 센서",
    activity_622: "카메라 행동분석",
  }[track] ?? track;
}

function reasonParts(reason) {
  const pairs = [
    ["rectal_temp_high", "체온 상승"],
    ["co2_high", "이산화탄소 농도 상승"],
    ["nh3_high", "암모니아 농도 상승"],
    ["feed_drop", "사료섭취 감소"],
    ["feed_spike", "사료섭취 급증"],
    ["water_drop", "급수량 감소"],
    ["water_spike", "급수량 급증"],
    ["treatment", "치료 이력 확인"],
    ["environment_failure", "환경 설비 이상"],
    ["ventilation", "환기 이상"],
  ];
  const found = pairs.filter(([token]) => reason.includes(token)).map(([, label]) => label);
  if (found.length) return [...new Set(found)];
  return reason.replace(/^rule:\s*/, "").split(/[|,]/).map((part) => part.trim()).filter(Boolean);
}

function incidentScore(row) {
  const byQueue = {
    disease: asNumber(row.max_track_score),
    management: asNumber(row.max_management_score),
    environment: asNumber(row.max_environment_score),
  };
  return round(byQueue[row.queue] ?? Math.max(asNumber(row.max_track_score), asNumber(row.max_management_score), asNumber(row.max_environment_score)), 4);
}

function scoreFieldForQueue(queue) {
  return {
    disease: "max_track_score",
    management: "max_management_score",
    environment: "max_environment_score",
  }[queue] || "max(track, management, environment)";
}

function categoryEvidenceLabel(queue) {
  return {
    disease: "질병 큐: 체온·행동 이상 점수 우선",
    management: "사양관리 큐: 급이·급수 점수 우선",
    environment: "환경 큐: CO2/NH3/환기 점수 우선",
  }[queue] || "복합 큐: 가장 높은 이상 점수 사용";
}

function eventTypeLabel(eventType) {
  return {
    environment_failure: "환경 설비 이상",
    feed_drop: "급이 감소",
    fever: "발열",
    respiratory: "호흡기 이상",
    treatment: "치료 이력",
    water_drop: "급수 감소",
  }[eventType] || eventType;
}

function environmentTempStage(row) {
  return {
    policy: row.environment_temp_policy || "",
    label: row.environment_temp_label || "",
    action: row.environment_temp_action || "",
  };
}

function operationalStageFromIncident(row) {
  const trackScore = asNumber(row.max_track_score);
  const environmentScore = asNumber(row.max_environment_score);
  const managementScore = asNumber(row.max_management_score);
  if (trackScore >= 0.9 || environmentScore >= 0.9) {
    return {
      key: "cctv_focus",
      label: "CCTV 확인",
      priorityLabel: "CCTV 확인",
      description: "고확신 이상 또는 환경 점수 상승",
    };
  }
  if (trackScore >= 0.6 || environmentScore >= 0.6 || managementScore >= 0.6) {
    return {
      key: "caution",
      label: "확인 필요",
      priorityLabel: "확인 필요",
      description: "담당자 점검 순번 상향",
    };
  }
  return {
    key: "observe",
    label: "관찰 후보",
    priorityLabel: "관찰",
    description: "다음 관측에서 반복 여부 확인",
  };
}

function operationalStageFromChamber(chamber, incident) {
  if (chamber.isNoData) {
    return { key: "nodata", label: "데이터 부족", description: "수집 기준 미달" };
  }
  if (incident?.operationalStage) return incident.operationalStage;
  if (chamber.modelTier === "medium" || chamber.modelTier === "high") {
    return { key: "observe", label: "관찰 후보", description: "모델 관심 구간" };
  }
  return { key: "normal", label: "정상", description: "확인 필요 이벤트 없음" };
}

function attachBarnComparison(chambers) {
  const byBuilding = new Map();
  chambers.forEach((chamber) => {
    if (!byBuilding.has(chamber.buildingLabel)) byBuilding.set(chamber.buildingLabel, []);
    byBuilding.get(chamber.buildingLabel).push(chamber);
  });

  byBuilding.forEach((items) => {
    const comparable = items.filter((item) => Number.isFinite(Number(item.max)));
    const meanMax = comparable.length
      ? comparable.reduce((sum, item) => sum + Number(item.max), 0) / comparable.length
      : 0;
    const ranked = [...comparable].sort((a, b) => Number(b.max) - Number(a.max));
    comparable.forEach((item) => {
      const rank = ranked.findIndex((candidate) => candidate.id === item.id) + 1;
      item.barnComparison = {
        scope: item.buildingLabel,
        comparedPens: comparable.length,
        meanMaxScore: round(meanMax),
        deltaFromBarnMean: round(Number(item.max) - meanMax),
        maxScoreRank: rank,
      };
    });
  });
}

function dateOnly(value) {
  return (value || "").split(" ")[0] || value;
}

function pct(value) {
  const n = asNumber(value, NaN);
  return Number.isFinite(n) ? round(n * 100, 1) : null;
}

function performanceSummary() {
  const scorecardRows = readOptionalCsv(CLEARFARM_SCORECARD_CSV);
  const leadRows = readOptionalCsv(CATEGORY_LEAD_TIME_CSV);
  const externalRows = readOptionalCsv(EXTERNAL_VALIDATION_CSV);
  const managementCompareRows = readOptionalCsv(MANAGEMENT_CANDIDATE_COMPARE_CSV);
  const recallCandidateRows = readOptionalCsv(CLEARFARM_RECALL_CANDIDATE_SUMMARY_CSV);
  const recallCandidateReasons = readOptionalCsv(CLEARFARM_RECALL_CANDIDATE_REASONS_CSV);
  const janMayCandidateRows = readOptionalCsv(CLEARFARM_JAN_MAY_CANDIDATE_COMPARE_CSV);
  const janMayCandidateReasons = readOptionalCsv(CLEARFARM_JAN_MAY_CANDIDATE_REASONS_CSV);
  const precisionTuningRows = readOptionalCsv(CLEARFARM_PRECISION_TUNING_CSV);
  const precisionPolicySummaryRows = readOptionalCsv(CLEARFARM_PRECISION_POLICY_SUMMARY_CSV);
  const environmentPolicyRows = readOptionalCsv(CLEARFARM_ENVIRONMENT_POLICY_CSV);

  const clearfarmRows = scorecardRows
    .filter((row) => row.score_col === "rule_score" && row.sign_col === "any_signs" && ["0.3", "0.9"].includes(String(row.threshold)))
    .map((row) => ({
      label: row.threshold === "0.3" ? "조기 선별" : "고확신 알림",
      threshold: `rule_score >= ${row.threshold}`,
      n: asNumber(row.n),
      alerts: asNumber(row.n_alerts),
      sensitivity: pct(row.sensitivity),
      specificity: pct(row.specificity),
      precision: pct(row.precision),
      f1: pct(row.f1),
    }));

  const leadAll = leadRows.find((row) => row.scope === "all" && row.alert_category_filter === "final") || {};
  const leadByEvent = leadRows
    .filter((row) => row.alert_category_filter === "final" && row.scope !== "all")
    .map((row) => ({
      eventType: row.scope,
      events: asNumber(row.events),
      matched: asNumber(row.lead_matched_events),
      recall24h: pct(row.recall_24h),
      recall48h: pct(row.recall_48h),
      recall72h: pct(row.recall_72h),
    }));

  const asf = externalRows.find((row) => row.dataset === "ASF Dryad challenge") || {};
  const hotpig = externalRows.find((row) => row.dataset === "HOTPIG") || {};

  const recallCandidate = recallCandidateRows
    .filter((row) => ["0.3", "0.300"].includes(String(row.threshold)))
    .map((row) => ({
      threshold: `rule_score >= ${asNumber(row.threshold).toFixed(1)}`,
      baselineAlerts: asNumber(row.baseline_alerts),
      candidateAlerts: asNumber(row.candidate_alerts),
      deltaAlerts: asNumber(row.delta_alerts),
      baselineRecall: pct(row.baseline_recall),
      candidateRecall: pct(row.candidate_recall),
      deltaRecall: pct(row.delta_recall),
      baselinePrecision: pct(row.baseline_precision),
      candidatePrecision: pct(row.candidate_precision),
      deltaPrecision: pct(row.delta_precision),
      baselineF1: pct(row.baseline_f1),
      candidateF1: pct(row.candidate_f1),
      deltaF1: pct(row.delta_f1),
    }))[0] || null;

  const recallCandidateReasonRows = recallCandidateReasons.slice(0, 6).map((row) => ({
    reason: reasonParts(row.rule_reasons || "").join(" + ") || row.rule_reasons || "기타",
    addedAlerts: asNumber(row.added_alerts),
    hitRate: pct(row.any_signs_rate),
    respiratoryRate: pct(row.respiratory_signs_rate),
    gutRate: pct(row.gut_signs_rate),
    heatRate: pct(row.heat_signs_rate),
  }));

  const janMayCandidate = janMayCandidateRows
    .filter((row) => row.scope === "jan_to_may" && row.config === "jan_may_candidate" && ["0.3", "0.300"].includes(String(row.threshold)))
    .map((row) => ({
      threshold: `rule_score >= ${asNumber(row.threshold).toFixed(1)}`,
      baselineAlerts: asNumber(row.alerts) - asNumber(row.delta_alerts_vs_baseline),
      candidateAlerts: asNumber(row.alerts),
      deltaAlerts: asNumber(row.delta_alerts_vs_baseline),
      baselineRecall: pct(asNumber(row.recall) - asNumber(row.delta_recall_vs_baseline)),
      candidateRecall: pct(row.recall),
      deltaRecall: pct(row.delta_recall_vs_baseline),
      baselinePrecision: pct(asNumber(row.precision) - asNumber(row.delta_precision_vs_baseline)),
      candidatePrecision: pct(row.precision),
      deltaPrecision: pct(row.delta_precision_vs_baseline),
      baselineF1: pct(asNumber(row.f1) - asNumber(row.delta_f1_vs_baseline)),
      candidateF1: pct(row.f1),
      deltaF1: pct(row.delta_f1_vs_baseline),
    }))[0] || null;

  const janMayCandidateReasonRows = janMayCandidateReasons.slice(0, 6).map((row) => ({
    reason: reasonParts(row.reason_group || "").join(" + ") || row.reason_group || "기타",
    addedAlerts: asNumber(row.added_alerts),
    hitRate: pct(row.match_rate),
    respiratoryRate: pct(row.respiratory_matches / Math.max(1, asNumber(row.added_alerts))),
    gutRate: pct(row.gut_matches / Math.max(1, asNumber(row.added_alerts))),
    heatRate: pct(row.heat_matches / Math.max(1, asNumber(row.added_alerts))),
  }));

  const precisionBaseline = precisionTuningRows.find((row) => row.scope === "all" && row.policy === "baseline_only") || {};
  const precisionTuned = precisionTuningRows.find((row) => row.scope === "all" && row.policy === "added_recent_same_reason_14d") || {};
  const precisionObserve = precisionPolicySummaryRows.find((row) => row.policy_level === "observe") || {};
  const precisionCandidate = precisionTuned.policy ? {
    threshold: "새 후보 중 같은 원인 14일 내 반복",
    baselineAlerts: asNumber(precisionBaseline.n_alerts),
    candidateAlerts: asNumber(precisionTuned.n_alerts),
    deltaAlerts: asNumber(precisionTuned.n_alerts) - asNumber(precisionBaseline.n_alerts),
    baselineRecall: pct(precisionBaseline.sensitivity),
    candidateRecall: pct(precisionTuned.sensitivity),
    deltaRecall: pct(asNumber(precisionTuned.sensitivity) - asNumber(precisionBaseline.sensitivity)),
    baselinePrecision: pct(precisionBaseline.precision),
    candidatePrecision: pct(precisionTuned.precision),
    deltaPrecision: pct(asNumber(precisionTuned.precision) - asNumber(precisionBaseline.precision)),
    baselineF1: pct(precisionBaseline.f1),
    candidateF1: pct(precisionTuned.f1),
    deltaF1: pct(asNumber(precisionTuned.f1) - asNumber(precisionBaseline.f1)),
    suppressed: asNumber(precisionObserve.precision_suppressed),
  } : null;

  const clearfarmRecallCandidates = [
    recallCandidate ? {
      id: "full_recall_candidate",
      title: "전체 데이터 후보",
      status: "관찰 민감도 후보",
      configFile: "config/domain_rules_clearfarm_recall_candidate.json",
      scope: "전체 기간",
      changes: ["NH3 기준 29 -> 20", "CO2 기준 2984 -> 2500", "습도 75 이상 후보 추가"],
      ...recallCandidate,
      reasonRows: recallCandidateReasonRows,
      interpretation: "전체 데이터에서는 민감도 개선 폭이 크지만 알림 수가 많이 늘어나므로 관찰 후보로만 둔다.",
    } : null,
    janMayCandidate ? {
      id: "jan_may_candidate",
      title: "상반기 우선 후보",
      status: "우선 추천",
      configFile: "config/domain_rules_clearfarm_jan_may_candidate.json",
      scope: "1~5월",
      changes: ["NH3 기준 29 -> 20", "습도 75 이상 후보 추가", "CO2 후보 제외"],
      ...janMayCandidate,
      reasonRows: janMayCandidateReasonRows,
      interpretation: "1~5월에서는 CO2를 제외한 NH3+습도 후보가 같은 민감도를 유지하면서 알림 부담을 조금 줄인다.",
    } : null,
    precisionCandidate ? {
      id: "precision_tuned_candidate",
      title: "정밀도 필터 적용",
      status: "다음 적용 후보",
      configFile: "artifacts/clearfarm_precision_tuning/full_recall_candidate/clearfarm_precision_policy_metrics.csv",
      scope: "전체 기간",
      changes: ["기존 알림 유지", "새 후보 중 같은 원인 14일 내 반복 시 승격", `${precisionCandidate.suppressed}건은 관찰 후보 유지`],
      ...precisionCandidate,
      reasonRows: recallCandidateReasonRows,
      interpretation: "전체 recall 후보를 그대로 쓰지 않고 반복 신호만 승격해, 민감도 상승분을 대부분 유지하면서 알림 부담을 낮춘다.",
    } : null,
  ].filter(Boolean);

  const environmentPolicy = environmentPolicyRows.map((row) => ({
    policy: row.policy,
    label: row.policy_label || row.policy,
    threshold: `${asNumber(row.threshold_c).toFixed(1)}°C`,
    alerts: asNumber(row.alerts),
    recall: pct(row.recall),
    precision: pct(row.precision),
    specificity: pct(row.specificity),
    falseAlertsPerDay: round(row.false_alerts_per_observed_day, 2),
    falseAlertsPer100PenDays: round(row.false_alerts_per_100_pen_days, 2),
    decision: row.decision,
  }));

  const highConfidence = clearfarmRows.find((row) => row.threshold === "rule_score >= 0.9") || {};
  const earlyScreening = clearfarmRows.find((row) => row.threshold === "rule_score >= 0.3") || {};
  const baselineMgmt = managementCompareRows.find((row) => row.experiment === "baseline_config") || {};
  const candidateMgmt = managementCompareRows.find((row) => row.experiment === "candidate_config") || {};

  return {
    sourceFiles: [CLEARFARM_SCORECARD_CSV, CLEARFARM_RECALL_CANDIDATE_SUMMARY_CSV, CLEARFARM_JAN_MAY_CANDIDATE_COMPARE_CSV, CLEARFARM_PRECISION_TUNING_CSV, CLEARFARM_PRECISION_POLICY_SUMMARY_CSV, CLEARFARM_ENVIRONMENT_POLICY_CSV, CATEGORY_LEAD_TIME_CSV, EXTERNAL_VALIDATION_CSV],
    headline: [
      {
        label: "ClearFarm 조기 선별",
        value: clearfarmRows[0]?.sensitivity,
        unit: "민감도",
        detail: `${clearfarmRows[0]?.threshold || "rule_score >= 0.3"} · 정밀도 ${clearfarmRows[0]?.precision ?? "-"}% · F1 ${clearfarmRows[0]?.f1 ?? "-"}%`,
        caution: "알림 수가 많아 1차 선별용",
      },
      {
        label: "ClearFarm 고확신 알림",
        value: clearfarmRows[1]?.precision,
        unit: "정밀도",
        detail: `${clearfarmRows[1]?.threshold || "rule_score >= 0.9"} · 특이도 ${clearfarmRows[1]?.specificity ?? "-"}% · 민감도 ${clearfarmRows[1]?.sensitivity ?? "-"}%`,
        caution: "놓치는 사건이 많아 단독 운영 불가",
      },
      {
        label: "사전 경보 포착",
        value: pct(leadAll.recall_24h),
        unit: "24시간 recall",
        detail: `${asNumber(leadAll.events)}개 이벤트 중 ${asNumber(leadAll.lead_matched_events)}개 사전 포착 · 48/72시간도 ${pct(leadAll.recall_48h) ?? "-"}%/${pct(leadAll.recall_72h) ?? "-"}%`,
        caution: "현재는 synthetic event 기준",
      },
      {
        label: "ASF 체온 rule",
        value: 95.0,
        unit: "정밀도",
        detail: asf.main_result || "rectal_temp_high 39.5C: sensitivity 48.7%, specificity 99.5%, precision 95.0%",
        caution: "체온 단독 진단으로 쓰지 않음",
      },
    ],
    clearfarmRows,
    environmentPolicy,
    leadTime: {
      events: asNumber(leadAll.events),
      matched: asNumber(leadAll.lead_matched_events),
      meanLeadHours: round(leadAll.mean_first_lead_hours, 1),
      precisionProxy: pct(leadAll.precision_proxy),
      recall24h: pct(leadAll.recall_24h),
      recall48h: pct(leadAll.recall_48h),
      recall72h: pct(leadAll.recall_72h),
      byEvent: leadByEvent,
    },
    clearfarmRecallCandidates,
    clearfarmRecallCandidate: clearfarmRecallCandidates[0] || null,
    managementCandidateCompare: {
      sourceFile: MANAGEMENT_CANDIDATE_COMPARE_CSV,
      baseline: {
        finalAlert: asNumber(baselineMgmt.final_alert),
        diseaseAlert: asNumber(baselineMgmt.disease_alert),
        managementAlert: asNumber(baselineMgmt.management_alert),
        environmentAlert: asNumber(baselineMgmt.environment_alert),
      },
      candidate: {
        finalAlert: asNumber(candidateMgmt.final_alert),
        diseaseAlert: asNumber(candidateMgmt.disease_alert),
        managementAlert: asNumber(candidateMgmt.management_alert),
        environmentAlert: asNumber(candidateMgmt.environment_alert),
      },
      conclusion: `feed_drop min 후보 적용 시 사양관리 alert가 ${asNumber(baselineMgmt.management_alert)}건에서 ${asNumber(candidateMgmt.management_alert)}건으로 증가`,
      next: "급이 급락 신호는 살아났지만 전체 alert도 늘어나므로 실제 farm event log로 precision/recall을 검증한 뒤 production 승격 여부를 결정",
    },
    externalChecks: externalRows.map((row) => ({
      dataset: row.dataset,
      role: row.validation_role,
      result: row.main_result,
      decision: row.project_decision,
    })),
    weaknesses: [
      {
        title: "고확신 알림의 누락 위험",
        value: `${highConfidence.sensitivity ?? "-"}%`,
        label: "민감도",
        detail: `rule_score >= 0.9에서는 정밀도 ${highConfidence.precision ?? "-"}%지만 민감도는 ${highConfidence.sensitivity ?? "-"}%입니다. 알림 수는 줄지만 실제 이상을 많이 놓칠 수 있습니다.`,
        next: "운영 화면에서는 고확신 알림을 최종 판정이 아니라 CCTV 집중 확인 단계로 써야 합니다.",
      },
      {
        title: "사전 경보 포착 부족",
        value: `${pct(leadAll.recall_24h) ?? "-"}%`,
        label: "24시간 recall",
        detail: `${asNumber(leadAll.events)}개 이벤트 중 ${asNumber(leadAll.lead_matched_events)}개만 사전에 포착했습니다. 현재 lead-time 평가는 synthetic event 기준이라 실제 농장 기록으로 재검증이 필요합니다.`,
        next: "실제 farm event log를 쌓아 lead-time recall을 다시 계산해야 합니다.",
      },
      {
        title: "조기 선별의 오탐 부담",
        value: `${earlyScreening.precision ?? "-"}%`,
        label: "정밀도",
        detail: `rule_score >= 0.3은 민감도 ${earlyScreening.sensitivity ?? "-"}%로 넓게 잡지만 정밀도는 ${earlyScreening.precision ?? "-"}%입니다.`,
        next: "확인 필요 큐에서 조치 결과를 누적해 threshold를 농장별로 보정해야 합니다.",
      },
    ],
    improvementPlan: [
      "고확신 알림은 최종 확정이 아니라 CCTV/현장 확인 우선순위로 표시",
      "실제 농장 이벤트 로그가 10건 이상 쌓이면 lead-time recall 재산출",
      "환경 온도 기준은 28.7/30.4/31.6°C 3단계로 나눠 운영 목적별로 표시",
      "상반기 전용 후보를 전체 후보와 나란히 비교해 우선 추천으로 관리",
      "ClearFarm 검증 결과를 반영해 절대 threshold를 농장별 상대 threshold로 전환",
    ],
    notes: [
      hotpig.main_result ? `HOTPIG: ${hotpig.main_result}` : "HOTPIG: heat-stress 외부 sanity check 유지",
      "현재 수치는 운영 전 검증용이며, 실제 농장 이벤트 리뷰가 쌓이면 threshold를 다시 조정해야 함",
    ],
  };
}

const chamberRows = readCsv(chamberSummaryPath);
const incidentRows = readCsv(incidentQueuePath);
const performance = performanceSummary();

const chambers = chamberRows.map((row) => ({
  id: row.chamber_id,
  buildingLabel: buildingLabel(row),
  code: row.chamber_id,
  room: chamberRoom(row.chamber_id),
  track: trackLabel(row.track),
  windows: asNumber(row.windows),
  mean: round(row.mean_score),
  max: round(row.max_score),
  modelTier: row.chamber_tier || "unknown",
  lowConf: String(row.low_confidence).toLowerCase() === "true",
  evidence: {
    sourceCsv: CHAMBER_SOURCE_CSV,
    sourceDataset: row.source_dataset,
    scoreFields: ["mean_score", "max_score", "chamber_tier", "operational_alert_windows"],
    scoreMeaning: "평소 패턴 대비 돈방별 이상 점수 요약",
    statusRule: "incident_queue.csv에 같은 돈방 이벤트가 있으면 확인 필요, 없으면 정상",
  },
}));
attachBarnComparison(chambers);

const noDataRooms = [];
if (!chambers.some((chamber) => chamber.id === "bioenergy:71408:3")) {
  noDataRooms.push({
    id: "bioenergy:71408:3-nodata",
    buildingLabel: "1동",
    code: "bioenergy:71408:3",
    room: "3번 돈방",
    note: "관측 횟수 부족(19회, 최소 24회 필요)으로 분석 대상에서 제외됨",
    isNoData: true,
  });
}

const buildingOrder = ["1동", "2동", "3동"];
const buildings = [...new Set([...buildingOrder.filter((label) => chambers.some((chamber) => chamber.buildingLabel === label) || noDataRooms.some((room) => room.buildingLabel === label)), ...chambers.map((chamber) => chamber.buildingLabel)])];
const farmScope = {
  farmId: "demo-farm",
  farmName: "시연 농장",
  mode: "single_farm",
  description: "운영 제품에서는 로그인한 농장의 돈사/돈방만 표시",
};

const incidents = incidentRows.map((row) => ({
  id: row.incident_id,
  chamberId: row.chamber_id,
  category: row.queue,
  start: dateOnly(row.incident_start_datetime),
  end: dateOnly(row.incident_end_datetime),
  windows: asNumber(row.window_count),
  score: incidentScore(row),
  reasonParts: reasonParts(row.reason || ""),
  action: row.recommended_action || "현장 확인 후 조치 결과를 기록",
  operationalStage: operationalStageFromIncident(row),
  environmentTemp: environmentTempStage(row),
  evidence: {
    sourceCsv: INCIDENT_SOURCE_CSV,
    rawReason: row.reason || "",
    scoreField: scoreFieldForQueue(row.queue),
    scoreFormula: categoryEvidenceLabel(row.queue),
    inputScores: {
      track: round(row.max_track_score),
      management: round(row.max_management_score),
      environment: round(row.max_environment_score),
    },
    decisionRule: "domain rule이 감지한 이벤트를 action queue로 승격",
  },
}));

chambers.forEach((chamber) => {
  const incident = incidents.find((item) => item.chamberId === chamber.id);
  chamber.operationalStage = operationalStageFromChamber(chamber, incident);
  chamber.evidence.statusRule = "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보";
});

noDataRooms.forEach((room) => {
  room.operationalStage = operationalStageFromChamber(room, null);
});

const generated = `// 이 파일은 dashboard/scripts/generate-dashboard-data.mjs가 생성합니다.\n// 입력: artifacts/final_chamber_summary.csv, artifacts/action_queues/incident_queue.csv\n\nexport const CHAMBERS = ${JSON.stringify(chambers, null, 2)};\n\nexport const NO_DATA_ROOMS = ${JSON.stringify(noDataRooms, null, 2)};\n\nexport const BUILDINGS = ${JSON.stringify(buildings, null, 2)};\nexport const FARM_SCOPE = ${JSON.stringify(farmScope, null, 2)};\nexport const TOTAL_ROOMS = CHAMBERS.length + NO_DATA_ROOMS.length;\n\nexport const INCIDENTS = ${JSON.stringify(incidents, null, 2)};\n\nexport const PERFORMANCE_SUMMARY = ${JSON.stringify(performance, null, 2)};

export const CATEGORY_LABEL = { disease: "질병", management: "사양관리", environment: "환경", behavior: "행동" };\nexport const CATEGORY_ICON_NAME = { disease: "thermometer", management: "bowl", environment: "wind", behavior: "user" };\n\nexport const CHAMBER_BY_ID = Object.fromEntries(CHAMBERS.map((c) => [c.id, c]));\n\nexport function durationDays(startStr, endStr) {\n  return Math.max(1, Math.round((new Date(endStr) - new Date(startStr)) / 86400000));\n}\n`;

fs.writeFileSync(outputPath, generated);
console.log(`Generated ${path.relative(projectRoot, outputPath)} from ${chambers.length} chambers and ${incidents.length} incidents.`);
