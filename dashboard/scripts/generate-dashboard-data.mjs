import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const dashboardRoot = path.resolve(path.dirname(__filename), "..");
const projectRoot = path.resolve(dashboardRoot, "..");

const chamberSummaryPath = path.join(projectRoot, "artifacts", "final_chamber_summary.csv");
const incidentQueuePath = path.join(projectRoot, "artifacts", "action_queues", "incident_queue.csv");
const outputPath = path.join(dashboardRoot, "src", "data.generated.js");

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

function dateOnly(value) {
  return (value || "").split(" ")[0] || value;
}

const chamberRows = readCsv(chamberSummaryPath);
const incidentRows = readCsv(incidentQueuePath);

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
}));

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
}));

const generated = `// 이 파일은 dashboard/scripts/generate-dashboard-data.mjs가 생성합니다.\n// 입력: artifacts/final_chamber_summary.csv, artifacts/action_queues/incident_queue.csv\n\nexport const CHAMBERS = ${JSON.stringify(chambers, null, 2)};\n\nexport const NO_DATA_ROOMS = ${JSON.stringify(noDataRooms, null, 2)};\n\nexport const BUILDINGS = ${JSON.stringify(buildings, null, 2)};\nexport const TOTAL_ROOMS = CHAMBERS.length + NO_DATA_ROOMS.length;\n\nexport const INCIDENTS = ${JSON.stringify(incidents, null, 2)};\n\nexport const CATEGORY_LABEL = { disease: "질병", management: "사양관리", environment: "환경", behavior: "행동" };\nexport const CATEGORY_ICON_NAME = { disease: "thermometer", management: "bowl", environment: "wind", behavior: "user" };\n\nexport const CHAMBER_BY_ID = Object.fromEntries(CHAMBERS.map((c) => [c.id, c]));\n\nexport function durationDays(startStr, endStr) {\n  return Math.max(1, Math.round((new Date(endStr) - new Date(startStr)) / 86400000));\n}\n`;

fs.writeFileSync(outputPath, generated);
console.log(`Generated ${path.relative(projectRoot, outputPath)} from ${chambers.length} chambers and ${incidents.length} incidents.`);
