# Gweta — MVP UI Task List (Enterprise Web)

> Scope: Implement the less-ink, evidence-first enterprise workspace described in `MVP_UI_IMPROVEMENTS.md`. Remove suggestion chips. Deliver omnibox + streamed answers + evidence rail, with lightweight document Q&A. Keep WhatsApp as a separate citizen channel.

## Legend
- 🔴 Not started  | 🟡 In progress  | 🟢 Complete  | ⏸️ Blocked

---

## 1) Workspace Shell
1. Header minimalization (brand, env badge, theme toggle, account) — 🔴
2. Remove "Suggested" chips and quick-action grid from web UI — 🔴
3. Add Omnibox (single input, supports `/` commands, Cmd/Ctrl+K) — 🔴
4. Keep concise trust banner (single line) above conversation — 🔴
5. Ensure responsive layout (evidence rail collapses <1024px) — 🔴

## 2) Conversation & Answer Card
1. Streamed answer rendering with TL;DR + key points — 🔴
2. Confidence band + "based on N sources" indicator — 🔴
3. Copy/share controls; feedback (👍/👎); "Explain in Shona" — 🔴
4. Less-ink answer card styles (no heavy borders, subtle dividers) — 🔴

## 3) Evidence Rail (Right)
1. Numbered citation list with hover preview (title/section/year) — 🔴
2. Open source action (new tab) — 🔴
3. Truncate long titles with tooltip — 🔴

## 4) Basic Document Q&A
1. Upload affordance near composer (PDF/DOCX) — 🔴
2. Ingest skeleton (parse → chunk → ready) — 🔴
3. Allow questions scoped to uploaded file; cite doc + statutes — 🔴

## 5) Accessibility & Internationalization
1. EN/Shona toggle in header; per-message translation action — 🔴
2. Keyboard support (Enter send, Shift+Enter newline, Cmd/Ctrl+K omnibox) — 🔴
3. AA contrast; focus rings; ARIA landmarks — 🔴

## 6) Performance & Telemetry
1. Stream tokens with minimal layout shifts — 🔴
2. Log TTFT, feedback events, citation clicks — 🔴
3. Cache last sources for quick hover previews — 🔴

## 7) Cleanup & Removal
1. Remove suggestion pills and extra quick-actions from `web/index.html` — 🔴
2. Prune unused CSS for chips/grids; keep tokens and essentials — 🔴

---

## Deliverables
- Updated `web/index.html` implementing the above.
- Any supporting JS/CSS for omnibox and evidence rail.
- No server changes required beyond existing RAG endpoints.

## Acceptance Criteria
- Users can ask via Omnibox and receive streamed answers with ≥2 sources.
- Evidence rail shows numbered sources with working links and previews.
- Doc Q&A: user uploads a file and asks at least one scoped question; response cites doc and statute.
- No "Suggested" chips present. Layout is clean, minimal, accessible.

## Out of Scope (MVP)
- Library, Matters/Projects, Admin/Billing, rich document viewer/annotation, agentic tools.

---

## Implementation Notes
- Keep DOM shallow; use CSS variables; avoid heavy bespoke components.
- Ensure mobile: collapse evidence rail; omnibox remains accessible.
- Reuse existing API `/api/v1/query`; add upload handler later if needed.
