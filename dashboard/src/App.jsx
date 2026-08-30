import { useMemo, useRef, useState } from "react";
import Header from "./components/Header.jsx";
import IncidentCard from "./components/IncidentCard.jsx";
import KpiGrid from "./components/KpiGrid.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useResolutions } from "./hooks/useResolutions.js";
import { useDashboardData } from "./DashboardDataContext.jsx";
import { postReview } from "./api.js";
import { Icon, IconClose, IconInfoFill } from "./icons.jsx";

function DataNote() {
  const { source } = useDashboardData();
  return (
    <div className="data-note">
      <IconInfoFill className="icon-info" />
      <span>
        {source === "api"
          ? "실시간 API(pig-serve-api)에 연결되어 파이프라인 산출물을 직접 읽고 있습니다. 확인/오탐 처리는 영구 리뷰 로그에 저장됩니다."
          : "백엔드 API에 연결되지 않아 빌드 시점 정적 스냅샷을 보고 있습니다. 확인/오탐 처리는 이 브라우저에만 저장됩니다."}
      </span>
    </div>
  );
}

function IncidentSection({ resolutions, resolve, unresolve }) {
  const { INCIDENTS, CATEGORY_LABEL } = useDashboardData();
  const [filter, setFilter] = useState("all");
  const visible = useMemo(
    () => INCIDENTS.filter((incident) => filter === "all" || incident.category === filter),
    [INCIDENTS, filter]
  );
  const counts = useMemo(() => {
    const base = { all: INCIDENTS.length, disease: 0, management: 0, environment: 0, behavior: 0 };
    INCIDENTS.forEach((incident) => {
      base[incident.category] += 1;
    });
    return base;
  }, [INCIDENTS]);

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
          ["behavior", CATEGORY_LABEL.behavior],
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

// 점수를 숫자로만 보여주면 비전공자는 판단 기준이 없다. 3단계 말로 바꿔서 보여준다.
// 실제 확인이 걸린 방(rule 기반 incident)은 모델 tier와 무관하게 "위험"으로 통일한다.
function scoreTier(modelTier, hasIncident) {
  if (hasIncident) return { key: "danger", label: "위험" };
  if (modelTier === "medium" || modelTier === "high") return { key: "watch", label: "관심" };
  return { key: "good", label: "양호" };
}

function sensorText(chamber) {
  if (chamber.isNoData) return "수집 미충족";
  return `${chamber.track} · 관측 ${chamber.windows}회`;
}

function UtilityStrip({ chamber }) {
  if (chamber.isNoData) return null;
  return (
    <div className="utility-strip">
      <Icon name="bowl" className="utility-dot" />
      <Icon name="droplet" className="utility-dot" />
      <Icon name="wind" className="utility-dot" />
      {chamber.track.includes("카메라") ? <Icon name="user" className="utility-dot" /> : null}
    </div>
  );
}

// camLabel: 이 돈방이 어느 CCTV 커버리지에 속하는지(복도 좌/우 어느 쪽인지)를 셀 위에 바로 표시한다.
// 팀원 YOLO/CV 모델과 연결할 때 "이 카메라가 이 돈방을 본다"는 매핑이 배치도에서 바로 보여야 하기 때문.
function PenCell({ chamber, onOpen, camLabel }) {
  const { INCIDENTS } = useDashboardData();
  if (chamber.isBlank) {
    return <div className="pen-cell tier-blank"><span className="blank-label">예비 구획</span></div>;
  }
  const incident = !chamber.isNoData ? INCIDENTS.find((item) => item.chamberId === chamber.id) : null;
  const severity = chamber.isNoData ? "sev-nodata" : incident ? "sev-critical" : "sev-normal";
  const content = (
    <>
      <div className="pen-main">
        <div className="pen-id">
          <span className="room-name">{chamber.room}</span>
          <span className="state-text">{statusLabel(chamber, incident)}</span>
        </div>
        {chamber.isNoData ? (
          <div className="nodata-note">{chamber.note}</div>
        ) : (
          <div className="sensor-line">{sensorText(chamber)}</div>
        )}
      </div>
      <div className="pen-reading-col">
        {!chamber.isNoData ? (() => {
          const tier = scoreTier(chamber.modelTier, Boolean(incident));
          return (
            <div className="pen-reading">
              <span className={`tier-badge tier-${tier.key}`}>{tier.label}</span>
              <span className="pen-reading-raw">{chamber.max.toFixed(2)}</span>
            </div>
          );
        })() : null}
        <div className="pen-badges">
          <UtilityStrip chamber={chamber} />
          {camLabel && !chamber.isNoData ? (
            <span className="cam-tag"><Icon name="camera" className="icon-cam" />{camLabel}</span>
          ) : null}
          {chamber.isNoData ? <span className="nodata-tag">데이터 부족</span> : null}
        </div>
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

function CamStrip({ label, rooms, side }) {
  return (
    <div className={`cam-strip cam-strip-${side}`}>
      <Icon name="camera" className="icon-cam" />
      <span>{label}</span>
      <b>{coverageLabel(rooms)}</b>
    </div>
  );
}

function sensorProfile(chamber, incident) {
  if (chamber.isNoData) {
    return {
      source: "관측 부족",
      devices: ["센서 수집 상태 확인", "최소 관측 횟수 확보"],
      checks: ["누락 기간 확인", "센서 전원/네트워크 확인", "재수집 후 분석 포함"],
    };
  }
  if (chamber.track.includes("카메라")) {
    return {
      source: "카메라 영상 분석",
      devices: ["CCTV", "자세/행동 감지", "돈방 위치 매핑"],
      // 모델이 실제로 구분하는 6개 개별 라벨만 표기. 급이/급수는 "활동 비율"에 다른 라벨과 합산돼
      // 들어갈 뿐 개별 신호가 아니라서 목록에 넣지 않는다(docs/01_data_understanding/BEHAVIOR_TAXONOMY_COMPARISON.md).
      behaviorStates: ["누워 있음", "서 있음", "걷기", "뛰기", "포유 행동", "탐색 행동", "활동 비율(급이·급수 등 포함)"],
      checks: ["카메라 시야 가림 확인", "개체 밀집/조도 상태 확인", "자세 탐지 결과와 대조"],
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
  const { BUILDINGS, CHAMBERS, NO_DATA_ROOMS, INCIDENTS, CATEGORY_LABEL } = useDashboardData();
  const [building, setBuilding] = useState(BUILDINGS[0]);
  const [selected, setSelected] = useState(null);
  const dialogRef = useRef(null);
  const rooms = useMemo(() => [...CHAMBERS, ...NO_DATA_ROOMS].filter((room) => room.buildingLabel === building), [CHAMBERS, NO_DATA_ROOMS, building]);
  const [leftRooms, rightRooms] = useMemo(() => splitRows(rooms), [rooms]);

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
        <div className="site-frame">
          <div className="site-road">
            <span>외부 도로</span>
            <span className="dim-total">전체 길이 120,000 (표준설계 기준)</span>
            <span>방역 라인</span>
          </div>
          <div className="site-body">
            <div className="site-gate">출입구 · CAM-GATE</div>
            <div className="barn-shell">
              <aside className="service-core">
                <div className="service-title">관리·설비 구역</div>
                <FacilityBlock icon="camera" label="출입 확인" sub="CAM-GATE" />
                <FacilityBlock icon="bowl" label="급이 라인" sub="feed sensor" />
                <FacilityBlock icon="droplet" label="급수 라인" sub="water sensor" />
                <FacilityBlock icon="wind" label="환기 설비" sub="CO2/NH3" />
              </aside>
              <div className="housing-bay">
                <CamStrip label="CAM-01" rooms={leftRooms} side="left" />
                <CamStrip label="CAM-02" rooms={rightRooms} side="right" />
                <div className="pen-col pen-col-left">
                  {leftRooms.map((room) => <PenCell key={room.id} chamber={room} onOpen={openDetail} camLabel="CAM-01" />)}
                </div>
                <div className="corridor-vert">
                  <span className="corridor-vert-label">작업복도</span>
                  <span className="corridor-vert-flow"><Icon name="wind" className="icon-cam" /> 환기 흐름</span>
                </div>
                <div className="pen-col pen-col-right">
                  {rightRooms.map((room) => <PenCell key={room.id} chamber={room} onOpen={openDetail} camLabel="CAM-02" />)}
                </div>
              </div>
            </div>
            <div className="dim-side">폭 9,000</div>
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
          const selectedCam = leftRooms.some((room) => room.id === selected.id) ? "CAM-01" : "CAM-02";
          return (
          <div className="dlg-inner">
            <div className="dlg-head">
              <h3>{selected.buildingLabel} {selected.room}</h3>
              <button type="button" className="dlg-close" onClick={() => dialogRef.current?.close()} aria-label="닫기">
                <IconClose className="icon-close" />
              </button>
            </div>
            <div className="dlg-sub">{selected.track}</div>
            <div className="dlg-stats">
              <div className="dlg-stat"><div className="k">평균 점수</div><div className="v">{selected.mean.toFixed(3)}</div></div>
              <div className="dlg-stat"><div className="k">최고 점수</div><div className="v">{selected.max.toFixed(3)}</div></div>
              <div className="dlg-stat"><div className="k">관측 횟수</div><div className="v">{selected.windows}회</div></div>
              <div className="dlg-stat"><div className="k">위험 등급</div><div className="v"><span className={`tier-badge tier-${scoreTier(selected.modelTier, Boolean(selectedIncident)).key}`}>{scoreTier(selected.modelTier, Boolean(selectedIncident)).label}</span></div></div>
            </div>
            <p className="dlg-stats-note">점수는 평소 패턴과 얼마나 다른지를 나타내는 값입니다. 숫자 자체보다 위험 등급과 색상(빨강 = 확인 필요)을 먼저 보세요.</p>
            {!selected.isNoData ? (
              <DetailSection title="CCTV 영상">
                <div className="video-slot">
                  <div className="video-slot-frame">
                    <Icon name="camera" className="icon-video" />
                    <span>{selectedCam} 영상 연동 준비 중</span>
                  </div>
                  <button type="button" className="btn video-btn" disabled>영상 보기</button>
                </div>
              </DetailSection>
            ) : null}
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
            {profile.behaviorStates ? (
              <DetailSection title="인식 가능한 행동">
                <DetailChips items={profile.behaviorStates} />
              </DetailSection>
            ) : null}
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
              <span>{selected.lowConf ? "관측 횟수가 적어 참고용으로만 봐야 합니다." : "경보가 있는 경우 아래 확인 필요 이벤트에서 조치 결과를 남깁니다."}</span>
            </div>
            <div className="dlg-tech">내부 코드: {selected.code}</div>
          </div>
          );
        })() : null}
      </dialog>
    </section>
  );
}

// 브라우저 localStorage는 세션이 끝나면 사라진다. 이 CSV를 pig-build-incident-review-log
// --dashboard-export로 넘기면 Python 쪽 영구 리뷰 로그(data/processed/incident_review_log.csv)에
// 병합돼 세션을 넘어 누적된다.
function exportReviewsCsv(resolutions) {
  const rows = Object.entries(resolutions).map(([incidentId, r]) => `${incidentId},${r.decision},${r.at}`);
  const csv = ["incident_id,decision,resolved_at", ...rows].join("\n") + "\n";
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `incident_review_export_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function HistoryView({ resolutions, unresolve }) {
  const { INCIDENTS } = useDashboardData();
  const resolved = INCIDENTS.filter((incident) => resolutions[incident.id]);
  return (
    <section>
      <div className="section-head">
        <h2>확인 내역</h2>
        <div className="section-head-right">
          <span className="section-note">
            브라우저 localStorage에 저장된 시연용 확인 결과입니다. 영구 저장하려면 내보내서
            <code className="inline-code">--dashboard-export</code>로 병합하세요.
          </span>
          <button
            type="button"
            className="btn"
            disabled={!resolved.length}
            onClick={() => exportReviewsCsv(resolutions)}
          >
            리뷰 내보내기 (CSV)
          </button>
        </div>
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
  const { source: dataSource } = useDashboardData();

  // localStorage is still the source of truth the UI reads from (works even
  // when the backend isn't running), but if the API is reachable we also
  // best-effort persist the decision server-side so it survives past this
  // browser session. A failed POST here doesn't block or roll back the
  // local confirm/dismiss -- the CSV export/import bridge stays as the
  // manual fallback for syncing later.
  function resolveAndSync(id, decision) {
    resolve(id, decision);
    if (dataSource === "api") {
      postReview(id, decision).catch((err) => console.warn(`review sync failed for ${id}:`, err));
    }
  }

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
              <IncidentSection resolutions={resolutions} resolve={resolveAndSync} unresolve={unresolve} />
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
