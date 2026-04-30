# Operations, Telemetry & Data Lifecycle Guide

## Overview
This document provides technical details on the KnowledgeVault-YT operational suite, including the 3-tier telemetry system, cross-store health monitoring, and the automated data lifecycle (Recycle Bin & Purge).

---

## 🎯 1. The Operations Suite

The **Operations Dashboard** serves as the mission control for the intelligence fleet.

### Orchestration Control
- **Unified Intake**: Integrated command bar for background harvests and bulk processing.
- **Background Tasks**: Non-blocking pipeline execution with persistent status tracking.
- **Repair Utilities**: One-click recovery tools for stalled scans or database locks.

### Fleet Monitor (Live Telemetry)
- **Active Trace**: Real-time progress visualization for every video in the current harvest cycle.
- **Pipeline Stage Tracking**: Drill-down into specific stages (Triage, Analysis, Graph Sync) for any active asset.
- **Live Monitor**: Auto-refreshing dashboard that updates every 10 seconds during active operations.

### Vault Health Monitor
A specialized utility to verify consistency across the triple-store architecture:
- **Consistency Scores**: Percentage of videos with matching records in SQL, Vector, and Graph stores.
- **Automated Repair**: A background process that identifies missing chunks, embeddings, or graph nodes and re-syncs them without re-harvesting.
- **Integrity Checks**: Verifies transcript reachability and summary validity.

---

## 🎯 2. Data Lifecycle & Sovereignty

KnowledgeVault-YT implements a safe, atomic data lifecycle to prevent accidental intelligence loss.

### The Recycle Bin (Soft-Delete)
When a video is "deleted," it is moved to the **Recycle Bin** rather than being purged immediately.
- **Database Flag**: `is_deleted = 1` in the `videos` table.
- **Recovery**: One-click restoration from the Settings page.
- **Undo Action Bar**: Immediate "Undo" toast and action bar appear after any deletion event.

### Permanent Purge
A "Purge" operation is required to permanently remove intelligence from all stores:
- **Relational Cleanup**: Deletes metadata and pipeline logs.
- **Content Cleanup**: Deletes transcript chunks, claims, and summaries.
- **History Record**: A non-video-specific record is kept in the `deletion_history` for audit purposes.

---

## 🎯 3. System Telemetry (3-Tier Logging)

1. **Bare-Mode Logs (`kvault.log`)**: Rotating text logs for deep backend diagnostics.
2. **Relational Trace (`pipeline_logs`)**: Structured SQL table for filtering logs by Scan ID or Video ID.
3. **Live Telemetry UI**: A real-time streaming feed in the Operations Dashboard with localized error boundaries.

---

## 🎯 4. Vault Snapshots (.kvvault)

The **Export Center** provides total data portability:
- **Bundled Archive**: Contains a SQLite backup, chat mission briefings, and a system manifest.
- **Independent Recovery**: Snapshots are designed to be imported into a fresh KnowledgeVault instance.
- **Obsidian Sync**: Exports processed intelligence as a structured Markdown vault.

---

## 📋 Operational Quick Reference

| Task | Location | Recommended Frequency |
| :--- | :--- | :--- |
| **Start Harvest** | Intelligence Center | As needed |
| **Monitor Fleet** | Operations Dashboard | During active scans |
| **Repair Vault Health**| Operations Dashboard | When consistency < 100% |
| **Generate Snapshot** | Export Center | Monthly |
| **Clear Recycle Bin** | Settings | Monthly |
