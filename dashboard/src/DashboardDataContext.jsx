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
    TOTAL_ROOMS: StaticData.TOTAL_ROOMS,
    INCIDENTS: StaticData.INCIDENTS,
    CATEGORY_LABEL: StaticData.CATEGORY_LABEL,
    CATEGORY_ICON_NAME: StaticData.CATEGORY_ICON_NAME,
    CHAMBER_BY_ID: StaticData.CHAMBER_BY_ID,
  };
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
        const chamberById = Object.fromEntries(chambersRes.chambers.map((c) => [c.id, c]));
        setState({
          CHAMBERS: chambersRes.chambers,
          NO_DATA_ROOMS: chambersRes.noDataRooms,
          BUILDINGS: chambersRes.buildings,
          TOTAL_ROOMS: chambersRes.totalRooms,
          INCIDENTS: incidentsRes.incidents,
          CATEGORY_LABEL: categoriesRes.categoryLabel,
          CATEGORY_ICON_NAME: categoriesRes.categoryIconName,
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
