import { useDashboardData } from "../DashboardDataContext.jsx";
import { durationDays } from "../utils.js";
import { Icon, IconDangerFill, IconSuccessFill, IconInfoFill, IconUser } from "../icons.jsx";

function CategoryBadge({ category }) {
  const { CATEGORY_LABEL, CATEGORY_ICON_NAME } = useDashboardData();
  return (
    <span className={`cat-badge cat-${category}`}>
      <Icon name={CATEGORY_ICON_NAME[category]} className="icon-cat" />
      {CATEGORY_LABEL[category]}
    </span>
  );
}

export default function IncidentCard({ incident, resolution, onConfirm, onDismiss, onUndo }) {
  const { CHAMBER_BY_ID } = useDashboardData();
  const chamber = CHAMBER_BY_ID[incident.chamberId] || { buildingLabel: "알 수 없음", room: incident.chamberId };
  const days = durationDays(incident.start, incident.end);
  const reasonParts = incident.reasonParts || [];

  return (
    <div className={`incident-card ${resolution ? "resolved" : "sev-critical"}`}>
      <div className="incident-top">
        <div className="incident-id-row">
          {resolution ? (
            <span className="badge sev-resolved">{resolution.decision === "confirmed" ? "확인됨" : "오탐"}</span>
          ) : (
            <span className="badge sev-critical">
              <IconDangerFill className="icon-sev" />
              긴급
            </span>
          )}
          <span className="chamber-name">
            {chamber.buildingLabel} {chamber.room}
          </span>
          <CategoryBadge category={incident.category} />
        </div>
      </div>

      <p className="incident-reason">
        {reasonParts.length ? (
          <>
            {reasonParts.map((part, index) => (
              <span key={part}>
                {index > 0 ? " + " : ""}
                <b>{part}</b>
              </span>
            ))}
            이 발생
          </>
        ) : (
          "상세 사유 없음"
        )}
      </p>

      <div className="incident-action">
        <span className="lbl">권장 조치</span>
        {incident.action}
      </div>

      <div className="incident-fields">
        <div className="incident-field">
          <div className="k">발생</div>
          <div className="v mono">{incident.start}</div>
        </div>
        <div className="incident-field">
          <div className="k">지속시간</div>
          <div className="v">{days}일 지속</div>
        </div>
        <div className="incident-field">
          <div className="k">이상 점수</div>
          <div className="v mono">{incident.score.toFixed(3)}</div>
        </div>
        <div className="incident-field">
          <div className="k">담당자</div>
          <div className="v muted">
            <IconUser className="icon-cat" />
            미배정
          </div>
        </div>
      </div>

      <div className="incident-actions">
        {resolution ? (
          <span className={`resolution-note ${resolution.decision === "confirmed" ? "confirmed" : "dismissed"}`}>
            {resolution.decision === "confirmed" ? (
              <IconSuccessFill className="icon-dot" />
            ) : (
              <IconInfoFill className="icon-dot" />
            )}
            {resolution.decision === "confirmed" ? "실제 문제로 확인됨" : "오탐으로 처리됨"}
            <button type="button" className="undo" onClick={() => onUndo(incident.id)}>
              되돌리기
            </button>
          </span>
        ) : (
          <>
            <button type="button" className="btn confirm" onClick={() => onConfirm(incident.id)}>
              확인 (실제 문제)
            </button>
            <button type="button" className="btn dismiss" onClick={() => onDismiss(incident.id)}>
              오탐 처리
            </button>
          </>
        )}
      </div>
    </div>
  );
}
