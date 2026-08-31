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
  return chamber.operationalStage?.label || incident?.operationalStage?.label || (chamber.isNoData ? "데이터 부족" : incident ? "확인 필요" : "정상");
}

// 점수를 숫자로만 보여주면 비전공자는 판단 기준이 없다. 3단계 말로 바꿔서 보여준다.
// 실제 확인이 걸린 방(rule 기반 incident)은 모델 tier와 무관하게 "위험"으로 통일한다.
function scoreTier(modelTier, hasIncident) {
  if (hasIncident) return { key: "danger", label: "위험" };
  if (modelTier === "medium" || modelTier === "high") return { key: "watch", label: "관심" };
  return { key: "good", label: "양호" };
}

function sensorText(chamber) {
  if (chamber.isNoData) return "수집 기준 미달";
  if (chamber.track.includes("카메라")) return `CCTV 행동 분석 · 관측 ${chamber.windows}회`;
  return `체온·환경 센서 · 관측 ${chamber.windows}회`;
}

function issueText(incident, chamber) {
  if (chamber.isNoData) return "데이터 부족";
  if (!incident && chamber.operationalStage?.key === "observe") return "변화 관찰";
  const reason = (incident?.reasonParts || []).join(" ");
  const flags = facilityFlags(incident);
  if (flags.feed && flags.water) return "급이·급수 이상";
  if (flags.feed) return "급이 이상";
  if (flags.water) return "급수 이상";
  if (flags.ventilation) return "환기 이상";
  if (reason.includes("체온")) return "체온 이상";
  if (chamber.track.includes("카메라")) return "행동 분석";
  return "기준 범위";
}

function barnComparisonText(chamber) {
  const cmp = chamber.barnComparison;
  if (!cmp || !cmp.comparedPens) return null;
  const delta = Number(cmp.deltaFromBarnMean || 0);
  const sign = delta > 0 ? "+" : "";
  return `${cmp.scope} ${cmp.maxScoreRank}/${cmp.comparedPens} · 평균 대비 ${sign}${delta.toFixed(2)}`;
}


// camLabel: 이 돈방이 어느 CCTV 커버리지에 속하는지(복도 좌/우 어느 쪽인지)를 셀 위에 바로 표시한다.
// 팀원 YOLO/CV 모델과 연결할 때 "이 카메라가 이 돈방을 본다"는 매핑이 배치도에서 바로 보여야 하기 때문.
function PenCell({ chamber, onOpen, camLabel }) {
  const { INCIDENTS } = useDashboardData();
  if (chamber.isBlank) {
    return <div className="pen-cell tier-blank"><span className="blank-label">예비 구획</span></div>;
  }
  const incident = !chamber.isNoData ? INCIDENTS.find((item) => item.chamberId === chamber.id) : null;
  const stage = chamber.operationalStage || incident?.operationalStage || {};
  const severity = chamber.isNoData
    ? "sev-nodata"
    : stage.key === "cctv_focus" || stage.key === "caution"
      ? "sev-critical"
      : stage.key === "observe"
        ? "sev-watch"
        : "sev-normal";
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
            <div className={`pen-reading tier-${tier.key}`}>
              <div className="score-row"><span className="pen-reading-raw">{chamber.max.toFixed(2)}</span><span>이상 점수</span></div>
              <div className="issue-line">{issueText(incident, chamber)}</div>
            </div>
          );
        })() : (
          <div className="pen-reading tier-muted">
            <div className="score-row"><span className="pen-reading-raw">--</span><span>이상 점수</span></div>
            <div className="issue-line">데이터 부족</div>
          </div>
        )}
        {camLabel && !chamber.isNoData ? <div className="cam-tag">{camLabel}</div> : null}
        {barnComparisonText(chamber) ? <div className="barn-compare-note">{barnComparisonText(chamber)}</div> : null}
        {stage.description && !chamber.isNoData ? <div className="stage-note">{stage.description}</div> : null}
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
      ? ["개체 체온 상승 여부 확인", "CO₂/NH₃ 센서값 재확인", "환기·분뇨 설비 상태 확인"]
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

function scoreBreakdownText(evidence) {
  const scores = evidence?.inputScores;
  if (!scores) return "이벤트 점수 없음";
  return `질병/행동 ${Number(scores.track).toFixed(3)} · 급이·급수 ${Number(scores.management).toFixed(3)} · 환경 ${Number(scores.environment).toFixed(3)}`;
}

function hasEnvironmentTempStage(incident) {
  const policy = incident?.environmentTemp?.policy;
  return ["screening", "balanced", "high_confidence"].includes(policy);
}

function environmentTempText(incident) {
  const stage = incident?.environmentTemp;
  if (!stage?.label) return "온도 단계 없음";
  return stage.action ? `${stage.label} · ${stage.action}` : stage.label;
}

function FacilityBlock({ label, sub }) {
  return (
    <div className="facility-block">
      <span>{label}</span>
      <small>{sub}</small>
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
        <span className="section-note">돈방 위치, 상태, 센서 관계를 한 화면에서 확인합니다.</span>
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
            <span className="dim-total">전체 길이 120m 기준</span>
            <span>방역 라인</span>
          </div>
          <div className="site-body">
            <div className="site-gate">출입구 · 카메라</div>
            <div className="barn-shell">
              <aside className="service-core">
                <div className="service-title">관리·설비 구역</div>
                <FacilityBlock label="출입 확인" sub="출입구 카메라" />
                <FacilityBlock label="급이 설비" sub="사료 섭취" />
                <FacilityBlock label="급수 설비" sub="음수량" />
                <FacilityBlock label="환기 설비" sub="CO₂ / NH₃" />
              </aside>
              <div className="housing-bay">
                <CamStrip label="CAM-01" rooms={leftRooms} side="left" />
                <CamStrip label="CAM-02" rooms={rightRooms} side="right" />
                <div className="pen-col pen-col-left">
                  {leftRooms.map((room) => <PenCell key={room.id} chamber={room} onOpen={openDetail} camLabel="CAM-01" />)}
                </div>
                <div className="corridor-vert">
                  <span className="corridor-vert-label">작업복도</span>
                  <span className="corridor-vert-flow">환기 흐름</span>
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
          <span><span className="sw cctv" /> CCTV 확인</span>
          <span><span className="sw critical" /> 확인 필요</span>
          <span><span className="sw watch" /> 관찰 후보</span>
          <span><span className="sw normal" /> 정상</span>
          <span><span className="sw nodata" /> 데이터 부족</span>
          <span>급이 이상</span>
          <span>급수 이상</span>
          <span>환기 이상</span>
          <span>CCTV 커버리지</span>
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
                <div><span>동 내 비교</span><b>{barnComparisonText(selected) || "비교 대상 부족"}</b></div>
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
                {hasEnvironmentTempStage(selectedIncident) ? (
                  <div className="environment-temp-stage">
                    <span>환경 온도 단계</span>
                    <b>{environmentTempText(selectedIncident)}</b>
                  </div>
                ) : null}
              </DetailSection>
            ) : null}
            <DetailSection title="판단 근거">
              <div className="dlg-evidence-grid trace-grid">
                <div><span>돈방 점수 출처</span><b>{selected.evidence?.sourceCsv || "artifacts/final_chamber_summary.csv"}</b></div>
                <div><span>상태 판단</span><b>{selected.evidence?.statusRule || "이벤트 큐 매칭 기준"}</b></div>
                {selectedIncident ? (
                  <>
                    <div><span>이벤트 출처</span><b>{selectedIncident.evidence?.sourceCsv || "artifacts/action_queues/incident_queue.csv"}</b></div>
                    <div><span>사용 점수</span><b>{selectedIncident.evidence?.scoreField || "category score"}</b></div>
                    <div><span>점수 선택 기준</span><b>{selectedIncident.evidence?.scoreFormula || "이벤트 큐별 대표 점수"}</b></div>
                    <div><span>입력 점수</span><b>{scoreBreakdownText(selectedIncident.evidence)}</b></div>
                  </>
                ) : (
                  <div><span>현재 상태</span><b>같은 돈방의 확인 필요 이벤트 없음</b></div>
                )}
              </div>
              {selectedIncident?.evidence?.rawReason ? (
                <div className="trace-reason">원본 rule: {selectedIncident.evidence.rawReason}</div>
              ) : null}
            </DetailSection>
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

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : "-";
}

function PerformanceView() {
  const { PERFORMANCE_SUMMARY } = useDashboardData();
  const summary = PERFORMANCE_SUMMARY || { headline: [], clearfarmRows: [], environmentPolicy: [], leadTime: {}, externalChecks: [], notes: [], sourceFiles: [] };
  const lead = summary.leadTime || {};

  return (
    <section>
      <div className="section-head">
        <h2>성능 요약</h2>
        <span className="section-note">현재 모델·규칙이 실제 검증 데이터에서 어느 정도 작동하는지 확인합니다.</span>
      </div>

      <div className="performance-grid">
        {(summary.headline || []).map((item) => (
          <div className="perf-metric" key={item.label}>
            <div className="perf-label">{item.label}</div>
            <div className="perf-value-row">
              <b>{formatPercent(item.value)}</b>
              <span>{item.unit}</span>
            </div>
            <p>{item.detail}</p>
            <small>{item.caution}</small>
          </div>
        ))}
      </div>

      <div className="performance-columns">
        <section className="perf-panel">
          <div className="perf-panel-head">
            <h3>ClearFarm 규칙 검증</h3>
            <span>비육돈 실제 농장 pen-day 기준</span>
          </div>
          <div className="perf-table" role="table" aria-label="ClearFarm rule score threshold performance">
            <div className="perf-table-row head" role="row">
              <span>운영 기준</span><span>민감도</span><span>특이도</span><span>정밀도</span><span>F1</span>
            </div>
            {(summary.clearfarmRows || []).map((row) => (
              <div className="perf-table-row" role="row" key={row.threshold}>
                <span><b>{row.label}</b><em>{row.threshold}</em></span>
                <span>{formatPercent(row.sensitivity)}</span>
                <span>{formatPercent(row.specificity)}</span>
                <span>{formatPercent(row.precision)}</span>
                <span>{formatPercent(row.f1)}</span>
              </div>
            ))}
          </div>
        </section>

        {(summary.environmentPolicy || []).length ? (
          <section className="perf-panel environment-policy-panel">
            <div className="perf-panel-head">
              <h3>환경 기준 3단계</h3>
              <span>온도 기준별 탐지 성능과 확인 부담</span>
            </div>
            <div className="environment-policy-table" role="table" aria-label="ClearFarm environment temperature policy comparison">
              <div className="environment-policy-row head" role="row">
                <span>단계</span><span>기준</span><span>민감도</span><span>정밀도</span><span>오탐/일</span><span>판단</span>
              </div>
              {summary.environmentPolicy.map((row) => (
                <div className="environment-policy-row" role="row" key={row.policy}>
                  <span><b>{row.label}</b></span>
                  <span>{row.threshold}</span>
                  <span>{formatPercent(row.recall)}</span>
                  <span>{formatPercent(row.precision)}</span>
                  <span>{row.falseAlertsPerDay}</span>
                  <span>{row.decision}</span>
                </div>
              ))}
            </div>
            <p className="environment-policy-note">기본 후보는 균형 단계입니다. 선별은 관찰 범위를 넓히는 용도, 고확신은 CCTV/현장 확인 우선순위로 해석합니다.</p>
          </section>
        ) : null}

        {(summary.clearfarmRecallCandidates || []).length ? (
          <section className="perf-panel recall-candidate-panel">
            <div className="perf-panel-head">
              <h3>ClearFarm 관찰 민감도 후보</h3>
              <span>전체 후보, 상반기 후보, 정밀도 필터 비교</span>
            </div>
            <div className="alert-flow-strip" aria-label="운영 알림 단계">
              <div>
                <span>1차 선별</span>
                <b>관찰 후보</b>
                <em>넓게 잡고 반복 여부 확인</em>
              </div>
              <div>
                <span>정밀 필터</span>
                <b>확인 필요</b>
                <em>같은 원인이 반복될 때 승격</em>
              </div>
              <div>
                <span>현장 확인</span>
                <b>CCTV 확인</b>
                <em>돈방 단위 후보를 행동 확인으로 연결</em>
              </div>
            </div>
            <div className="candidate-compare-grid">
              {summary.clearfarmRecallCandidates.map((candidate) => (
                <article className={`candidate-card ${candidate.id === "jan_may_candidate" ? "recommended" : ""} ${candidate.id === "precision_tuned_candidate" ? "precision-selected" : ""}`} key={candidate.id}>
                  <div className="candidate-card-head">
                    <div>
                      <b>{candidate.title}</b>
                      <span>{candidate.scope}</span>
                    </div>
                    <strong>{candidate.status}</strong>
                  </div>
                  <div className="candidate-summary-line">
                    <div>
                      <span>민감도</span>
                      <b>{formatPercent(candidate.baselineRecall)} → {formatPercent(candidate.candidateRecall)}</b>
                    </div>
                    <div>
                      <span>정밀도</span>
                      <b>{formatPercent(candidate.baselinePrecision)} → {formatPercent(candidate.candidatePrecision)}</b>
                    </div>
                    <div>
                      <span>알림 수</span>
                      <b>{candidate.baselineAlerts} → {candidate.candidateAlerts}</b>
                    </div>
                  </div>
                  <p className="candidate-interpretation">{candidate.interpretation}</p>
                  {Number.isFinite(Number(candidate.suppressed)) ? (
                    <div className="candidate-operation-note">
                      <b>{candidate.suppressed}건</b>
                      <span>확정 알림으로 올리지 않고 관찰 후보에 유지</span>
                    </div>
                  ) : null}
                  <div className="candidate-change-list">
                    {(candidate.changes || []).map((change) => <span key={change}>{change}</span>)}
                  </div>
                </article>
              ))}
            </div>
            <div className="candidate-reason-table" role="table" aria-label="ClearFarm recommended candidate added alert reasons">
              <div className="candidate-reason-row head" role="row">
                <span>상반기 후보 추가 원인</span><span>추가 알림</span><span>관찰 일치율</span>
              </div>
              {((summary.clearfarmRecallCandidates || []).find((candidate) => candidate.id === "jan_may_candidate")?.reasonRows || []).map((row) => (
                <div className="candidate-reason-row" role="row" key={`${row.reason}-${row.addedAlerts}`}>
                  <span>{row.reason}</span>
                  <span>{row.addedAlerts}건</span>
                  <span>{formatPercent(row.hitRate)}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="perf-panel">
          <div className="perf-panel-head">
            <h3>Lead-time 평가</h3>
            <span>이벤트 시작 전 경보 포착 여부</span>
          </div>
          <div className="lead-summary">
            <div><span>사건</span><b>{lead.events || 0}건</b></div>
            <div><span>사전 포착</span><b>{lead.matched || 0}건</b></div>
            <div><span>평균 선행 시간</span><b>{lead.meanLeadHours || 0}시간</b></div>
            <div><span>정밀도 proxy</span><b>{formatPercent(lead.precisionProxy)}</b></div>
          </div>
          <div className="recall-bars" aria-label="lead time recall">
            {[
              ["24시간", lead.recall24h],
              ["48시간", lead.recall48h],
              ["72시간", lead.recall72h],
            ].map(([label, value]) => (
              <div className="recall-bar" key={label}>
                <span>{label}</span>
                <div><i style={{ width: `${Number(value) || 0}%` }} /></div>
                <b>{formatPercent(value)}</b>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="perf-panel weakness-panel">
        <div className="perf-panel-head">
          <h3>현재 취약점</h3>
          <span>운영 적용 전 반드시 설명해야 하는 숫자</span>
        </div>
        <div className="weakness-list">
          {(summary.weaknesses || []).map((item) => (
            <div className="weakness-item" key={item.title}>
              <div className="weakness-value"><b>{item.value}</b><span>{item.label}</span></div>
              <div>
                <h4>{item.title}</h4>
                <p>{item.detail}</p>
                <em>{item.next}</em>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="perf-panel plan-panel">
        <div className="perf-panel-head">
          <h3>개선 계획</h3>
          <span>성능 수치에서 바로 이어지는 작업</span>
        </div>
        <ol className="improvement-list">
          {(summary.improvementPlan || []).map((item) => <li key={item}>{item}</li>)}
        </ol>
      </section>

      <section className="perf-panel external-panel">
        <div className="perf-panel-head">
          <h3>외부 데이터 검증 근거</h3>
          <span>운영 전 신뢰도 판단용</span>
        </div>
        <div className="external-checks">
          {(summary.externalChecks || []).map((item) => (
            <div className="external-check" key={item.dataset}>
              <b>{item.dataset}</b>
              <span>{item.role}</span>
              <p>{item.result}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="perf-sources">
        <h3>수치 출처</h3>
        {(summary.sourceFiles || []).map((file) => <code key={file}>{file}</code>)}
      </section>
    </section>
  );
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
          {currentView === "performance" ? <PerformanceView /> : null}
          {currentView === "history" ? <HistoryView resolutions={resolutions} unresolve={unresolve} /> : null}
        </div>
        <footer>시연용 데이터 · 최종 운영 연결 시 incident review log와 rule tuning 결과를 함께 저장합니다.</footer>
      </main>
    </>
  );
}
