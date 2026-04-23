# KnowledgeVault-YT: User Guide (v1.1)

Welcome to KnowledgeVault-YT, a professional-grade research intelligence system. This guide provides comprehensive instructions for navigating the unified hub architecture and utilizing advanced research features.

---

## ✦ 1. Guided Onboarding
On your first run with an empty vault, KnowledgeVault will present an **Onboarding Modal**. This 5-step guide introduces the core research lifecycle:
1. **Harvest**: Ingesting raw video content.
2. **Triage**: Filtering for high-fidelity knowledge.
3. **Synthesis**: Discovering thematic bridges.
4. **Execution**: Utilizing procedural blueprints.

---

## ✦ 2. The Intelligence Hubs

The platform is organized into functional "Hubs" accessible via the sidebar:

### Intelligence Center
The primary research interface.
- **Hybrid Search**: Enter natural language questions or paste a YouTube URL to harvest.
- **Saved Discoveries**: Bookmark critical insights directly to your dashboard.
- **Pinned Queries**: Pin frequent search terms for one-click discovery.

### Ingestion Hub
Manage the intake of raw content.
- **New Harvest**: Robust parsing of channels, playlists, and individual videos.
- **Triage Queue**: Manually approve or reject videos that fall below the automatic confidence threshold.
- **Rejection Audit**: Review previously rejected content to ensure no signal was lost.

### Operations Dashboard
The mission control for your intelligence fleet.
- **Orchestration Control**: Background job management and pipeline health.
- **Fleet Monitor**: Real-time trace of active harvest operations.
- **Vault Health**: Cross-store verification (SQL vs Vector vs Graph).
- **Live Logs**: Streaming telemetry for system troubleshooting.

### Execution OS (Blueprint Center)
Actionable procedural knowledge extracted from tutorials.
- **Rich Blueprints**: Step-by-step guides with timestamps and descriptions.
- **Progress Tracking**: Mark steps as completed to monitor mastery.

---

## ✦ 3. Advanced Features

### Atmosphere Control
Switch between **Nebula Dark** and **Stellar Light** themes using the sidebar toggle. The entire design system (glass cards, metrics, charts) adapts for optimal focus in any lighting condition.

### Vault Maintenance
Located in the **Settings** and **Export Center**:
- **Recycle Bin**: Soft-deleted videos can be recovered or permanently purged.
- **Vault Snapshots**: Create portable `.kvvault` packages for archival or transfer.
- **Mission Packages**: Sync research sessions with other investigators.

---

## ✦ 4. Troubleshooting
- **Missing Results?** Ensure Ollama is running with `llama3.2` and `nomic-embed-text`.
- **Pipeline Stalling?** Check the **Live Logs** in the Operations Dashboard for network or resource errors.
- **UI Inconsistency?** Use the **Vault Health** tool in the Operations Dashboard to repair cross-store discrepancies.
