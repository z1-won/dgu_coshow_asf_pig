import { useMemo } from "react";
import { useDashboardData } from "../DashboardDataContext.jsx";

const VIEW_TITLE = { home: "홈", plan: "돈방 배치도", performance: "성능", history: "확인 내역" };

export default function Header({ currentView, resolutions }) {
  const { INCIDENTS, FARM_SCOPE, source } = useDashboardData();
  const openIncidents = useMemo(
    () => INCIDENTS.filter((i) => !resolutions[i.id]),
    [INCIDENTS, resolutions]
  );
  const cctvCount = useMemo(
    () => openIncidents.filter((i) => i.operationalStage?.key === "cctv_focus").length,
    [openIncidents]
  );
  const cautionCount = useMemo(
    () => openIncidents.filter((i) => i.operationalStage?.key === "caution").length,
    [openIncidents]
  );
  const observeCount = useMemo(
    () => openIncidents.filter((i) => i.operationalStage?.key === "observe").length,
    [openIncidents]
  );
  const criticalCount = cctvCount + cautionCount;
  const today = useMemo(
    () =>
      new Date().toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "long",
        day: "numeric",
        weekday: "short",
      }),
    []
  );

  return (
    <div className="main-header">
      <h1>{VIEW_TITLE[currentView]} <span>{FARM_SCOPE?.farmName || "현재 농장"}</span></h1>
      <span className={`status-chip${criticalCount > 0 ? " has-critical" : ""}`}>
        <span className="dot" />
        <span>{criticalCount > 0 ? `확인 필요 ${criticalCount}건` : "정상"}</span>
      </span>
      <div className="header-stats">
        <span className="header-stat crit">
          CCTV <b>{cctvCount}</b>
        </span>
        <span className="header-stat warn">
          관찰 <b>{observeCount + cautionCount}</b>
        </span>
      </div>
      <div className="header-right">
        <span className="header-time">
          {today}
          <span className="sync">{source === "api" ? "갱신: 실시간 API 연결됨" : "갱신: 시연용 고정 데이터"}</span>
        </span>
      </div>
    </div>
  );
}
