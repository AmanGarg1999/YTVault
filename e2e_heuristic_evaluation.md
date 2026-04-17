# E2E Heuristic Evaluation: KnowledgeVault-YT
**Date**: April 14, 2026 (Session 2 — Deep Audit)  
**Evaluator**: Antigravity (AI Architect — Claude Opus 4.6)  
**Build**: v1.1 (Architecture Overhaul)  
**Pages Tested**: 15/15 (100% Coverage)  
**Test Methodology**: Source-code analysis + Live browser interaction + Edge-case injection

---

## Executive Summary

KnowledgeVault-YT has matured into a visually striking research platform built on a cohesive **Nebula-Glassmorphism** design system. The vault contains **21 channels**, **10,698 videos**, and **7,938 indexed assets**. However, the application **still fails to survive multiple unhappy paths**, with a **P0 crash on the Settings page** and critical UI regressions including **invisible navigation buttons** and **raw JSON data leaks** in the Intelligence Lab. While previous iterations fixed the global search crash, new regressions have been introduced in the dataframe API usage. The application's functional depth is impressive, but it is not production-ready.

**Overall Verdict: C+ (Stabilization Required — Near Phase Gate)**

---

## 1. The Friction Log

*A minute-by-minute walkthrough of every pain point encountered during a full simulated user lifecycle.*

### Phase 1: First Impressions & Navigation

| # | Action | Observation | Severity |
|:--|:-------|:------------|:---------|
| 1 | **Load Dashboard** | Page loads in ~2s. Nebula-Glassmorphism renders correctly. Radial health chart (75%) displays cleanly. Metric cards show real data (21 channels, 10698 videos, 7938 indexed). | ✅ PASS |
| 2 | **Check sidebar branding** | "KnowledgeVault / Research Intelligence OS" branding box renders with gradient and proper typography. DB=green, LLM=yellow (degraded), VEC=green. | ✅ PASS |
| 3 | **Inspect "Dashboard" nav button** | The **first nav item under "Intelligence Hub" is completely invisible** — it renders as a blank/empty button with no text. This is the "Dashboard" button in its `primary` (active) state. The text "Dashboard" is invisible because the `primary` button style uses white text on a white-ish gradient that loses contrast in the light sidebar context. | **CRITICAL** |
| 4 | **Check Harvest button** | The "Harvest" button in the global command bar **has invisible text** — same white-on-white rendering issue. The button shape is visible but the word "Harvest" is not. | **CRITICAL** |
| 5 | **Scroll Dashboard** | "High-Density Intel" leaderboard renders. Video card shows "0% CONFIDENCE" — this is because `triage_confidence` is 0.0 for `PENDING_REVIEW` videos, which is technically correct but confusing for the user (looks like a bug). | **MEDIUM** |
| 6 | **Check Vault Health card** | The rightmost metric card ("Vault Health") overflows — the text "Ready for Search" is truncated/clipped with "Re..." and "Se..." visible. The `75%` radial chart itself renders correctly. | **MEDIUM** |

### Phase 2: Search & Discovery

| # | Action | Observation | Severity |
|:--|:-------|:------------|:---------|
| 7 | **Navigate to Global Search** | The "Global Search" nav button, when **inactive**, also appears invisible (blank button). When active (red highlight), the text appears. This is the same root cause as finding #3. | **CRITICAL** |
| 8 | **XSS Test: `<script>alert(1)</script>`** | **Handled gracefully.** Returns "No Intelligence Found" with a helpful message. No crash, no script execution. FTS5 sanitization is working. | ✅ PASS |
| 9 | **Whitespace-only search: `"   "`** | Returns a **blank page with no feedback**. The `query.strip()` check exists but fires a `st.toast()` and `return`, which silently clears the content area without any persistent visible message. User sees an empty screen with the search input bordered red. | **MEDIUM** |
| 10 | **Valid search: "artificial intelligence"** | Search results load with spinner and toast. Results display with proper RRF scores, icons, and "Drill Down" buttons. Hybrid ranking (keyword + semantic) is functional. | ✅ PASS |

### Phase 3: Intelligence Lab Deep Dive

| # | Action | Observation | Severity |
|:--|:-------|:------------|:---------|
| 11 | **Open Intelligence Lab** | The "Intelligence Lab" nav button text is **invisible when inactive** (same ghost button issue). Page loads successfully with 5 tabs. | **CRITICAL** |
| 12 | **Knowledge Mind-Map tab** | Graph visualization loads with slider. Nodes render in Nebula Indigo. Physics simulation works. | ✅ PASS |
| 13 | **Expert Network tab** | Graph renders with data. **Major visual issue: overlapping labels.** Edge labels like "AutonBaLeadershiplandtAdaptabilityesnerce" are corrupted/concatenated nonsense strings. Node labels are also overlapping heavily. This is a data quality issue from the guest/topic extraction pipeline. | **HIGH** |
| 14 | **Thematic Bridges tab** | **CRITICAL: Raw JSON leak.** The bridge cards render `{"name":"The State of Humanity","relevance":0.8,"description":"The speaker believes that..." ...}` as raw JSON text instead of parsing the topic_a and topic_b fields. The `bridge.topic_a` and `bridge.topic_b` columns contain serialized JSON objects, not plain strings. | **CRITICAL** |
| 15 | **Market Trends tab** | Renders line chart successfully when data is available. | ✅ PASS |

### Phase 4: Settings / Data Management

| # | Action | Observation | Severity |
|:--|:-------|:------------|:---------|
| 16 | **Navigate to Settings** | Page loads the header ("Data Management Center") and the "Intelligence Source Explorer" section. Then **crashes with a red error**: `Failed to load Data Management: Invalid selection mode: single_row. Valid options are: {'single-row-required', 'multi-column', 'multi-row', 'single-column', 'single-row', 'multi-cell', 'single-cell'}` | **P0 CRITICAL** |
| 17 | **Root Cause** | `data_management.py:80` passes `selection_mode="single_row"` (underscore). The Streamlit API changed and now requires `selection_mode="single-row"` (hyphen). | **FIX REQUIRED** |

### Phase 5: Review Center & Pipeline

| # | Action | Observation | Severity |
|:--|:-------|:------------|:---------|
| 18 | **Open Review Center** | Page loads. Shows "50 Intelligence Targets Awaiting Triage" with video cards. Accept/Reject buttons are visible. However, the "Accept" button text is **invisible** (same white-on-white issue). | **CRITICAL** |
| 19 | **Rejected tab - missing `</div>` closure** | In `reject_review.py:90-94`, the `<div class="danger-btn">` wrapper is opened but the corresponding `st.markdown('</div>')` is at line 94, which is **inside** the `if st.button("Purge Intel")` block — meaning it only renders the closing tag if the button is clicked. This causes DOM corruption on every render. | **HIGH** |
| 20 | **Pipeline Center** | Loads successfully. Shows active scans with progress bars. "Global Process Control" has "Resume All Scans" and "Halt Operations" buttons. However, the error handler at line 80 references `failure_confirmation_dialog` which is **not imported** — it would crash on any error. | **HIGH** |

### Phase 6: Remaining Pages

| # | Action | Observation | Severity |
|:--|:-------|:------------|:---------|
| 21 | **Monitoring Hub** | Loads successfully. System Health, Queue Manager, Pipeline Logs, and Followed Channels tabs all render data. | ✅ PASS |
| 22 | **Performance Metrics** | Loads successfully. Shows scan performance data with charts and stage breakdowns. | ✅ PASS |
| 23 | **Transcript Viewer** | Video card grid renders with search. Button text ("VIEW TRANSCRIPT") is visible because it uses Streamlit `type="primary"`. Channel IDs shown as raw `UCKnapqRNHs7HbhJoyDY...` instead of channel names. | **MEDIUM** |
| 24 | **Export Center** | Loads successfully. Bulk export, mission briefings, and Obsidian sync all render. | ✅ PASS |
| 25 | **Research Chat** | Loads correctly. Chat input and session management functional. | ✅ PASS |
| 26 | **Blueprint Center** | Loads. Shows extracted checklists from tutorials. "Watch Video" links are correctly generated. | ✅ PASS |
| 27 | **Comparative Lab** | Loads. Channel selection and topic input work. Analysis button is properly disabled until inputs are provided. | ✅ PASS |
| 28 | **Research Agent** | Loads. "Launch Investigation" button is correctly disabled until query is entered. Previous reports are displayed. | ✅ PASS |
| 29 | **Ingestion Hub** | Loads with Quick Harvest and Bulk Operations tabs. URL validation working. | ✅ PASS |

---

## 2. Technical Debt Audit

### **P0 — System Blockers (Crashes/Data Loss)**

| ID | File | Issue | Fix |
|:---|:-----|:------|:----|
| **TD-001** | [data_management.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/views/data_management.py#L80) | `selection_mode="single_row"` uses underscore instead of hyphen. Crashes the entire Settings page. | Change to `"single-row"` |
| **TD-002** | [pipeline_center.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/views/pipeline_center.py#L80) | `failure_confirmation_dialog` is used in the error handler but **not imported**. Any exception will cause a `NameError` instead of graceful recovery. | Add to imports |

### **P1 — Visual Regressions (User-Facing)**

| ID | File | Issue | Fix |
|:---|:-----|:------|:----|
| **TD-003** | [app.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/app.py#L190-L211) | **Ghost Buttons**: Primary buttons (active nav) in the light-theme sidebar render white text on a light gradient → invisible text. Affects Dashboard, Global Search, all active nav buttons, and the "Harvest" button. | Add `color: #ffffff !important; text-shadow: 0 1px 2px rgba(0,0,0,0.3)` or use a darker background for buttons in the sidebar context |
| **TD-004** | [intelligence_lab.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/views/intelligence_lab.py#L290-L296) | **Raw JSON Leak** in Thematic Bridges: `bridge.topic_a` and `bridge.topic_b` contain serialized JSON objects, not plain strings. Renders raw `{"name":"...","relevance":0.8,...}` text in the UI. | Parse JSON before rendering: `json.loads(bridge.topic_a)["name"]` |
| **TD-005** | [reject_review.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/views/reject_review.py#L90-L94) | **DOM Corruption**: `<div class="danger-btn">` opened on line 90, but `</div>` closing tag is only rendered inside the `if st.button(...)` block on line 94 — executes only on button click, not on every render. This creates an unclosed DOM element. | Move the closing `</div>` outside the button `if` block |
| **TD-006** | [app.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/app.py#L389-L390) | `header {display: none !important;}` hides Streamlit's native header. This is intentional for aesthetics but **eliminates the Streamlit deploy button, hamburger menu, and "Running/Rerun" indicators**. Users lose "Visibility of System Status" (Nielsen #1). | Consider keeping the header and restyling it, or add a custom status indicator |

### **P2 — Design Inconsistencies**

| ID | Location | Issue |
|:---|:---------|:------|
| **TD-007** | Dashboard → metric grid | The 4th metric card ("Vault Health") overflows. The label and description text ("Ready for Search") are clipped with "Re..." / "Se..." visible. Needs `min-width` or responsive layout fix. |
| **TD-008** | Dashboard → leaderboard | Videos show "0% CONFIDENCE" badge in cyan — looks like a system error to users. Should display "Pending" or "Unscored" for `triage_confidence == 0`. |
| **TD-009** | Transcript Viewer → video cards | Channel IDs shown as raw technical IDs (`UCKnapqRNHs7HbhJoyDY...`) instead of human-readable channel names. |
| **TD-010** | Intelligence Lab → Expert Network | Node labels severely overlap. Edge labels contain corrupted concatenated text ("AutonBaLeadershiplandtAdaptabilityesnerce"). Data quality issue from NER/topic extraction. |
| **TD-011** | Thematic Bridges tab | "Probe Neural Bridges" button text is invisible (same ghost button pattern as TD-003). |
| **TD-012** | Global Search | Whitespace-only queries show a blank page with no persistent error — only a transient toast. Should show a persistent `info_card`. |
| **TD-013** | CSS → Scrollbar | Custom scrollbar styling hardcodes dark colors (`#020617`, `#1e293b`) that don't respect the light theme toggle. |
| **TD-014** | CSS → Glass card hover | `.metric-card:hover` hardcodes `background: rgba(30, 41, 59, 0.6)` — doesn't adapt to light theme. |

### **P3 — Architectural Concerns**

| ID | Location | Issue |
|:---|:---------|:------|
| **TD-015** | [app.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/app.py#L59-L78) | CSS custom properties use Python f-string interpolation inside `<style>` blocks for theming. This re-renders the entire CSS on every theme toggle. Consider using CSS `data-theme` attributes. |
| **TD-016** | [app.py](file:///home/huntingvision/Desktop/knowledgeVault-YT/src/ui/app.py#L571) | Global module-level patching: `st._global_orchestrators = {}` patches the Streamlit module object directly. This is fragile and may break across Streamlit versions. |
| **TD-017** | UI helpers `glass_card` | The `glass_card()` context manager renders `<div>` open/close tags via `st.markdown()`. Streamlit renders all elements sequentially — the `<div>` tags are **not** actually wrapping the inner content in the DOM. This is a known Streamlit limitation; the visual effect works only coincidentally. |
| **TD-018** | Research Chat | `VectorStore()` is instantiated fresh on every page render (line 21 of `research_chat.py`). Should reuse the cached `vs` instance from `app.py`. |

---

## 3. Nielsen's 10 Heuristics Assessment

| Heuristic | Score | Evidence |
|:----------|:------|:---------|
| **1. Visibility of System Status** | 6/10 | Spinners and toasts exist for harvests and searches. Active scan progress bars in sidebar. However, the native Streamlit header is hidden (no "Running" indicator). Background thread status is not pushed to the UI in real-time. |
| **2. Match Between System & Real World** | 7/10 | Terminology like "Harvest", "Intelligence Lab", "Neural Bridges" is evocative but may confuse non-power users. "Triage" is accurate. "Nebula" / "Stellar Lab" theme names are whimsical. |
| **3. User Control & Freedom** | 7/10 | Back buttons exist in Transcript Viewer and cluster details. "Clear Selection" in Intelligence Lab. Undo is not available for Accept/Reject actions. |
| **4. Consistency & Standards** | 5/10 | Major inconsistency: nav buttons swap between visible/invisible based on active state. Some pages use `st.subheader()`, others use custom `section_header()`. Mix of native Streamlit components and custom HTML. |
| **5. Error Prevention** | 7/10 | URL validation exists before harvest. Destructive action dialogs gate deletions. Research Agent button is disabled without input. |
| **6. Recognition vs. Recall** | 6/10 | Navigation is always visible in sidebar. But no breadcrumbs. "Blueprint Center" name doesn't hint at "checklists from tutorials". |
| **7. Flexibility & Efficiency** | 5/10 | Keyboard shortcuts (Alt+1-9) exist but are undiscoverable (no UI hint). No command palette. No bulk accept/reject in Review Center. |
| **8. Aesthetic & Minimal Design** | 7/10 | Glassmorphism is consistently applied. Typography hierarchy is clear. But 15+ nav items in sidebar is overwhelming. Raw JSON leaks and corrupted graph labels detract. |
| **9. Error Recovery** | 4/10 | Settings page crash is unrecoverable without code fix. Pipeline Center's error handler itself crashes (`NameError`). Whitespace search silently fails. |
| **10. Help & Documentation** | 5/10 | Blueprint Center serves as minimal docs. Sidebar footer has "User Documentation" link but it just navigates to Blueprint Center. No contextual help, tooltips are sparse, no onboarding tour. |

---

## 4. Critical Gaps for User Retention

### Gap 1: **Batch Operations in Review Center**
The Review Center currently shows 50 pending items but requires individual Accept/Reject clicks with page reloads for each. A power user ingesting a large channel (880+ videos) cannot efficiently triage at scale. **Required**: "Select All / Accept All / Reject All" with checkbox selection and batch operations.

### Gap 2: **Real-Time Pipeline Observability**
Background threads have no mechanism to push live status updates to the Streamlit frontend. The sidebar "Task Queue Monitor" only updates on manual page reloads. When a user starts a harvest, there is no way to know if it's running, stalled, or completed without navigating to Pipeline Center and refreshing. **Required**: WebSocket-based or polling status updates, notification system for completed/failed harvests.

### Gap 3: **Data Export Integrity & Undo System**
Destructive operations (Video Deletion, Channel Purge, Guest Cleanup) have confirmation dialogs but **no undo capability**. Once purged, data is permanently lost from SQLite. The vector and graph stores may retain orphaned data. **Required**: Soft-delete with configurable retention period (7/30 days), transaction log with rollback capability.

---

## 5. Quality Score (1-10)

| Metric | Score | Justification |
|:-------|:------|:--------------|
| **Discoverability** | **6/10** | Sidebar navigation covers all features, but 15 items without grouping collapse makes it overwhelming. Ghost button regression means users literally cannot read active page names. Blueprint Center is undiscoverable as "docs". |
| **Reliability** | **5/10** | Settings page P0 crash. Pipeline Center error handler crash. Raw JSON leaks in Intelligence Lab. DOM corruption in Review Center. However, search edge cases (XSS, special chars) now survive gracefully — a genuine improvement from previous evaluations. |
| **Delight** | **6/10** | The Nebula-Glassmorphism design system is genuinely beautiful when it works. Glass cards, radial charts, premium typography, and micro-animations create a premium feel. But invisible buttons, clipped text, and JSON leaks immediately destroy the illusion. |

**Overall Grade: C+ (Stabilization Required — Near Phase Gate)**

> The platform has crossed the threshold from "prototype" to "near-production", with a rich feature set spanning ingestion, triage, search, analysis, export, and collaboration. But 3 distinct crash-inducing bugs and 6 visual regressions prevent a passing grade. A focused 48-hour remediation sprint targeting TD-001 through TD-005 would elevate this to a **B+**.

---

## 6. Prioritized Remediation Checklist

```
[P0] TD-001: Fix selection_mode="single_row" → "single-row" in data_management.py
[P0] TD-002: Add failure_confirmation_dialog import to pipeline_center.py
[P1] TD-003: Fix ghost button contrast — ensure button text is visible in both themes
[P1] TD-004: Parse JSON in Thematic Bridges before rendering topic names
[P1] TD-005: Fix unclosed <div class="danger-btn"> in reject_review.py
[P2] TD-006: Restore or replace Streamlit header status indicator
[P2] TD-007: Fix Vault Health card overflow/truncation
[P2] TD-008: Show "Unscored" instead of "0% CONFIDENCE" for triage_confidence == 0
[P2] TD-009: Resolve channel IDs to names in Transcript Viewer
[P2] TD-012: Show persistent error card for whitespace-only search
[P3] TD-010: Improve Expert Network graph label rendering
[P3] TD-013/14: Fix theme-insensitive hardcoded colors in CSS
[P3] TD-018: Reuse cached VectorStore in Research Chat
```

---

## 7. Visual Evidence

![Dashboard showing metric cards, ghost button, and leaderboard](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/dashboard_overview.png)
*Figure 1: Dashboard overview — note the invisible "Dashboard" button in sidebar (ghost button) and clipped "Vault Health" card text.*

![XSS input handled gracefully in Global Search](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/xss_graceful_handling.png)
*Figure 2: XSS input `<script>alert(1)</script>` handled gracefully — returns "No Intelligence Found" without crash.*

![Settings page crash — invalid selection_mode](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/settings_error.png)
*Figure 3: Settings / Data Management crash — `selection_mode="single_row"` API regression.*

![Expert Network graph with corrupted labels](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/expert_network_graph.png)
*Figure 4: Expert Network graph — overlapping/corrupted edge labels indicating NER data quality issues.*

![Raw JSON leak in Thematic Bridges](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/thematic_bridges_raw_json.png)
*Figure 5: Thematic Bridges showing raw JSON serialized objects instead of parsed topic names.*

![Review Center with 50 pending items](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/review_center_pending.png)
*Figure 6: Review Center showing 50 pending triage items — "Accept" button text is invisible (ghost button issue).*

![Whitespace search returns blank page](/home/huntingvision/.gemini/antigravity/brain/f5d9719e-cd64-4de9-b962-1df3b888d714/artifacts/whitespace_search_empty.png)
*Figure 7: Whitespace-only search query returns blank page with no persistent feedback.*

---

*Evaluation compiled from: 636 lines of UI component analysis, 994 lines of app.py routing analysis, 15 browser-automated page traversals, and 7 edge-case injections.*
