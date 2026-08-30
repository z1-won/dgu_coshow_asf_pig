import { useCallback, useState } from "react";

const STORAGE_KEY = "pigproject_incident_resolutions_v4";

function load() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function save(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage 접근 불가(사생활 보호 모드 등) 시 조용히 무시 -- 세션 내 상태는 유지된다.
  }
}

export function useResolutions() {
  const [resolutions, setResolutions] = useState(load);

  const resolve = useCallback((id, decision) => {
    setResolutions((prev) => {
      const next = { ...prev, [id]: { decision, at: new Date().toISOString() } };
      save(next);
      return next;
    });
  }, []);

  const unresolve = useCallback((id) => {
    setResolutions((prev) => {
      const next = { ...prev };
      delete next[id];
      save(next);
      return next;
    });
  }, []);

  return { resolutions, resolve, unresolve };
}
