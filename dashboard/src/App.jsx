import { useMemo, useRef, useState } from "react";
import Header from "./components/Header.jsx";
import IncidentCard from "./components/IncidentCard.jsx";
import KpiGrid from "./components/KpiGrid.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useResolutions } from "./hooks/useResolutions.js";
import { BUILDINGS, CHAMBERS, INCIDENTS, NO_DATA_ROOMS, CATEGORY_ICON_NAME, CATEGORY_LABEL } from "./data.js";
import { Icon, IconClose, IconInfoFill } from "./icons.jsx";

function DataNote() {
  return (
    <div className="data-note">
      <IconInfoFill className="icon-info" />
      <span>
        현재 화면은 파이프라인 산출물 기반 시연용 스냅샷입니다. 실제 운영에서는 경보 확인 결과가 review log로 저장되어 rule tuning에 반영됩니다.
      </span>
    </div>
  );
}

function IncidentSection({ resolutions, resolve, unresolve }) {
  const [filter, setFilter] = useState("all");
  const visible = useMemo(
    () => INCIDENTS.filter((incident) => filter === "all" || incident.category === filter),
    [filter]
  );
  const counts = useMemo(() => {
    const base = { all: INCIDENTS.length, disease: 0, management: 0, environment: 0 };
    INCIDENTS.forEach((incident) => {
      base[incident.category] += 1;
    });
    return base;
  }, []);

  return (
    <section>
      <div className="section-head">
        <h2>확인 필요 이벤트</h2>
        <span className="section-note">질병, 사양관리, 환경 원인을 분리해 현장 확인 순서를 정합니다.</span>
      </div>
      <div className="tabs" role="tablist" aria-label="이벤트 카테고리 필터">
        {[
          ["all", "전체"],
          ["disease", CATEGORY_LABEL.disease],
          ["management", CATEGORY_LABEL.management],
          ["environment", CATEGORY_LABEL.environment],
        ].map(([key, label]) => (
          <button key={key} type="button" className="tab" aria-pressed={filter === key} onClick={() => setFilter(key)}>
            {label}<span className="n">{counts[key]}</span>
          </button>
        ))}
      </div>
      <div className="incidents">
        {visible.length ? (
          visible.map((incident) => (
            <IncidentCard
              key={incident.id}
              incident={incident}
              resolution={resolutions[incident.id]}
              onConfirm={(id) => resolve(id, "confirmed")}
              onDismiss={(id) => resolve(id, "dismissed")}
              onUndo={unresolve}
            />
          ))
        ) : (
          <div className="empty-state">해당 카테고리의 이벤트가 없습니다.</div>
        )}
      </div>
    </section>
  );
}

function facilityFlags(incident) {
  const reason = (incident?.reasonParts || []).join(" ");
  return {
    feed: incident?.category === "management" || reason.includes("사료"),
    water: incident?.category === "management" || reason.includes("급수"),
    ventilation: incident?.category === "environment" || reason.includes("이산화탄소") || reason.includes("암모니아") || reason.includes("환경"),
  };
}

function statusLabel(chamber, incident) {
  if (chamber.isNoData) return "데이터 부족";
  if (incident) return "확인 필요";
  return "정상";
}

function sensorText(chamber) {
  if (chamber.isNoData) return "수집 미충족";
  return `${chamber.track} · ${chamber.windows} windows`;
}

function UtilityStrip({ chamber }) {
  if (chamber.isNoData) return null;
  return (
    <div className="utility-strip">
      <Icon name="bowl" className="utility-dot" />
      <Icon name="droplet" className="utility-dot" />
      <Icon name="wind" className="utility-dot" />
    </div>
  );
}

function PenCell({ chamber, onOpen }) {
  if (chamber.isBlank) {
    return <div className="pen-cell tier-blank"><span className="blank-label">예비 구획</span></div>;
  }
  const incident = !chamber.isNoData ? INCIDENTS.find((item) => item.chamberId === chamber.id) : null;
  const severity = chamber.isNoData ? "sev-nodata" : incident ? "sev-critical" : "sev-normal";
  const content = (
    <>
      <div className="pen-primary">
        <span className="room-name">{chamber.room}</span>
        {chamber.isNoData ? <span className="nodata-tag">데이터 부족</span> : null}
      </div>
      <div className="pen-status-group">
        <div className="state-text">{statusLabel(chamber, incident)}</div>
        {chamber.isNoData ? (
          <div className="nodata-note">{chamber.note}</div>
        ) : (
          <>
            <div className="pen-reading">
              <b>{chamber.max.toFixed(2)}</b>
              <span>max</span>
            </div>
            <div className="sensor-line">{sensorText(chamber)}</div>
          </>
        )}
        <UtilityStrip chamber={chamber} />
        {chamber.isNoData ? <span className="verify-tag">미검증</span> : null}
      </div>
    </>
  );

  if (chamber.isNoData) {
    return <div className={`pen-cell ${severity}`} title={chamber.note}>{content}</div>;
  }
  return <button type="button" className={`pen-cell ${severity}`} onClick={() => onOpen(chamber)}>{content}</button>;
}

function roomSortKey(room) {
  const code = room.code || room.id || "";
  const facility = Number(code.match(/facility(\d+)/)?.[1] || 0);
  const pen = Number(code.match(/pen(\d+)/)?.[1] || code.match(/:(\d+)$/)?.[1] || 999);
  return facility * 100 + pen;
}

function splitRows(items) {
  const sorted = [...items].sort((a, b) => roomSortKey(a) - roomSortKey(b));
  const midpoint = Math.ceil(sorted.length / 2);
  const upper = sorted.slice(0, midpoint);
  const lower = sorted.slice(midpoint);
  const max = Math.max(upper.length, lower.length, 1);
  const fill = (row, prefix) => [...row, ...Array.from({ length: max - row.length }, (_, i) => ({ id: `${prefix}-blank-${i}`, isBlank: true }))];
  return [fill(upper, "upper"), fill(lower, "lower")];
}

function coverageLabel(row) {
  const rooms = row.filter((room) => !room.isBlank).map((room) => room.room);
  if (!rooms.length) return "커버 대상 없음";
  if (rooms.length <= 3) return rooms.join(", ");
  return `${rooms[0]}-${rooms[rooms.length - 1]} · ${rooms.length}개 구획`;
}

function CameraCoverage({ upperRooms, lowerRooms }) {
  return (
    <div className="camera-coverage" aria-label="CCTV 커버리지">
      <div className="coverage-line coverage-upper">
        <Icon name="camera" className="icon-cam" />
        <span>CAM-01</span>
        <b>{coverageLabel(upperRooms)}</b>
      </div>
      <div className="coverage-line coverage-lower">
        <Icon name="camera" className="icon-cam" />
        <span>CAM-02</span>
        <b>{coverageLabel(lowerRooms)}</b>
      </div>
    </div>
  );
}

function sensorProfile(chamber, incident) {
  if (chamber.isNoData) {
    return {
      source: "관측 부족",
      devices: ["센서 수집 상태 확인", "최소 관측 window 확보"],
      checks: ["누락 기간 확인", "센서 전원/네트워크 확인", "재수집 후 분석 포함"],
    };
  }
  if (chamber.track.includes("카메라")) {
    return {
      source: "CV/행동 분석",
      devices: ["CCTV", "자세/행동 감지", "돈방 위치 매핑"],
      checks: ["카메라 시야 가림 확인", "개체 밀집/조도 상태 확인", "YOLO 자세 탐지 결과와 대조"],
    };
  }
  const flags = facilityFlags(incident);
  const devices = ["체온 센서", "환경 센서"];
  if (flags.feed) devices.push("급이 라인");
  if (flags.water) devices.push("급수 라인");
  if (flags.ventilation) devices.push("환기/가스 센서");
  return {
    source: "체온·환경 센서",
    devices,
    checks: incident
      ? ["개체 체온 상승 여부 확인", "CO2/NH3 센서값 재확인", "환기·분뇨 설비 상태 확인"]
      : ["최근 센서 수집 상태 확인", "기준선 대비 변화 추적", "경보 발생 시 현장 확인 기록"],
  };
}

function DetailSection({ title, children }) {
  return (
    <div className="dlg-section">
      <div className="dlg-section-title">{title}</div>
      {children}
    </div>
  );
}

function DetailChips({ items }) {
  return <div className="dlg-chip-row">{items.map((item) => <span key={item}>{item}</span>)}</div>;
}

function FacilityBlock({ icon, label, sub }) {
  return (
    <div className="facility-block">
      <Icon name={icon} className="icon-facility" />
      <div>
        <span>{label}</span>
        <small>{sub}</small>
      </div>
    </div>
  );
}

function PlanView() {
  const [building, setBuilding] = useState(BUILDINGS[0]);
  const [selected, setSelected] = useState(null);
  const dialogRef = useRef(null);
  const rooms = useMemo(() => [...CHAMBERS, ...NO_DATA_ROOMS].filter((room) => room.buildingLabel === building), [building]);
  const [upperRooms, lowerRooms] = useMemo(() => splitRows(rooms), [rooms]);

  function openDetail(chamber) {
    setSelected(chamber);
    requestAnimationFrame(() => dialogRef.current?.showModal());
  }

  return (
    <section>
      <div className="section-head">
        <h2>돈방 배치도</h2>
        <span className="section-note">표준 돈사 배치 개념을 따라 돈방열, 작업복도, 설비 위치를 함께 봅니다.</span>
      </div>
      <div className="plan-toolbar">
        <div className="building-tabs">
          {BUILDINGS.map((item) => (
            <button key={item} type="button" className="tab" aria-pressed={building === item} onClick={() => setBuilding(item)}>{item}</button>
          ))}
        </div>
        <div className="standard-specs" aria-label="표준설계도 참고 규격">
          <span>축사 2024 돈사1 참고</span>
          <b>연면적 1,080㎡</b>
          <b>처마 3.30-4.80m</b>
        </div>
      </div>
      <div className="barn-plan">
        <div className="dimension-line">
          <span>표준 평면 방향 · 돈방열 + 작업복도 + 돈방열</span>
          <b>출입·방역 동선</b>
        </div>
        <div className="external-road">
          <span>외부 도로</span>
          <span>출입구</span>
          <span>방역 라인</span>
        </div>
        <div className="barn-shell">
          <aside className="service-core">
            <div className="service-title">관리·설비 구역</div>
            <FacilityBlock icon="camera" label="출입 확인" sub="CAM-GATE" />
            <FacilityBlock icon="bowl" label="급이 라인" sub="feed sensor" />
            <FacilityBlock icon="droplet" label="급수 라인" sub="water sensor" />
            <FacilityBlock icon="wind" label="환기 설비" sub="CO2/NH3" />
          </aside>
          <div className="housing-bay">
            <CameraCoverage upperRooms={upperRooms} lowerRooms={lowerRooms} />
            <div className="pen-row upper-row">
              {upperRooms.map((room) => <PenCell key={room.id} chamber={room} onOpen={openDetail} />)}
            </div>
            <div className="corridor work-corridor">
              <Icon name="camera" className="icon-cam" />
              <span className="corridor-label">작업복도 · CCTV 시야 기준선</span>
              <span className="corridor-cam"><Icon name="camera" className="icon-cam" /> 상단열</span>
              <span className="corridor-cam"><Icon name="camera" className="icon-cam" /> 하단열</span>
              <span className="airflow-mark"><Icon name="wind" className="icon-cam" /> 환기 흐름</span>
            </div>
            <div className="pen-row lower-row">
              {lowerRooms.map((room) => <PenCell key={room.id} chamber={room} onOpen={openDetail} />)}
            </div>
          </div>
        </div>
        <div className="legend">
          <span><span className="sw critical" /> 확인 필요</span>
          <span><span className="sw normal" /> 정상</span>
          <span><span className="sw nodata" /> 데이터 부족</span>
          <span><Icon name="bowl" className="icon-cam" /> 급이</span>
          <span><Icon name="droplet" className="icon-cam" /> 급수</span>
          <span><Icon name="wind" className="icon-cam" /> 환기/환경</span>
          <span><Icon name="camera" className="icon-cam" /> CCTV</span>
        </div>
      </div>
      <dialog ref={dialogRef} onClose={() => setSelected(null)}>
        {selected ? (() => {
          const selectedIncident = INCIDENTS.find((item) => item.chamberId === selected.id);
          const profile = sensorProfile(selected, selectedIncident);
          const flags = facilityFlags(selectedIncident);
          const connectedFacilities = [
            flags.feed ? "급이 라인" : null,
            flags.water ? "급수 라인" : null,
            flags.ventilation ? "환기/가스 센서" : null,
          ].filter(Boolean);
          return (
          <div className="dlg-inner">
            <div className="dlg-head">
              <h3>{selected.buildingLabel} {selected.room}</h3>
              <button type="button" className="dlg-close" onClick={() => dialogRef.current?.close()} aria-label="닫기">
                <IconClose className="icon-close" />
              </button>
            </div>
            <div className="dlg-sub">{selected.code} · {selected.track}</div>
            <div className="dlg-stats">
              <div className="dlg-stat"><div className="k">평균 점수</div><div className="v">{selected.mean.toFixed(3)}</div></div>
              <div className="dlg-stat"><div className="k">최대 점수</div><div className="v">{selected.max.toFixed(3)}</div></div>
              <div className="dlg-stat"><div className="k">관측 window</div><div className="v">{selected.windows}</div></div>
              <div className="dlg-stat"><div className="k">모델 tier</div><div className="v">{selected.modelTier}</div></div>
            </div>
            <DetailSection title="표준 규격 참고">
              <DetailChips items={["축사 2024 돈사1", "연면적 1,080㎡", "지상 1층", "처마 3.30-4.80m"]} />
            </DetailSection>
            <DetailSection title="데이터·설비 연결">
              <div className="dlg-evidence-grid">
                <div><span>데이터 소스</span><b>{profile.source}</b></div>
                <div><span>연결 설비</span><b>{connectedFacilities.length ? connectedFacilities.join(" · ") : "기본 센서 모니터링"}</b></div>
              </div>
              <DetailChips items={profile.devices} />
            </DetailSection>
            <DetailSection title="현장 확인 포인트">
              <ul className="dlg-checklist">
                {profile.checks.map((check) => <li key={check}>{check}</li>)}
              </ul>
            </DetailSection>
            {selectedIncident ? (
              <DetailSection title="현재 이벤트 근거">
                <DetailChips items={selectedIncident.reasonParts?.length ? selectedIncident.reasonParts : [CATEGORY_LABEL[selectedIncident.category]]} />
              </DetailSection>
            ) : null}
            <div className="dlg-msg">
              <IconInfoFill className="icon-info" />
              <span>{selected.lowConf ? "학습 window가 적어 참고용으로만 봐야 합니다." : "경보가 있는 경우 아래 확인 필요 이벤트에서 조치 결과를 남깁니다."}</span>
            </div>
            <div className="dlg-tech">원본 code: {selected.code}</div>
          </div>
          );
        })() : null}
      </dialog>
    </section>
  );
}

function HistoryView({ resolutions, unresolve }) {
  const resolved = INCIDENTS.filter((incident) => resolutions[incident.id]);
  return (
    <section>
      <div className="section-head">
        <h2>확인 내역</h2>
        <span className="section-note">브라우저 localStorage에 저장된 시연용 확인 결과입니다.</span>
      </div>
      <div className="incidents">
        {resolved.length ? (
          resolved.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} resolution={resolutions[incident.id]} onUndo={unresolve} />
          ))
        ) : (
          <div className="empty-state">아직 확인 처리한 이벤트가 없습니다.</div>
        )}
      </div>
    </section>
  );
}

export default function App() {
  const [currentView, setCurrentView] = useState("home");
  const { resolutions, resolve, unresolve } = useResolutions();

  return (
    <>
      <Sidebar currentView={currentView} onNavigate={setCurrentView} />
      <main className="main">
        <Header currentView={currentView} resolutions={resolutions} />
        <div className="view">
          <DataNote />
          {currentView === "home" ? (
            <>
              <section>
                <div className="section-head">
                  <h2>전체 현황</h2>
                  <span className="section-note">돈방 단위 이상 선별과 현장 확인 큐를 요약합니다.</span>
                </div>
                <KpiGrid resolutions={resolutions} />
              </section>
              <IncidentSection resolutions={resolutions} resolve={resolve} unresolve={unresolve} />
            </>
          ) : null}
          {currentView === "plan" ? <PlanView /> : null}
          {currentView === "history" ? <HistoryView resolutions={resolutions} unresolve={unresolve} /> : null}
        </div>
        <footer>시연용 데이터 · 최종 운영 연결 시 incident review log와 rule tuning 결과를 함께 저장합니다.</footer>
      </main>
    </>
  );
}
