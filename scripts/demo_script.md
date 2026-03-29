# Resolvly — Unified demo script (slides + live product)

One script for **judge pitches**, **demo videos**, and **live walkthroughs**. Aligns with your deck: **Track 1 · Biology & Physical Health · Claude Hackathon 2026**, problem stats, **who benefits** (three tiers), **live demo**, ethics, and **what’s next** (Phases 2–3).

Optional generated deck: **`scripts/Resolvly_Pitch_Demo.pptx`** (`pip install python-pptx` → `python scripts/generate_demo_pptx.py`).

---

## How this maps to your slides

| Your slide (from deck) | Script section |
|-------------------------|----------------|
| **Cover / title** — Resolvly, tagline, problem stats (1 in 5, &lt;1%, 99%) | **Part A** |
| **Who we’re building for** — quote, Primary / Secondary / Tertiary | **Part B** |
| **Technical + demo** (may be same deck section as “solution”) | **Part C + Part D** |
| **Ethics** (if separate in deck) | **Part E** |
| **What’s Next** — Phases 2–3, pillars | **Part F** |

---

## Timing (target **~5–7 minutes** with demo)

| Block | Time | What |
|-------|------|------|
| **Part A** — Cover + problem stats | ~0:45–1:00 | Slides |
| **Part B** — Who benefits (quote + three tiers) + why it scales | ~1:00–1:30 | Slides |
| **Part C** — Technical execution → handoff | ~0:45–1:00 | Slides |
| **Part D** — **Live demo** | ~2:00–3:00 | Product |
| **Part E** — Ethics (harms + **how the product addresses them**) + three questions | ~1:15–1:45 | Slides |
| **Part F** — What’s next (roadmap) + thanks | ~0:45–1:00 | Slides |

---

## Before you go live — setup checklist

- [ ] **Backend** running (e.g. uvicorn) with env vars if needed  
- [ ] **Frontend** dev server: `npm run dev`  
- [ ] Vite proxy / API base URL points at backend  
- [ ] Test PDFs: `test_documents/denial_letter.pdf`, `explanation_of_benefits.pdf`, `medical_bill.pdf`  
- [ ] Browser ~100% zoom, notifications off  
- [ ] Optional: second monitor for slides; mic/camera tested  

---

## What judges care about — weave these in

- **Real problem, specific people** — not a vague “everyone.”  
- **AI empowers** — does not replace patients, clinicians, or lawyers.  
- **Ethics** — who benefits, who could be harmed, safeguards.  
- **Working prototype** — show it.  
- **Clear problem and approach.**

### Three questions — answer out loud (**Part E**)

1. **Who are you building this for, and why do they need it?**  
2. **What could go wrong, and what would you do about it?**  
3. **How does this help people rather than make decisions for them?**

---

## Part A — Cover slide: Resolvly + problem scale (~45–60 sec)

**On screen:** *Track 1 · Biology & Physical Health · Claude Hackathon 2026* — **Resolvly** — *Navigating health insurance denials* — *A free, AI-powered tool for Indiana patients — and eventually, every American.*

**Say:**

> “I’m presenting **Resolvly** — **navigating health insurance denials** — on **Track 1: Biology and Physical Health** for the **Claude Hackathon**.  
>   
> We’re building a **free, AI-powered** path that starts with **Indiana patients** because we can ground the product in **real state insurance context** — with a roadmap to **scale nationally** so this can help **every American** who gets stuck in the same paperwork.  
>   
> The scale of the problem is staggering: about **one in five insured Americans** faces a **denied claim**. Yet **less than one percent** of denials are ever **appealed** — and **ninety-nine percent** of patients **don’t know they can fight back**. That gap isn’t because people don’t care — it’s because **the system speaks in codes and jargon**, not plain English.”

**Optional closer for this slide:**

> “Resolvly exists to **close that gap** — starting at the kitchen table.”

---

## Part B — Who we’re building for · why it matters · why it scales (~1:00–1:30)

**On screen:** *Problem · Who benefits · Why it scales* — **Who We’re Building For — And Why It Matters** — quote box — three beneficiary rows.

**Lead with the human moment (quote):**

> “We’re building for **the person who opens a denial letter at their kitchen table** and has **no idea what it means** or **what to do next** — sometimes staring at a **five‑figure bill** they **shouldn’t owe** if the denial were overturned or fixed.”

**Three beneficiary levels (say explicitly):**

> “**Primary:** **Uninsured and underinsured Indiana patients** holding denial letters with **no idea what to do** — that’s our **first beachhead**.  
>   
> **Secondary:** **Small medical practices** that **don’t have dedicated billing teams** to chase every denial — we can reduce their load with **summaries and exports** over time.  
>   
> **Tertiary:** **Patient advocates and social workers** who help **vulnerable populations** — the same explanations and drafts help them **move faster** for the people they serve.”

**Why it matters (tie to health access):**

> “This is **access** in a **financial and practical** sense: if you can’t decode the denial, you can’t use the **appeal rights** you already have — and care and money both get stuck.”

**Why it scales (one breath):**

> “Denial letters and EOBs follow **predictable patterns** nationwide. Our architecture uses **live lookups** from **authoritative public sources** — CMS-style codes, regulations, state insurance context — so we’re not maintaining a **stale private encyclopedia** of billing rules.”

**Bridge:**

> “Next: **does the product actually work?** I’ll walk through **what we built**, then **show it live**.”

---

## Part C — Technical execution · Purposeful AI → live demo (~60–90 sec, then hands-on)

**Say:**

> “**Does the core functionality work?** In our prototype, users **upload real PDFs** — denial letter, EOB, and bill — and give **plan context** so **deadlines and routing** are right — **ACA, ERISA, Medicaid**, employer vs marketplace, etc.  
>   
> We **extract** entities, **enrich** from **verified public sources**, then **analyze**: root-cause style classification, deadlines, completeness-style checks, and outputs — **plain-language summary**, **action checklist**, **bill breakdown**, **appeal-oriented drafting**, and **Indiana-focused resources** where we’ve wired them.  
>   
> **Is AI purposeful?** Yes — for **unstructured text**, **classification**, and **drafting** — plus **rules and structured extraction** where that’s the right tool — not a single **black-box score** that replaces reading your own mail.  
>   
> **Stack:** **React** and **FastAPI** — orchestration and agents. For the hackathon, flows are **session-forward** so we’re not building a **long-term PHI warehouse** by default.  
>   
> **I’m switching to the product.**”

---

## Part D — Live product demo (~2–3 min)

**Do and narrate:**

1. Open **`/analyze`** (or landing → Get started).  
   **Say:** “**Upload wizard** — we capture **policy context** so **deadlines** and **regulatory routing** aren’t wrong.”

2. **Select plan type** and **funding** (match your story — e.g. aligns with Indiana / employer narratives).

3. **Upload** three PDFs from **`test_documents/`** — denial, EOB, medical bill.

4. Start analysis.  
   **Say:** “**Extract** → **unified claim object** → **code lookup**, **regulation / state rules**, **analysis**. Timing depends on **APIs**.”

5. Open **Action Plan** (or primary results).  
   **Say:** “**Recovery roadmap** — deadlines and steps from **their** documents.”

6. **Quick tour — pick two:** Bill breakdown · Appeal drafting · Code lookup / Indiana resources.

**One-liner:**

> “Summaries and drafts are **starting points** — users **verify** and **decide**.”

**Backup if slow API:**

> “Stages: **extraction → enrichment → analysis → outputs**.”

**Backup if error:**

> “Production would **surface errors**; here I use **pre-tested** `test_documents/`.”

---

## Part E — Ethics · how our **existing product** addresses harms · three questions (~1:15–1:45)

**Say — frame the harms:**

> “We took **harms** seriously: **over-trusting** AI summaries, **false confidence** about **legal** outcomes, mishandling **sensitive health and financial data**, and **replacing** human judgment. Here’s how **what we actually built** pushes back on those risks — not just slide bullets.”

**Say — map harms to the live product (pick depth to fit time):**

> **Data & retention.** Our MVP is built **without a claims database**: analysis results live in the **browser session** for the demo flow — we’re **not** building a long-term **PHI warehouse** by default. On the server, documents are processed in **memory** for the request and discarded; that matches our **no–PHI-at-rest** posture for v1 and limits breach blast radius compared to storing uploads.  
>   
> **Legal & medical overreach.** **Every major screen** carries an explicit disclaimer: we’re an **advocacy / information** tool — **not a law firm**, **not medical advice**, **not financial advice**. The **landing page**, **upload/analyze flow**, **action plan**, **bill breakdown**, **appeal drafting**, and **results** views all say that in **footer copy** tied to what the user is looking at — e.g. action plans reference **algorithmic analysis** and **public** regulatory sources; appeal drafting tells users to **edit before sending** and to involve an **attorney or advocate** before submission.  
>   
> **Transparency vs. black box.** Explanations lean on **retrieved, checkable sources** — **CMS-style** code definitions, **regulatory** lookup, **state DOI–style** context — so users aren’t asked to trust a mystery score alone. Where the pipeline is uncertain, we surface **assumptions** and **completeness** signals so **garbage-in** doesn’t silently become **confidence-out**.  
>   
> **Autonomy.** We **don’t file appeals**, **don’t call insurers on your behalf**, and **don’t** present drafts as final — the user **reviews**, **edits**, and **decides**. That’s **human-in-the-loop by design**, not a checkbox.

**Say — the three questions (keep tight):**

> **Who for, and why?** **Kitchen-table patients**, **small practices**, **advocates** — clarity **before** deadlines.  
> **What could go wrong?** We **name** misinterpretation and data sensitivity — and **encode** mitigations in **UI**, **architecture**, and **disclosure** above.  
> **Help vs. decide?** We **inform and draft**; **filing and final calls stay with the person** — and with **professionals** when the disclaimer says so.

**If you’re under ~90 seconds for Part E:** Say the **harms line**, then only **three product proofs**: **(1)** session / no persistent claim DB, **(2)** footers + appeal “edit before send,” **(3)** no auto-filing — then the **three questions** in one sentence each.

---

## Part F — What’s next · impact · close (~45–60 sec)

**On screen (your roadmap slide):** *What’s Next for Resolvly* — Phases 2–3 (weeks 5–12); note **V2** adds **Supabase persistence** (or equivalent) when you’re ready for accounts and durable storage.

**Say (hit each pillar briefly):**

> “**What’s next** — we’re thinking in **three pillars**:  
>   
> **Polish and reach:** **Plain‑English** modes for **low digital literacy**, **multi‑language** starting with **Spanish**, better **inputs** — **mobile camera**, **clipboard paste** — and a **WCAG AA** accessibility pass so we don’t exclude the people who need this most.  
>   
> **Expand coverage:** **All 50 states** with **state-specific deadline logic**, deeper integration with **Department of Insurance** complaint and review paths, an **anonymous denial-trends** dataset for transparency, and **provider-facing exports** for small practices.  
>   
> **Sustainable impact:** A path to **B2B** tools like a **provider portal**, using denial insights for **advocacy and policy**, **partnerships** with patient-advocacy orgs, and — when we persist data — a serious **compliance** story: **HIPAA BAA**, grants or nonprofit paths, not growth at the expense of trust.  
>   
> **Impact:** If we help people **use appeal rights they already have**, we improve **access** to care and reduce **harm from administrative failure**.  
>   
> Thank you — **questions welcome**.”

---

## If you’re short on time — cut in this order

1. Part A — keep **one stat** (e.g. 1 in 5) only.  
2. Part B — quote **or** three tiers, not both in full.  
3. Part D — **Analyze → Action Plan** only.  
4. Part E — **three product proofs** + **three questions** only (skip long harm list).  
5. Part F — **one pillar** + thanks.

---

## One-page cheat sheet (60 seconds before you record)

- **One-liner:** **Resolvly** — free AI help **navigating denials**; **Indiana first**, **America-scale** vision.  
- **Stats:** **1 in 5** denied · **&lt;1%** appealed · **99%** don’t know they can fight.  
- **Who:** **Kitchen-table patient** · **small practices** · **advocates**.  
- **Demo:** `/analyze` → 3 PDFs → run → **Action Plan** + 2 screens.  
- **AI:** Assistive + rules; **not** replacing judgment.  
- **Ethics:** Footers + session/MVP data posture + **edit-before-send** + **no auto-filing**; **user in control**.  
- **Next:** **Access** · **50 states** · **DOI** · **WCAG** · **V2 persistence** thoughtfully.  

---

## Files in this repo

| File | Purpose |
|------|---------|
| `scripts/demo_script.md` | **This** — full spoken script |
| `scripts/generate_demo_pptx.py` | Optional generated **`Resolvly_Pitch_Demo.pptx`** |
| `test_documents/*.pdf` | Sample uploads for the live demo |
