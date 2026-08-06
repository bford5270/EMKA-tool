# DHA Innovation Grant — $10,000 Request

Pitch email and budget for a $10,000 DHA innovation award funding Phase 0 of EMKA
(see `EMKA_Framework_HSOAG.md` for the full concept paper).

**Posture:** the software is already built and costs the government nothing. The
$10,000 is a hardware-only request that buys the two devices needed to measure the
concept on the two tiers we would actually field.

Fill in every `[bracketed]` item before sending. See "Before you send" at the bottom.

---

## The email

**To:** [Innovation program POC / DHA J-9 / MHS innovation inbox]
**Cc:** [Commanding Officer, 1st Medical Battalion] · [1st MLG Surgeon] · [I MEF Surgeon]
**Subject:** $10K Innovation Request — Air-Gapped, Citation-Verified Clinical Reference for DDIL Environments (EMKA)

[Salutation],

I am requesting **$10,000 in [program name] innovation funds** to complete a 90-day
prototype validation of the Expeditionary Medical Knowledge Assistant (EMKA): a
fully air-gapped, PHI-free reference system that answers a corpsman's or provider's
plain-language clinical question from the doctrine and CPGs we already own — and
proves the answer by quoting the source verbatim with a pinpoint citation.

**The problem.** Deployed medicine assumes connectivity it will not have. JTS CPGs,
CoTCCC guidelines, VA/DoD CPGs, and the NTTP 4-02 series live on networked portals
that fail under bandwidth denial, EMCON, and MASCAL time pressure. A hard drive full
of PDFs technically solves offline access and fails in practice — no one pages
through a 400-page publication at 0300. The gap is not knowledge. It is access.

**What makes this different from a chatbot.** EMKA retrieves and cites; it does not
recall. Every displayed quotation is machine-verified character-for-character
against the source PDF before it reaches the screen, and when retrieval confidence
is insufficient the system abstains — it says "not in corpus" rather than
improvising. It also reasons over the querying element's actual formulary and AMAL,
surfacing a source's own stated alternative when first-line is unavailable, never an
invented substitution. A skeptical provider can open the cited page and check it in
seconds. The trust model is "verify me," not "believe me."

**What you are not funding.** This is not a software development effort. The full
stack — ingestion with citation-fidelity guarantees, hybrid retrieval with an
abstention gate, grounded synthesis, the verbatim verifier, the resource-aware
capability layer, the web interface, and a gold-standard evaluation harness — is
**already built, in-house, at zero cost to the government**, and is in the
repository today. The entire software and model stack is open-source or
open-weight: **$0 in licensing, now and at scale.** No program of record, no
network connectivity, no PHI authority to operate, no contract vehicle.

**What the $10,000 buys.** Hardware only — the two devices required to measure the
two-tier fielding concept rather than assert it:

| # | Line item | Cost | Why it is required |
|---|---|---|---|
| 1 | Tier 2 compute appliance — 128 GB unified-memory x86 mini-workstation (Strix Halo class) | $4,800 | The Role 2 / planning-cell configuration. Unified memory runs a 70B-class quantized model in a single small box on ordinary power. x86 keeps it inside standard DoD imaging and STIG baselines. |
| 2 | Tier 1 edge module — 64 GB embedded AI module (Jetson AGX Orin class) | $2,000 | The Role 1 / BAS configuration: sub-1 kg, 15–60 W, hours on a battery bank. Without it, the two-tier recommendation is an assumption instead of a measurement. |
| 3 | Storage and corpus media — 4 TB NVMe plus write-once media for signed corpus packages | $450 | Corpus, model weights, and system image with growth room; write-once media is the physical-transfer update path for an air-gapped device. |
| 4 | Isolated network kit and transit case — unmanaged switch, cabling, ruggedized case | $600 | Client access is wired Ethernet to an isolated switch. No WAN hardware is procured. |
| 5 | Tactical power validation kit — 300 Wh battery bank, DC inverter, inline watt meter | $450 | Converts the power claim into measured runtime at each tier under load. |
| 6 | Field client end-user device — ruggedized tablet, wired/isolated | $1,000 | Validates the interface where it will actually be read: gloved hands, poor light, one-handed. |
| 7 | Consumables and contingency (7%) | $700 | Cabling, adapters, media, thermal and mounting hardware. |
|   | **Total** | **$10,000** | |

Software and model licensing: **$0.** Labor: **$0 requested** — development is in-kind
and already expended; sustainment is the unit's [~2 hours of maintainer training per
quarter]. No travel, no salary, and no recurring costs are requested.

**What you get back in 90 days.**

1. Two provisioned, air-gapped devices running the complete stack — no network interface, verifiable by inspection.
2. Measured results against seven pre-registered metrics on a ~200-case SME-authored question set (a 30-case seed already exists in the repository): retrieval recall@10 ≥ 95%, citation accuracy ≥ 99%, verbatim-quote integrity 100% enforced, grounded-answer rate ≥ 98%, honest-abstention ≥ 95%, latency ≤ 30 s, and a zero-tolerance critical-failure count adjudicated by blinded clinical review.
3. A head-to-head Tier 1 vs. Tier 2 benchmark — a fielding recommendation supported by data on which model class each role actually needs.
4. Measured runtime on tactical power at both tiers.
5. An accreditation-ready artifact package for the servicing AO: reproducible build manifest, hash-verified component inventory, STIG-hardened image, and audit-log design for the standalone/PIT pathway.
6. A results brief to [HSOAG / sponsor] and a draft manuscript for *Military Medicine* — offline retrieval-augmented reference systems have not been evaluated in an operational military medical setting.

**Risk posture.** PHI-free by design — the device indexes publications only and
carries a persistent no-PHI banner. Air-gapped by design — there is no WAN interface
on the device. Unclassified corpus with appropriate distribution statements. If the
metrics do not hold, the honest answer is "not yet," the finding is still
publishable, and the government owns two commodity computers and a documented,
reproducible build. The downside is bounded at $10,000; the upside is a validated,
zero-licensing capability that scales to any deployed medical element.

I have the concept paper, system design document, and working prototype available
and can demonstrate the system in person or over VTC at your convenience. Happy to
send the read-ahead in advance of [date].

Very respectfully,

Brian S. Ford, CDR, MC, USN
Chief Medical Officer, 1st Medical Battalion, 1st Marine Logistics Group, I MEF
[phone] · [email]

*Attachments: EMKA Capability Concept Paper (HSOAG); Phase 0 budget detail*

---

## Before you send

**Fill in:** program name and POC, cc line, salutation, phone/email, demo or
read-ahead date, and confirm the maintainer-training figure in the labor sentence.

**Verify against the actual solicitation:**

- **Allowability.** The budget is deliberately non-labor, non-travel — equipment and
  supplies only — because most micro-grants at this level prohibit salary. If yours
  permits SME time or exercise travel, that is the highest-value place to add.
- **Micro-purchase threshold.** Two devices at $4,800 and $2,000 sit under the
  simplified-acquisition/GPC limits individually. Confirm the program's own
  procurement mechanism before promising a 90-day timeline.
- **Period of performance.** The email says "90 days"; state a firm start date if
  the solicitation requires one.
- **Prior coordination.** Section 9.3 of the concept paper commits to engaging the
  ISSM and AO *before* hardware purchase. If that engagement has already started,
  say so in the risk-posture paragraph — reviewers fund efforts that have already
  cleared the accreditation question.

**If you need a shorter version** for a cold intro or a submission form with a
character limit, cut to: the ask, the problem paragraph, "what makes this different
from a chatbot," the budget table, and the 90-day deliverables list. The
what-you-are-not-funding paragraph is the one that most differentiates this request —
keep it if you keep only one.
