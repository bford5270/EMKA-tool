const TIER_LABELS = {
  T1: "T1 — Command",
  T2: "T2 — Service/DHA",
  T3: "T3 — CPG",
  T4: "T4 — Doctrine",
  T5: "T5 — Reference",
};

/** One verbatim source passage. Sources are PRIMARY in the UI.
 *  Unit-shelf items are watermarked in a distinct color. */
export default function SourceCard({ source }) {
  const unit = source.unit_watermark;
  return (
    <article
      className={
        "rounded-lg border bg-white shadow-sm overflow-hidden " +
        (unit ? "border-orange-400 border-2" : "border-slate-300")
      }
    >
      {unit && (
        <div className="bg-orange-100 text-orange-900 text-xs font-bold px-3 py-1 uppercase tracking-wide">
          Unit-added — not custodian-verified
        </div>
      )}
      <div className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs mb-2">
          <span className="rounded bg-slate-800 text-white px-2 py-0.5 font-semibold">
            {TIER_LABELS[source.authority_tier] ?? source.authority_tier}
          </span>
          <span className="text-slate-600 font-medium">
            {source.pub_number} — {source.title}
          </span>
          {/* corpus edition/date on every citation */}
          <span className="rounded bg-slate-200 px-2 py-0.5 text-slate-700">
            edition: {source.edition_date}
          </span>
        </div>
        <blockquote className="whitespace-pre-wrap text-sm border-l-4 border-slate-300 pl-3 text-slate-800">
          {source.text}
        </blockquote>
        <div className="mt-2 flex items-center justify-between text-xs">
          <span className="text-slate-500">{source.breadcrumb}</span>
          {/* tap-to-open the PDF at the cited page */}
          <a
            className="text-blue-700 underline font-medium"
            href={`/source/${encodeURIComponent(source.doc_id)}/page/${source.page}#page=${source.page}`}
            target="_blank"
            rel="noreferrer"
          >
            Open PDF p.{source.page}
          </a>
        </div>
      </div>
    </article>
  );
}
