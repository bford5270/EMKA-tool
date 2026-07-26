/** The synthesized answer — deliberately SUBORDINATE to the sources:
 *  rendered after them, in a muted panel, with its verification status.
 *  <quote src="…">…</quote> spans become inline quotes with citation chips. */

const QUOTE_RE = /<quote\s+src="([^"]+)"\s*>([\s\S]*?)<\/quote>/g;
const CONFLICT_RE = /<conflict\s+chunks="[^"]*"\s*>([\s\S]*?)<\/conflict>/g;

function renderSynthesis(text, citationsById) {
  const cleaned = text.replace(CONFLICT_RE, "$1");
  const parts = [];
  let last = 0;
  let m;
  QUOTE_RE.lastIndex = 0;
  while ((m = QUOTE_RE.exec(cleaned)) !== null) {
    if (m.index > last) parts.push({ kind: "text", value: cleaned.slice(last, m.index) });
    parts.push({ kind: "quote", chunkId: m[1], value: m[2] });
    last = m.index + m[0].length;
  }
  if (last < cleaned.length) parts.push({ kind: "text", value: cleaned.slice(last) });

  return parts.map((p, i) =>
    p.kind === "text" ? (
      <span key={i}>{p.value}</span>
    ) : (
      <span key={i} className="bg-emerald-50 border border-emerald-300 rounded px-1">
        “{p.value}”
        <span className="ml-1 text-[10px] align-super text-emerald-800 font-semibold">
          {citationsById[p.chunkId]?.citation ?? p.chunkId}
        </span>
      </span>
    )
  );
}

export default function AnswerPanel({ result }) {
  const citationsById = Object.fromEntries(
    (result.citations ?? []).map((c) => [c.chunk_id, c])
  );
  const verified = result.verification?.integrity;
  return (
    <section
      aria-label="Synthesized answer"
      className="rounded-lg border border-slate-300 bg-slate-50 p-4"
    >
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-sm font-bold text-slate-600 uppercase tracking-wide">
          Synthesized answer
        </h2>
        <span
          className={
            "text-xs font-semibold rounded px-2 py-0.5 " +
            (verified
              ? "bg-emerald-100 text-emerald-800"
              : "bg-red-100 text-red-800")
          }
        >
          {verified
            ? `✓ quotes machine-verified (${result.verification.summary})`
            : "verification failed"}
        </span>
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-800">
        {renderSynthesis(result.synthesis, citationsById)}
      </p>
      <p className="mt-3 text-xs text-slate-500">
        This synthesis is subordinate to the verbatim sources above. Verify
        against the cited publications; retrieval confidence{" "}
        {Number(result.retrieval_confidence).toFixed(2)}.
      </p>
    </section>
  );
}
