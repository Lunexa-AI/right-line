# RightLine — MVP UI Revamp / Improvements

**Product vision:** A Zimbabwe‑first, enterprise‑grade Legal AI assistant that’s trustworthy, fast, and easy to adopt — starting with employment law Q\&A and document help, scaling to multi‑domain legal ops for enterprises.

---

## 1) UX pillars (decision filters)

* **Clarity over cleverness.** Plain language, simple flows, visible citations.
* **Trust by design.** Source transparency, version stamps of laws, safe defaults, and audit trails.
* **Speed you can feel.** Streamed answers, optimistic UI, keyboard‑first.
* **Focus.** One primary task per screen; progressive disclosure for power features.
* **Local first.** English ⇄ Shona instant switch; Zimbabwe legal taxonomy & entities baked in.

Use these pillars to accept/reject features during MVP triage.

---

## 2) Primary personas & top jobs

1. **HR/People Ops Manager** (SMEs & NGOs) — needs fast, reliable summaries of labour law obligations, model letters, and policy checks.
2. **In‑house Legal/Compliance** — needs deep research, document review, and shareable audit trails.
3. **Paralegal/Lawyer** — needs drafting support with authoritative citations and export to firm templates.

---

## 3) Information Architecture (MVP scope)

* **Home** (Getting started + suggested tasks + recents)
* **Chat Workbench** (core Q\&A + citations + export)
* **Document Review** (upload PDF/DOCX → extract + explain + cite)
* **Library** (Acts/Statutory Instruments/Case law indexes; link‑outs for now)
* **Settings** (Org & privacy, language, tone presets, model choices)

Nice‑to‑have later: **Matters/Projects**, **Prompt Library**, **Admin Console**, **Usage Analytics**.

---

## 4) Screen blueprints (MVP)

### A) Home (Launchpad)

**Goal:** Orient and route users in 5 seconds.

* Top bar: brand + **Environment badge** (Preview/Enterprise) + quick links (Library, Docs, Settings).
* Hero search: “**Ask about Zimbabwe law**…” with pill chips (Working hours • Overtime • Dismissal • Medical leave).
* **Trust banner**: “Legal information only” — terse, non‑blocking; link to full policy.
* **Quick actions grid** (cards):

  * Ask about employment rights
  * Upload a document to review
  * Draft a letter (demand, warning, dismissal)
  * Compare a contract to the Labour Act
* **Recent sessions** (list with rename, pin, share, delete).
* **What’s new** (release notes popover) + **Help** (shortcuts & examples).

**Empty‑state copy** must be warm, local, and credible.

---

### B) Chat Workbench (Research & Drafting)

**Three‑pane layout:**

1. **Left rail** (optional): Sessions/Matters and saved prompts. Collapsible.
2. **Center**: Conversation stream.
3. **Right rail**: **Citations & Actions** (sticky).

**Composer:**

* Multiline input with **/slash commands** (e.g., /summarise, /draft‑letter, /explain‑like‑I’m‑HR, /shona, /cite, /compare‑to‑Labour‑Act).
* Attachments (PDF/DOCX) with inline file chips.
* Preset toggles: **Mode** (Informational • Drafting • Research), **Language** (EN/Shona), **Reading level**.
* Keyboard: `Cmd+Enter` send; `Cmd+K` command palette; `Up` to edit last message.

**Answer block:**

* Streamed text with **confidence band** (Low/Med/High) and **Last updated** law version stamp.
* **Footnote citations** \[1]\[2]\[3] with **hover cards** (title, section, year) + **Open section** action.
* **Action row**: Copy • Export (DOCX/PDF) • Save to Matter • Share link • Ask a lawyer (human escalation placeholder).
* **Reasoning controls**: “Show outline” (bullet view), “Explain in Shona,” “Legal test applied.”

**Right rail (sticky):**

* **Sources** (ordered): Sections & case law with jump links; open in viewer.
* **Related tasks**: Draft letter; Create policy checklist; Compare clauses.
* **Data policy hint**: where data is stored & retention toggle (org setting).

---

### C) Document Review Workbench

**Split view:** Left **document viewer** (PDF/DOCX with section TOC), Right **Insights**.

* Upload → show **ingest steps** (upload → parse → index → ready) with skeleton loaders.
* **Insights tabs:**

  * **Summary** (bullets) • **Issues** (risk flags) • **Clauses** (detected) • **Citations** (to law) • **Checklist** (compliance gaps).
* **Inline highlights**: Click a finding to scroll & highlight the relevant passage.
* **Actions**: Draft letter/response → select template (disciplinary invite, demand, termination, policy update).
* **Export**: Annotated PDF, DOCX summary, or JSON (devs).

---

### D) Library (lightweight index for MVP)

* Search across: **Labour Act \[Chapter]**, **SI 15/2006**, selected **case law**.
* Results as **cards** with section titles, snippet, citation, and **Open in right rail**.
* Version chip (2024‑xx). Show **last crawl** date.

---

## 5) Components & patterns (design system seed)

* **Design tokens:**

  * Color: Trust blues + emerald accents; accessible contrast AA+; warning amber for disclaimers.
  * Spacing: 4/8/12/16/24/32 scale. Radius: 12–16px (2xl for cards). Shadows: soft.
  * Typography: Inter/IBM Plex; 16px base; 600 for headings, 400 body; 14px meta.
* **Cards** (elevated, hover lift), **Chips** (filter & action), **Badges** (Preview, Beta), **Tabs** (underline motion), **Toasts** (non‑blocking), **Skeletons** (shimmer), **Empty states** (icon + one‑line + primary CTA), **Pills** for modes.
* **Citations** pattern: numeric footnotes in‑line, right‑rail list with deep links.
* **File chips**: name + pages count + remove.
* **Pagination**: cursor‑based; infinite scroll for chat history with year separators.

---

## 6) Trust, safety, and compliance UX

* **Disclaimers**: persistent but subtle; blocking only on risky flows (draft demand letters, termination advice) with one‑time acknowledgement per session.
* **Confidence + coverage**: show if answer relies on unverified/secondary sources.
* **Versioning**: “Based on Labour Act version YYYY‑MM” with link to change log.
* **Redaction toggle** on uploads (hide names/IDs before processing). Show what’s redacted.
* **Audit trail**: exportable conversation transcript with timestamps and source list.

---

## 7) Accessibility & internationalization

* EN/Shona toggle in header; per‑message translation.
* Minimum AA contrast; focus rings; skip‑to‑content; ARIA landmarks.
* All icons have labels; keyboard navigation complete.

---

## 8) Performance & perceived speed

* Pre‑warm models; show **TTFT** progress; stream tokens.
* Optimistic UI: attachments appear immediately; placeholders for citations that resolve.
* Cache last 5 sources per session; prefetch likely sections on hover.

---

## 9) Microcopy (tone & examples)

* Friendly, brief, local. Avoid legalese until asked.
* Examples for home and empty states:

  * “What is the lawful maximum overtime per week?”
  * “Draft a dismissal letter compliant with SI 15/2006, section 5.”
  * “Explain maternity leave rules in Shona for factory workers.”

---

## 10) Analytics & quality loops

* Instrument: query type, TTFT, tokens, citation clicks, export events, user feedback (👍/👎 with reason).
* Session replay (privacy‑safe) for UX; redact PII in logs by default.
* Quality dashboard: % answers with ≥2 authoritative citations, avg confidence, deflection to human.

---

## 11) MVP backlog (MoSCoW)

**Must‑have**

* Home launchpad with chips + trust banner + recents.
* Chat workbench with streaming answers, footnote citations, right‑rail sources.
* /slash commands for modes; EN/Shona toggle.
* Upload and basic Document Review (summary + citations + export PDF/DOCX).
* Keyboard shortcuts; error states; skeletons.

**Should‑have**

* Confidence band + law version stamps.
* Library index with search across Acts/SIs (subset).
* Shareable read‑only conversation link.

**Could‑have**

* Prompt Library; command palette; session pinning.
* Redaction toggle; basic audit export (JSON).

**Won’t (yet)**

* Full Matters/Projects; granular org admin; billing UI.

---

## 12) Implementation notes (React stack)

* **Next.js + React + Tailwind + shadcn/ui + lucide-react**.
* **State**: TanStack Query for IO; Zustand for UI state.
* **Editor**: TipTap/textarea hybrid; file preview with PDF.js.
* **i18n**: i18next.
* **Theming**: CSS variables for tokens; dark & light.
* **Testing**: Playwright for flows, Storybook for components.

---

## 13) Acceptance criteria (MVP)

* A: From Home, user asks “How much annual leave am I entitled to?” → streamed answer with ≥2 citations; export to PDF works.
* B: User uploads a contract → sees summary + at least 3 clause detections + jump‑to highlights.
* C: Toggling Shona re‑phrases the last answer without losing citations.
* D: Confidence + law version stamps visible on every answer block.
* E: Accessibility: All interactive controls reachable via keyboard; contrast AA+.

---

## 14) Visual style quick spec

* **Palette**: Midnight (bg), Charcoal (surfaces), Azure (primary), Emerald (affirm), Amber (warn), Crimson (danger).
* **Density**: roomy by default; compact mode for power users.
* **Iconography**: minimal; use text labels at first mention.

---

## 15) Near‑term roadmap (6–8 weeks)

**Week 1–2**

* Tokens + theme; header; Home chips; trust banner; recents.
* Chat shell with streaming + footnotes + right‑rail sources.

**Week 3–4**

* /slash commands; EN/Shona; export; shortcuts.
* Document Review v1 with summary + citations.

**Week 5–6**

* Library index + law version stamps + confidence band.
* Error handling, empty states, analytics events, basic audit export.

**Week 7–8**

* Polish: skeletons, hover‑cards for citations, shareable links, compact mode.

---

## 16) Risks & mitigations

* **Hallucination risk** → Require citations to Zimbabwe primary sources; show confidence.
* **Data sensitivity** → Default redaction; org retention setting surfaced in UI.
* **Scope creep** → Stick to pillars; MoSCoW backlog enforced at weekly review.

---

## 17) Example UI copy (ready to paste)

* Banner: “**Legal information only.** For advice on your specific situation, consult a lawyer.”
* Empty chat: “Try: *What is the minimum wage?* or *Explain dismissal procedures in Shona.*”
* Upload dropzone: “Drop a contract here to get a summary and legal references.”
* Confidence: “Confidence: **Medium** — based on 3 sources updated 2024‑06.”

---

**Outcome:** If we ship these improvements, RightLine will feel as simple as ChatGPT, as transparent as a research tool, and as pragmatic as CoCounsel — but tailored for Zimbabwe from day one.
