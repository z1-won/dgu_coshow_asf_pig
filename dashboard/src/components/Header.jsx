import { useMemo } from "react";
import { useDashboardData } from "../DashboardDataContext.jsx";

const VIEW_TITLE = { home: "홈", plan: "돈방 배치도", history: "확인 내역" };

export default function Header({ currentView, resolutions }) {
  const { INCIDENTS, source } = useDashboardData();
  const criticalCount = useMemo(
    () => INCIDENTS.filter((i) => !resolutions[i.id]).length,
    [INCIDENTS, resolutions]
  );
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
      <h1>{VIEW_TITLE[currentView]}</h1>
      <span className={`status-chip${criticalCount > 0 ? " has-critical" : ""}`}>
        <span className="dot" />
        <span>{criticalCount > 0 ? `확인 필요 ${criticalCount}건` : "정상"}</span>
      </span>
      <div className="header-stats">
        <span className="header-stat crit">
          긴급 <b>{criticalCount}</b>
        </span>
        <span className="header-stat warn">
          주의 <b>0</b>
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
