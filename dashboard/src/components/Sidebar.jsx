import { IconBrand, IconHome, IconLayout, IconHistory, IconChecklist } from "../icons.jsx";

const NAV_ITEMS = [
  { view: "home", label: "홈", Icon: IconHome },
  { view: "plan", label: "돈방 배치도", Icon: IconLayout },
  { view: "performance", label: "성능", Icon: IconChecklist },
  { view: "history", label: "확인 내역", Icon: IconHistory },
];

export default function Sidebar({ currentView, onNavigate }) {
  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <IconBrand className="icon-brand" />
        <div>
          <span className="name">돈방 관제</span>
          <span className="env">시연용 데이터</span>
        </div>
      </div>
      <div className="sidebar-nav">
        {NAV_ITEMS.map(({ view, label, Icon }) => (
          <button
            key={view}
            type="button"
            className="nav-item"
            aria-current={currentView === view}
            onClick={() => onNavigate(view)}
          >
            <Icon className="icon-nav" />
            <span>{label}</span>
          </button>
        ))}
      </div>
      <div className="sidebar-foot">
        데이터 출처
        <br />
        <span className="mono">final_chamber_anomaly_scores.csv</span>
      </div>
    </nav>
  );
}
