# 📋 Pipeline Logs, Monitoring & Data Management Guide

## Overview

This document describes the new comprehensive logging, monitoring, and data management features added to knowledgeVault-YT. These features provide **real-time visibility** into pipeline operations and enable **granular control** over data management.

---

## 🎯 Key Features

### 1. **Real-Time Logging System** (3-Tier Architecture)

#### Tier 1: Application Logs (File-Based)
- **Location:** `data/kvault.log`
- **Format:** Rotating file handler (5MB per file, 3 backups)
- **Content:** All DEBUG+ messages from all modules
- **Access:** View with `tail -f data/kvault.log`

#### Tier 2: Activity Database (SQLite)
- **Table:** `pipeline_logs`
- **Retention:** Configurable (default 30 days)
- **Features:** 
  - Filterable by scan_id, video_id, channel_id, level, stage
  - Full-text search on messages
  - Error detail tracking with stack traces

#### Tier 3: UI Logs & Activity Monitor
- **Page:** 📋 Logs & Activity Monitor
- **Features:**
  - Live activity feed with real-time updates
  - Log filtering by level, scan, stage
  - Per-video timeline visualization
  - Error analysis and pattern detection
  - CSV/JSON export for analysis

### 2. **Log Levels & Event Types**

```
 SUCCESS  - Major milestones (video accepted, stage complete)
ℹ️  INFO     - General operations (discovery, triage start)
️  WARNING  - Non-critical issues (missing transcript, slow processing)
 ERROR    - Pipeline failures that need attention
🐛 DEBUG    - Detailed diagnostic info (SQL queries, timing)
```

### 3. **Pipeline Stages**

Each log entry tracks which pipeline stage generated it:

```
DISCOVERY       - Video discovery phase
TRIAGE          - Triage classification decision
TRANSCRIPT      - Transcript fetching
REFINEMENT      - Sponsor segment removal
NORMALIZATION   - Text normalization via LLM
CHUNKING        - Transcript segmentation
ANALYSIS        - Chunk analysis (topics, entities, claims)
EMBEDDING       - Vector embedding and ChromaDB indexing
GRAPH_SYNC      - Neo4j knowledge graph sync
DATA_MANAGEMENT - Deletion and data maintenance ops
```

---

## 🎮 Pipeline Control Features

### Pause a Scan
```python
# Via UI: 📊 Pipeline Monitor → Select Scan → ⏸️ Pause
db.pause_scan(scan_id, reason="Need to stop for investigation")
```
- Pipeline respects pause state at each video boundary
- No partial shutdowns (safe state guaranteed)
- Can be paused indefinitely
- Log captured: INFO level, GENERAL stage

### Resume a Paused Scan
```python
#Via UI: 📊 Pipeline Monitor → Resume Button
db.resume_scan(scan_id)
```
- Resumes from last processing batch
- Updates control state and timestamps
- Resumption logged with timestamp

### Stop a Scan
```python
# Via UI: 📊 Pipeline Monitor →  Stop
db.stop_scan(scan_id)
```
- Graceful shutdown at next safe point
- Scan marked as "STOPPED"
- Can resume processing all unfinished videos later
- Different from PAUSED (indicates permanent intent)

---

## 📹 Video Discovery Queue Management

### Remove Video from Processing Queue

**When to use:** Before video enters ACCEPTED state

```python
# Via UI: 🎮 Pipeline Control → Video Queue → Remove
success = db.remove_video_from_queue(video_id)
```

**What happens:**
- Video status changes from DISCOVERED → SKIPPED
- Video is NOT re-scanned in subsequent harvests
- Can still manually re-add if needed
- Logged as INFO level event

**Important:** Only works on DISCOVERED videos (before triage). Once ACCEPTED, use deletion instead.

---

## 🗑️ Data Deletion & Management

### Understanding Deletion Behavior

#### What Gets Deleted

```
️  Transcript Chunks    - All segmented text data
💭 Claims             - Extracted claims/assertions  
💬 Quotes             - Notable quotations
👤 Guest Appearances  - Links to identified people
📄 Temp State         - Processing scratch data
📊 Video Summary      - Cached summaries
 Video Status       - Reset to DISCOVERED
```

#### What Does NOT Get Deleted (BUT causes issues!)

```
🚫 ChromaDB Embeddings  - Vector embeddings remain
🚫 Neo4j Nodes         - Graph nodes remain
🚫 File Logs           - Historical logs remain
```

**Important:** After deletion, if you reprocess the same video, you'll get **duplicate embeddings and graph nodes**. Consider manual cleanup.

### Delete Single Video Data

```python
# Via UI: 🗑️ Data Management → Delete Single Video
result = db.delete_video_data(
    video_id="dQw4w9WgXcQ",
    reason="Data corruption in segment 5"
)

# Result includes:
{
    "chunks_deleted": 42,
    "guests_removed": 3,
    "appearances_removed": 5,
    "claims_deleted": 12,
    "quotes_deleted": 8,
    "video_deleted": True,
}
```

**After deletion:**
- Video goes back to DISCOVERED state
- CAN be reprocessed (will scan same URL again)
- New data will be generated
- Old vector/graph data will coexist with new

### Delete All Videos from Channel

```python
# Via UI: 🗑️ Data Management → Delete Channel
result = db.delete_channel_data(
    channel_id="UCxxxxx",
    reason="Channel cleanup"
)

# Result includes:
{
    "videos_deleted": 147,
    "chunks_deleted": 5421,
    "guests_removed": 89,
    "channel_reset": True,
}
```

**After deletion:**
- All videos in channel reset to DISCOVERED
- Channel stats reset (0 processed videos)
- Can re-harvest to rebuild data
- Previous data remains in vector/graph stores

### Deletion History Tracking

```python
# All deletions are logged
history = db.get_deletion_history(limit=50)

# Each entry includes:
{
    "deleted_at": "2025-04-04T14:23:15",
    "deletion_type": "video|channel",
    "target": "video_id or channel_id",
    "reason": "User provided reason",
    "data_deleted": {...stats...}  # JSON with counts
}

# Access via UI: 🗑️ Data Management → Deletion History
```

---

## 💾 Reprocessing After Deletion

### Scenario 1: Deleted a Single Video

```
Before:  VideoID "ABC" in database, fully processed, chunks indexed
Action:  Delete video data
After:   VideoID "ABC" still exists, reset to DISCOVERED state

Reprocess:
1. Run harvest with same URL
2. System detects existing VideoID, skips re-discovery
3. Processes from checkpoint stage onward
4. NEW chunks/embeddings created
5. OLD embeddings still exist → duplicates!
```

**Recommendation:** If reprocessing, manually clean ChromaDB:
```python
# Future cleanup feature
# python -m src.storage.cleanup --mode deduplicate
```

### Scenario 2: Want to Re-scan Same Channel

```
Before:  Channel with 100 videos, fully processed
Action:  Delete all channel data
After:   Channel metadata unchanged, all videos reset to DISCOVERED

Reprocess:
1. Run harvest on same channel
2. System finds existing VideoIDs
3. Skips re-discovery, goes straight to processing
4. Same issue: new + old embeddings coexist
```

**Recommendation:** Delete from vector/graph stores before re-harvesting.

### Scenario 3: Delete Data to Free Space, Plan to Reprocess Later

```
Action:  Delete 50 videos to free space (but may process again later)
Implication:  Videos stay in system, just lose downloaded data
Result:       Can reprocess anytime - data is regenerable

Gotcha:  Vector/graph duplicates on reprocess
Solution: Archive old embeddings in chromadb before reprocessing
```

---

## 📊 Logs & Activity Monitor UI

### Real-Time Activity Feed
- **Updates automatically** as pipeline runs
- **Filter by:** Scan ID, Log Level, Time Range
- **Search:** Full-text search on messages
- **Export:** CSV/JSON for analysis

### Per-Video Timeline
- **Visual timeline** of all events for a video
- **Stage transitions** clearly marked
- **Error highlighting** with full details
- **Context snippets** from log messages

### Error Analysis
- **Pattern detection** - groups similar errors
- **Error frequency** - which errors occur most
- **Affected videos** - which videos hit each error
- **Troubleshooting suggestions** based on error type

### Log Cleanup
```python
# Keep logs for 30 days only (configurable)
db.clear_logs(older_than_days=30)
# Returns: count of deleted logs
```

---

## 🎮 Pipeline Control UI

### Active Scans Dashboard
- **Progress visualization** for each running scan
- **Control buttons** for pause/resume/stop
- **Video list** for each scan
- **Status indicators** (RUNNING/PAUSED/STOPPED)

### Video Queue Management
- **View all** videos awaiting processing
- **Remove individually** before processing starts
- **Batch operations** (planned)

### Processing Status by Stage
- **Bar chart** of videos at each pipeline stage
- **Detailed counts** for troubleshooting
- **Progress tracking** toward completion

### Triage Summary
- **Acceptance rate** - percent of videos accepted
- **Rejection reasons** - why videos were rejected
- **Pending reviews** - videos awaiting manual decision

---

## 🗑️ Data Management UI

### Delete Single Video
1. **Select video** from dropdown
2. **Preview:** What will be deleted
3. **Confirm:** Enter delete reason
4. **Execute:** Single click deletion

**UI Shows:**
- Video metadata
- Count of chunks/claims/quotes to delete
- Warning about vector/graph duplicates
- Cascade impact summary

### Delete Channel
1. **Select channel** from dropdown
2. **Confirmation:** Shows count of videos affected
3. **Reason:** Required for audit trail
4. **Execute:** Confirms before proceeding

**UI Shows:**
- Total videos in channel
- Breakdown of data to delete
- Storage impact estimate

### Deletion History
- **Audit trail** of all deletions
- **Timestamps** for forensics
- **Reasons** provided by user
- **Data deleted count** for each operation

### Storage Optimization Tips
- **Cleanup recommendations** - what to delete first
- **Storage estimates** - current database size
- **Optimization guide** - how to reduce footprint

---

## 📡 Logging API Reference

### Log a Pipeline Event

```python
db.log_pipeline_event(
    level="INFO",              # SUCCESS, INFO, WARNING, ERROR, DEBUG
    message="Processing started",
    scan_id="abc12345",        # Optional
    video_id="dQw4w9WgXcQ",    # Optional
    channel_id="UCxxxxx",      # Optional
    stage="TRIAGE",            # Pipeline stage
    error_detail="",           # Full traceback if ERROR
)
```

### Fetch Logs

```python
logs = db.get_logs(
    scan_id="abc12345",        # Filter by scan
    video_id="dQw4w9WgXcQ",    # Filter by video
    level="ERROR",             # Filter by level
    limit=100,                 # Max results
    order="DESC"               # DESC or ASC
)

# Returns list[PipelineLog]
for log in logs:
    print(f"{log.timestamp} | {log.level} | {log.message}")
```

### Get Summary

```python
summary = db.get_log_summary(scan_id="abc12345")
# Returns: {"INFO": 45, "SUCCESS": 12, "WARNING": 3, "ERROR": 0}
```

---

## 🛠️ Troubleshooting

### Pipeline Keeps Pausing
**Check:** `logs_monitor.py` → Error Analysis
- Look for patterns
- Check timestamp of pause events
- Review pause reason in control state

### Data Deletion Failed
**Check:**
1. Video exists: `db.get_video(video_id)`
2. No foreign key issues: Review error detail
3. Database lock: Wait and retry

### Can't Find Video in Dropdown
**Possible causes:**
1. Video already DONE - it's completed
2. Video REJECTED - use different filter
3. Video deleted - check deletion history

### Reprocessing Created Duplicates
**Expected behavior** - embeddings/graph duplicates exist
**Solution (TODO):**
1. Export deletion manifest
2. Delete from chromadb/neo4j by manifest
3. Re-harvest
4. New embeddings won't duplicate

---

## 🔒 Data Persistence After Deletion

### What Persists

```
 PERSISTS:
- Video ID record (reset to DISCOVERED)
- Channel metadata
- All file logs
- Deletion history
- ChromaDB embeddings (DUPLICATE on reprocess)
- Neo4j graph nodes (DUPLICATE on reprocess)

 DELETED:
- Transcript chunks
- Claims and quotes
- Guest appearances
- Video summaries
- Temp processing state
```

### Reprocessability Matrix

| Action | Video Reprocessable? | Data Regenerable? | Duplicates? |
|--------|----------------------|-------------------|------------|
| Delete video data | Yes | Yes | Yes* |
| Delete channel data | Yes | Yes | Yes* |
| Delete after DONE | Yes | Yes | Yes* |
| Delete DISCOVERED video | Yes (skipped) | Yes | No** |

*Embeddings/graph nodes remain from before deletion
**Skipped videos won't be re-discovered

---

## 📋 Quick Reference

### Common Tasks

**I want to pause a harvest temporarily:**
→ 📊 Pipeline Monitor → ⏸️ Pause Scan

**I want to stop a harvest and resume later:**
→ 📊 Pipeline Monitor → ⏸️ Pause → Later → ▶️ Resume

**I want to stop a harvest permanently:**
→ 📊 Pipeline Monitor →  Stop

**I want to remove a video before processing:**
→ 🎮 Pipeline Control → Remove from Queue

**I want to delete a video's data:**
→ 🗑️ Data Management → Delete Single Video

**I want to clear an entire channel:**
→ 🗑️ Data Management → Delete Channel

**I want to see what went wrong:**
→ 📋 Logs & Activity → Error Analysis

**I want to export logs for analysis:**
→ 📋 Logs & Activity → Export (CSV/JSON)

---

## 🚀 Integration Examples

### Custom Pipeline Monitoring

```python
from src.storage.sqlite_store import SQLiteStore

db = SQLiteStore("data/kvault.db")

# Get all errors from last 10 minutes
import datetime
recent_errors = db.get_logs(
    level="ERROR",
    limit=1000
)
recent_errors = [l for l in recent_errors 
                 if datetime.datetime.fromisoformat(l.timestamp) 
                 > datetime.datetime.now() - datetime.timedelta(minutes=10)]

# Send alert if too many errors
if len(recent_errors) > 5:
    send_slack_alert(f"️ {len(recent_errors)} errors in last 10 min")
```

### Automated Cleanup

```python
# Delete videos not accessed in 6 months
import datetime

videos = db.get_videos_by_status("DONE", limit=10000)
old_videos = [v for v in videos 
              if datetime.datetime.fromisoformat(v.created_at) 
              < datetime.datetime.now() - datetime.timedelta(days=180)]

for video in old_videos:
    db.delete_video_data(video.video_id, reason="Auto-cleanup: 6mo old")
    print(f"Deleted: {video.title}")
```

---

## 📞 Support

For issues or questions:
1. Check **Logs & Activity Monitor** for error details
2. Review **Error Analysis** section for patterns
3. Check **deletion history** if data-related
4. See **Troubleshooting** section above
5. Review **logs/kvault.log** for full details

---

Last Updated: 2025-04-04
