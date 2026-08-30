import { useMemo } from "react";
import { INCIDENTS, TOTAL_ROOMS } from "../data.js";

// 레퍼런스(관제시스템 UI 톤앤매너 PDF)의 "큰 숫자를 그룹으로 묶어 보여주는" 배치만 차용.
// 다크 크롬/컬러 배지/차트는 가져오지 않고, 색은 이상(긴급) 상태에만 남겨둔다.
export default function KpiGrid({ resolutions }) {
  const { normalRate, normalCount, affected, criticalCount } = useMemo(() => {
    const open = INCIDENTS.filter((i) => !resolutions[i.id]);
    const affectedCount = new Set(open.map((i) => i.chamberId)).size;
    return {
      normalRate: Math.round(((TOTAL_ROOMS - affectedCount) / TOTAL_ROOMS) * 100),
      normalCount: TOTAL_ROOMS - affectedCount,
      affected: affectedCount,
      criticalCount: open.length,
    };
  }, [resolutions]);

  return (
    <div className="kpi-groups">
      <div className="kpi-group">
        <div className="kpi-group-label">돈방 현황</div>
        <div className="kpi-group-stats">
          <div className="kpi-stat">
            <div className="kpi-stat-val">{normalRate}%</div>
            <div className="kpi-stat-lbl">정상률 · {normalCount}/{TOTAL_ROOMS}개</div>
          </div>
          <div className="kpi-stat">
            <div className={`kpi-stat-val${affected > 0 ? " crit" : ""}`}>{affected}</div>
            <div className="kpi-stat-lbl">확인 필요 돈방</div>
          </div>
        </div>
      </div>
      <div className="kpi-group">
        <div className="kpi-group-label">확인 이벤트</div>
        <div className="kpi-group-stats">
          <div className="kpi-stat">
            <div className={`kpi-stat-val${criticalCount > 0 ? " crit" : ""}`}>{criticalCount}</div>
            <div className="kpi-stat-lbl">긴급 · 즉시 대응 권장</div>
          </div>
          <div className="kpi-stat">
            <div className="kpi-stat-val">0</div>
            <div className="kpi-stat-lbl">주의 · 현재 없음</div>
          </div>
        </div>
      </div>
    </div>
  );
}
