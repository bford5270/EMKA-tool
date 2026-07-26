import { useState } from "react";

/** "Flag this answer" -> POST /flag -> maintainer/custodian queue. */
export default function FlagControl({ result }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (reason.trim().length < 3) return;
    try {
      const r = await fetch("/flag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: result.question,
          reason,
          mode: result.mode,
          chunk_ids: (result.sources ?? []).map((s) => s.chunk_id),
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setStatus("Flagged — routed to the maintainer queue.");
      setOpen(false);
      setReason("");
    } catch (err) {
      setStatus(`Flag failed: ${err.message}`);
    }
  }

  return (
    <div className="text-sm">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="text-red-700 underline font-medium"
        >
          ⚑ Flag this answer
        </button>
      ) : (
        <form onSubmit={submit} className="flex gap-2 items-start">
          <textarea
            className="flex-1 rounded border border-slate-300 p-2"
            rows={2}
            placeholder="What is wrong? (bad citation, conflict missed, stale edition…)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button
            type="submit"
            className="rounded bg-red-700 text-white px-3 py-2 font-semibold"
          >
            Send
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded border border-slate-300 px-3 py-2"
          >
            Cancel
          </button>
        </form>
      )}
      {status && <p className="mt-1 text-slate-600">{status}</p>}
    </div>
  );
}
