// Pure helpers that don't depend on where the data came from (static build-time
// snapshot vs. live API) -- kept separate from DashboardDataContext.jsx so
// components can use them without pulling in the fetch/fallback machinery.

export function durationDays(startStr, endStr) {
  return Math.max(1, Math.round((new Date(endStr) - new Date(startStr)) / 86400000));
}
