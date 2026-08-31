import { createContext, useContext, useEffect, useState } from "react";
import * as StaticData from "./data.js";
import { fetchCategories, fetchChambers, fetchIncidents } from "./api.js";

// 백엔드(pig-serve-api)가 떠 있으면 실시간 데이터를, 없으면 빌드 시점 정적 스냅샷을 쓴다.
// 발표/데모 중 백엔드를 안 띄웠다고 대시보드 자체가 죽으면 안 되기 때문에 항상 fallback이 있다.
const DashboardDataContext = createContext(null);

function fromStatic() {
  return {
    CHAMBERS: StaticData.CHAMBERS,
    NO_DATA_ROOMS: StaticData.NO_DATA_ROOMS,
    BUILDINGS: StaticData.BUILDINGS,
    FARM_SCOPE: StaticData.FARM_SCOPE,
    TOTAL_ROOMS: StaticData.TOTAL_ROOMS,
    INCIDENTS: StaticData.INCIDENTS,
    CATEGORY_LABEL: StaticData.CATEGORY_LABEL,
    CATEGORY_ICON_NAME: StaticData.CATEGORY_ICON_NAME,
    PERFORMANCE_SUMMARY: StaticData.PERFORMANCE_SUMMARY,
    CHAMBER_BY_ID: StaticData.CHAMBER_BY_ID,
  };
}

function stageFromScores(scores = {}) {
  const track = Number(scores.track) || 0;
  const management = Number(scores.management) || 0;
  const environment = Number(scores.environment) || 0;
  if (track >= 0.9 || environment >= 0.9) {
    return { key: "cctv_focus", label: "CCTV 확인", priorityLabel: "CCTV 확인", description: "고확신 이상 또는 환경 점수 상승" };
  }
  if (track >= 0.6 || management >= 0.6 || environment >= 0.6) {
    return { key: "caution", label: "확인 필요", priorityLabel: "확인 필요", description: "담당자 점검 순번 상향" };
  }
  return { key: "observe", label: "관찰 후보", priorityLabel: "관찰", description: "다음 관측에서 반복 여부 확인" };
}

function stageForChamber(chamber, incident) {
  if (chamber.isNoData) return { key: "nodata", label: "데이터 부족", description: "수집 기준 미달" };
  if (incident?.operationalStage) return incident.operationalStage;
  if (chamber.modelTier === "medium" || chamber.modelTier === "high") {
    return { key: "observe", label: "관찰 후보", description: "모델 관심 구간" };
  }
  return { key: "normal", label: "정상", description: "확인 필요 이벤트 없음" };
}

function attachOperationalStages(chambers, noDataRooms, incidents) {
  const normalizedIncidents = incidents.map((incident) => ({
    ...incident,
    operationalStage: incident.operationalStage || stageFromScores(incident.evidence?.inputScores),
  }));
  const byChamber = Object.fromEntries(normalizedIncidents.map((incident) => [incident.chamberId, incident]));
  const normalizedChambers = chambers.map((chamber) => ({
    ...chamber,
    operationalStage: stageForChamber(chamber, byChamber[chamber.id]),
  }));
  const normalizedNoData = noDataRooms.map((room) => ({
    ...room,
    operationalStage: stageForChamber(room, null),
  }));
  return { chambers: normalizedChambers, noDataRooms: normalizedNoData, incidents: normalizedIncidents };
}

export function DashboardDataProvider({ children }) {
  const [state, setState] = useState(() => ({ ...fromStatic(), source: "static", loading: true, error: null }));

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [chambersRes, incidentsRes, categoriesRes] = await Promise.all([
          fetchChambers(),
          fetchIncidents(),
          fetchCategories(),
        ]);
        if (cancelled) return;
        const normalized = attachOperationalStages(chambersRes.chambers, chambersRes.noDataRooms, incidentsRes.incidents);
        const chamberById = Object.fromEntries(normalized.chambers.map((c) => [c.id, c]));
        setState({
          CHAMBERS: normalized.chambers,
          NO_DATA_ROOMS: normalized.noDataRooms,
          BUILDINGS: chambersRes.buildings,
          FARM_SCOPE: chambersRes.farmScope || StaticData.FARM_SCOPE,
          TOTAL_ROOMS: chambersRes.totalRooms,
          INCIDENTS: normalized.incidents,
          CATEGORY_LABEL: categoriesRes.categoryLabel,
          CATEGORY_ICON_NAME: categoriesRes.categoryIconName,
          PERFORMANCE_SUMMARY: StaticData.PERFORMANCE_SUMMARY,
          CHAMBER_BY_ID: chamberById,
          source: "api",
          loading: false,
          error: null,
        });
      } catch (err) {
        if (cancelled) return;
        setState({ ...fromStatic(), source: "static", loading: false, error: String(err) });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return <DashboardDataContext.Provider value={state}>{children}</DashboardDataContext.Provider>;
}

export function useDashboardData() {
  const ctx = useContext(DashboardDataContext);
  if (!ctx) throw new Error("useDashboardData must be used within a DashboardDataProvider");
  return ctx;
}
