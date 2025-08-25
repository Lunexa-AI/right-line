# Gweta — Enterprise Web UI (MVP) Improvements

**Product vision:** Gweta is an AI‑native, enterprise‑grade legal assistant for Zimbabwean organisations (law firms, enterprises, government). It prioritises accuracy, citations, and speed. For citizens, Gweta WhatsApp is a free “smart lawyer friend.”

---

## 1) UX pillars (decision filters)

* **Less ink.** Hide non‑essentials; fewer controls, fewer borders, fewer words.
* **Evidence‑first.** Citations and provenance must be one glance away; no speculation.
* **Speed you can feel.** Streamed answers, minimal layout shifts, keyboard‑first.
* **Single‑task focus.** One primary action on screen; progressive disclosure.
* **Local first.** EN ⇄ Shona instant switch; ZW legal taxonomy & entities.

Use these pillars to accept/reject features during MVP triage.

---

## 2) Primary personas & top jobs

1. **HR/People Ops Manager** (SMEs & NGOs) — needs fast, reliable summaries of labour law obligations, model letters, and policy checks.
2. **In‑house Legal/Compliance** — needs deep research, document review, and shareable audit trails.
3. **Paralegal/Lawyer** — needs drafting support with authoritative citations and export to firm templates.

---

## 3) Information Architecture (MVP scope)

Single, focused workspace (no suggested chips, no busy home):
* **Header**: Brand, environment badge, account menu, theme toggle.
* **Omnibox (command bar)**: One field to search/ask. `Cmd/Ctrl+K` opens it anywhere.
* **Conversation area**: Streamed answers with TL;DR and key points.
* **Evidence rail (right)**: Source list with quick jump; collapsible.
* **Attachment affordance**: Minimal “Upload document” near the composer for basic doc Q&A.

Nice‑to‑have later: **Matters/Projects**, **Prompt Library**, **Admin Console**, **Usage Analytics**.

---

## 4) Screen blueprints (MVP)

### A) Workspace (single‑screen MVP)

* Top bar (minimal). No secondary nav, no suggested pills.
* Centered Omnibox with placeholder “Search or ask about Zimbabwean law…”.
* Below: conversation stream; first answer replaces empty state.
* Discreet trust banner (one line) above stream.

---

### B) Conversation

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

* Answer card: TL;DR, key points, copy/share, confidence band. Minimal chrome.
* Evidence rail: ordered citations; hover card shows title/section/year; “open source”.
* Controls: feedback (👍/👎), “Explain in Shona”, “Export PDF”.

**Right rail (sticky):**

* **Sources** (ordered): Sections & case law with jump links; open in viewer.
* **Related tasks**: Draft letter; Create policy checklist; Compare clauses.
* **Data policy hint**: where data is stored & retention toggle (org setting).

---

### C) Document Q&A (lightweight)

**Split view:** Left **document viewer** (PDF/DOCX with section TOC), Right **Insights**.

* Upload PDF/DOCX → show ingest steps (parse → chunk → ready). Skeletons only; no heavy viewers.
* Ask questions about the uploaded file; answers cite both doc passages and statutes.

---

### D) Library (lightweight index for MVP)

* Search across: **Labour Act \[Chapter]**, **SI 15/2006**, selected **case law**.
* Results as **cards** with section titles, snippet, citation, and **Open in right rail**.
* Version chip (2024‑xx). Show **last crawl** date.

---

## 5) Components & patterns (ink‑diet edition)

* **Design tokens:**

  * Color: Trust blues + emerald accents; accessible contrast AA+; warning amber for disclaimers.
  * Spacing: 4/8/12/16/24/32 scale. Radius: 12–16px (2xl for cards). Shadows: soft.
  * Typography: Inter/IBM Plex; 16px base; 600 for headings, 400 body; 14px meta.
* Omnibox: single input, supports `/` commands; grows multi‑line as needed.
* Answer card: generous line‑height, no frames; faint divider between turns.
* Evidence list: numbered links; no cards; truncate long titles with tooltip.
* Toasts not modals; skeletons for loading; focus rings for accessibility.

Removed: suggestion chips/pills, busy quick‑action grids, left sidebar by default.

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

## 8) Performance principles

* Pre‑warm models; show **TTFT** progress; stream tokens.
* Avoid heavy DOM; no permanent side rails on small screens.
* Cache last sources for quick hover previews.

---

## 9) Microcopy (enterprise tone)

* Friendly, brief, local. Avoid legalese until asked.
* Omnibox placeholder: “Search or ask about Zimbabwean law…”
* Feedback: “Helpful?” / “Not helpful?”
* Evidence label: “Sources”.
* WhatsApp tagline: “Get the smart lawyer friend you always wanted.”

---

## 10) Analytics & quality loops

* Instrument: query type, TTFT, tokens, citation clicks, export events, user feedback (👍/👎 with reason).
* Session replay (privacy‑safe) for UX; redact PII in logs by default.
* Quality dashboard (later): % answers with ≥2 authoritative citations, avg confidence, deflection to human.

---

## 11) MVP scope (MoSCoW)

**Must‑have**

* Omnibox + streamed answers with citations & confidence.
* Evidence rail with jump links; copy/share.
* EN/Shona; basic doc upload for Q&A.

**Should‑have**

* Export answer as PDF; shareable read‑only link.
* Minimal analytics events (TTFT, feedback, citation clicks).

**Could‑have**

* Prompt Library; command palette; session pinning.
* Redaction toggle; basic audit export (JSON).

**Won’t (yet)**

* Full Matters/Projects; granular org admin; billing UI.

---

## 12) Implementation notes (stack‑agnostic)

* Keep DOM shallow; prefer CSS variables; avoid heavy bespoke components.
* Keyboard: `Enter` send; `Shift+Enter` newline; `Cmd/Ctrl+K` for command palette.
* Responsiveness: evidence rail collapses under 1024px; omnibox stays sticky.

---

## 13) Acceptance criteria (MVP)

* Ask: “Annual leave entitlement” → streamed answer with ≥2 sources + confidence.
* Upload a contract → ask “Is notice period compliant?” → cites doc + statute.
* Toggle to Shona maintains citations.
* Accessibility: all core actions keyboard‑reachable; AA contrast.

---

## 14) Visual style quick spec

* **Palette**: Midnight (bg), Charcoal (surfaces), Azure (primary), Emerald (affirm), Amber (warn), Crimson (danger).
* **Density**: roomy by default; compact mode for power users.
* **Iconography**: minimal; use text labels at first mention.

---

## 15) Near‑term roadmap (6–8 weeks)

**Week 1–2**

* Tokens + theme; header; workspace shell (no suggestions).
* Chat shell with streaming + evidence rail.

**Week 3–4**

* /slash commands; EN/Shona; export; shortcuts.
* Document Review v1 with summary + citations.

**Week 5–6**

* Library index (later) + confidence band.
* Error handling, analytics events, basic audit export.

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

**Outcome:** An enterprise‑ready, less‑ink, evidence‑first MVP that is actually useful today (RAG + citations + doc Q&A), while preparing the surface for agentic features later. Citizens get a free WhatsApp “lawyer friend.”
