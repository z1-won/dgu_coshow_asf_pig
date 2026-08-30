// KRDS(github.com/KRDS-uiux/krds-uiux) 실제 아이콘 경로를 그대로 쓰는 것(닫기/정보/경고/성공/오류)과,
// KRDS에 없어 같은 "채움(fill)" 방식으로 새로 그린 축산 도메인 아이콘(체온/사료/환기/카메라/담당자 등)으로 구성된다.

function Svg({ className, children }) {
  return (
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className={className}>
      {children}
    </svg>
  );
}

export function IconInfoFill({ className }) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="10" fill="#0b78cb" />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        fill="#fff"
        d="M11.9 9.44a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4Zm-.6 1v1.2h1.1v3.95h.9v1.2h-4v-1.2h1.3v-3.95h-1.1v-1.2h1.8Z"
      />
    </Svg>
  );
}

export function IconWarningFill({ className }) {
  return (
    <Svg className={className}>
      <path fill="#c78500" d="M11.13 2a1 1 0 0 1 1.74 0l9.96 17.25a1 1 0 0 1-.87 1.5H2.04a1 1 0 0 1-.87-1.5L11.13 2Z" />
      <path fillRule="evenodd" clipRule="evenodd" fill="#fff" d="M13 8.5H11v6H13v-6ZM13 16H11v2H13v-2Z" />
    </Svg>
  );
}

export function IconSuccessFill({ className }) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="10" fill="#228738" />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        fill="#fff"
        d="m16.78 8.32-5.7 7.94-4.21-4.48 1.16-1.1L11 13.75l4.56-6.36 1.22.93Z"
      />
    </Svg>
  );
}

export function IconDangerFill({ className }) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="10" fill="#de3412" />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        fill="#fff"
        d="M12 13.13 14.97 16.1l1.13-1.13-2.97-2.97 2.97-2.97-1.13-1.13-2.97 2.97-2.97-2.97-1.13 1.13L9.87 12l-2.97 2.97 1.13 1.13L11 13.13Z"
      />
    </Svg>
  );
}

export function IconClose({ className }) {
  return (
    <Svg className={className}>
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M20.48 4.65a.85.85 0 0 0-1.2-1.2L12 10.87 4.65 3.51a.85.85 0 0 0-1.2 1.2l7.35 7.35-7.35 7.36a.85.85 0 0 0 1.2 1.2L12 13.13l7.35 7.35a.85.85 0 0 0 1.2-1.2l-7.35-7.35 7.28-7.28Z"
      />
    </Svg>
  );
}

export function IconHome({ className }) {
  return (
    <Svg className={className}>
      <path d="M12 3 21 10.8V21a1 1 0 0 1-1 1h-4.5v-7h-7v7H4a1 1 0 0 1-1-1V10.8L12 3Z" />
    </Svg>
  );
}

export function IconLayout({ className }) {
  return (
    <Svg className={className}>
      <rect x="3.5" y="4" width="7.2" height="7.2" rx="1.3" />
      <rect x="13.3" y="4" width="7.2" height="7.2" rx="1.3" />
      <rect x="3.5" y="13.2" width="7.2" height="7.2" rx="1.3" />
      <rect x="13.3" y="13.2" width="7.2" height="7.2" rx="1.3" />
    </Svg>
  );
}

export function IconChecklist({ className }) {
  return (
    <Svg className={className}>
      <rect x="4.5" y="3.5" width="15" height="17.5" rx="1.8" />
      <rect x="8.5" y="1.8" width="7" height="3.2" rx="1" fill="var(--surface)" />
      <path fill="var(--surface)" d="M7.3 11.7 9.7 14l3.9-4.3 1.1 1-5 5.5-3.4-3.6 1-0.9Z" />
    </Svg>
  );
}

export function IconThermometer({ className }) {
  return (
    <Svg className={className}>
      <path d="M13 3.5a2 2 0 0 0-4 0v9.3a4 4 0 1 0 4 0V3.5Zm-2 12.7a1.6 1.6 0 1 1 0-3.2 1.6 1.6 0 0 1 0 3.2Z" />
    </Svg>
  );
}

export function IconBowl({ className }) {
  return (
    <Svg className={className}>
      <path d="M3 10.5h18a1 1 0 0 1 .98 1.2A8.2 8.2 0 0 1 13.9 18h-3.8a8.2 8.2 0 0 1-8.08-6.3A1 1 0 0 1 3 10.5Z" />
      <ellipse cx="12" cy="9.6" rx="8.4" ry="1.9" />
    </Svg>
  );
}

export function IconDroplet({ className }) {
  return (
    <Svg className={className}>
      <path d="M12 2.7 7 8.9a7.2 7.2 0 1 0 10 0L12 2.7Zm0 16.4a3.7 3.7 0 0 1-3.7-3.7h1.8A1.9 1.9 0 0 0 12 17.3v1.8Z" />
    </Svg>
  );
}

export function IconWind({ className }) {
  return (
    <Svg className={className}>
      <rect x="2.5" y="7.2" width="12" height="2" rx="1" />
      <rect x="2.5" y="11.5" width="16" height="2" rx="1" />
      <rect x="2.5" y="15.8" width="9" height="2" rx="1" />
    </Svg>
  );
}

export function IconCamera({ className }) {
  return (
    <Svg className={className}>
      <path d="M9.2 5h5.6l.9 1.6H19a1.6 1.6 0 0 1 1.6 1.6v9.2a1.6 1.6 0 0 1-1.6 1.6H5a1.6 1.6 0 0 1-1.6-1.6V8.2A1.6 1.6 0 0 1 5 6.6h3.3L9.2 5Z" />
      <circle cx="12" cy="13" r="3.4" fill="var(--surface)" />
      <circle cx="12" cy="13" r="2.1" />
    </Svg>
  );
}

export function IconUser({ className }) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="7.8" r="3.4" />
      <path d="M4.6 20c0-3.6 3.3-6.1 7.4-6.1s7.4 2.5 7.4 6.1a1 1 0 0 1-1 1H5.6a1 1 0 0 1-1-1Z" />
    </Svg>
  );
}

export function IconBrand({ className }) {
  return (
    <Svg className={className}>
      <path d="M12 2.6c-4.9 0-8.9 3.7-8.9 8.3 0 3 1.7 5.6 4.3 7.1l-.6 2.8a.9.9 0 0 0 1.2 1l3.1-1.3c.3 0 .6.1.9.1s.6 0 .9-.1l3.1 1.3a.9.9 0 0 0 1.2-1l-.6-2.8c2.6-1.5 4.3-4.1 4.3-7.1 0-4.6-4-8.3-8.9-8.3Zm-4 8.6a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Zm8 0a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Zm-4 3.6c-1.4 0-2.6-.6-2.6-1.4S10.6 12 12 12s2.6.6 2.6 1.4-1.2 1.4-2.6 1.4Z" />
    </Svg>
  );
}

export function IconHistory({ className }) {
  return (
    <Svg className={className}>
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M6 3.5A1.5 1.5 0 0 0 4.5 5v15A1.5 1.5 0 0 0 6 21.5h12a1.5 1.5 0 0 0 1.5-1.5V5A1.5 1.5 0 0 0 18 3.5h-2.3a2.2 2.2 0 0 0-2-1.5h-3.4a2.2 2.2 0 0 0-2 1.5H6Zm3-.3h6a.7.7 0 0 1 0 1.4H9a.7.7 0 0 1 0-1.4Zm-.4 9.1 2.2 2.2 4.6-5-1.1-1-3.6 3.9-1.2-1.2-1 1.1Z"
      />
    </Svg>
  );
}

// name → 컴포넌트 매핑 (카테고리 뱃지처럼 문자열 키로 아이콘을 골라야 하는 자리에서 사용)
export const ICONS_BY_NAME = {
  infoFill: IconInfoFill,
  warningFill: IconWarningFill,
  successFill: IconSuccessFill,
  dangerFill: IconDangerFill,
  thermometer: IconThermometer,
  bowl: IconBowl,
  droplet: IconDroplet,
  wind: IconWind,
  camera: IconCamera,
  user: IconUser,
  checklist: IconChecklist,
  layout: IconLayout,
  home: IconHome,
  history: IconHistory,
  close: IconClose,
};

export function Icon({ name, className }) {
  const Cmp = ICONS_BY_NAME[name];
  if (!Cmp) return null;
  return <Cmp className={className} />;
}
