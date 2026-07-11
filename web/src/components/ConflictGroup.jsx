import SourceCard from "./SourceCard.jsx";

/** Conflicting sources rendered SIDE BY SIDE under an explicit flag.
 *  The system surfaces disagreement; the clinician resolves it. */
export default function ConflictGroup({ conflicts, sources }) {
  const byId = Object.fromEntries(sources.map((s) => [s.chunk_id, s]));
  return (
    <section aria-label="Conflicting sources" className="space-y-4">
      {conflicts.map((c, i) => {
        const items = c.chunk_ids.map((id) => byId[id]).filter(Boolean);
        return (
          <div
            key={i}
            className="rounded-lg border-2 border-purple-400 bg-purple-50 p-3"
          >
            <div className="text-purple-900 font-bold text-sm mb-1 uppercase tracking-wide">
              ⚠ These sources differ
            </div>
            {c.description && (
              <p className="text-sm text-purple-900 mb-3">{c.description}</p>
            )}
            <div className="grid md:grid-cols-2 gap-3">
              {items.map((s) => (
                <SourceCard key={s.chunk_id} source={s} />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
