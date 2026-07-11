/** Command-provided availability facts shown alongside the clinical passages.
 *  Unit-shelf governed data — always labeled, stale dates flagged loudly. */
export default function CapabilityNotes({ notes }) {
  if (!notes.length) return null;
  return (
    <section
      aria-label="Availability"
      className="rounded-lg border border-orange-300 bg-orange-50 p-3"
    >
      <div className="text-xs font-bold text-orange-900 uppercase tracking-wide mb-1">
        Loadout availability (unit-added, not custodian-verified)
      </div>
      <ul className="text-sm space-y-1">
        {notes.map((n, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{n.matched_name}</span>
            <span
              className={
                "text-xs rounded px-2 py-0.5 font-semibold " +
                (n.available === false
                  ? "bg-red-200 text-red-900"
                  : n.available
                    ? "bg-emerald-200 text-emerald-900"
                    : "bg-slate-200 text-slate-700")
              }
            >
              {n.available === false
                ? `NOT in ${n.role} loadout`
                : n.available
                  ? `in ${n.role} loadout`
                  : "availability unknown"}
            </span>
            <span className="text-xs text-slate-600">
              as-of {n.as_of} · {n.source}
            </span>
            {n.stale && (
              <span className="text-xs font-bold text-red-700 bg-red-100 rounded px-2 py-0.5">
                AS-OF DATE STALE — treat as unreliable
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
