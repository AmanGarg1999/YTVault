# 🚀 NEW FEATURES: Logging, Monitoring & Data Management

## What's Been Added? 

You now have a **comprehensive system** for:
1. ✅ **Real-time logging** - See exactly what's happening in your pipeline
2. ✅ **Pipeline control** - Pause, resume, or stop scans at any time
3. ✅ **Video queue management** - Remove videos before processing starts
4. ✅ **Data deletion** - Safely delete video/channel data with full cascade
5. ✅ **Activity monitoring** - Track processing status and errors in real-time
6. ✅ **Deletion history** - Audit trail of all deletions

---

## 🎯 Quick Start (5 Minutes)

### 1. Launch the UI
```bash
cd knowledgeVault-YT
python3 src/main.py ui
```

### 2. Navigate to the New Pages

The sidebar now has **3 new options**:

- **📋 Logs & Activity** - Real-time pipeline events and error tracking
- **🎮 Pipeline Control** - Pause/resume/stop scans and manage video queue  
- **🗑️ Data Management** - Delete data with safety confirmation

### 3. Start a Scan and Watch It Live

```bash
# In another terminal:
python3 src/main.py harvest "https://youtube.com/@channelname"
```

Then in UI:
- Go to **📊 Pipeline Monitor** → See scan starting
- Go to **📋 Logs & Activity** → Watch live events stream in
- Go to **🎮 Pipeline Control** → Control scan execution

### 4. Try Pause/Resume

- **📊 Pipeline Monitor** → Find your scan → **⏸️ Pause**
- Watch the pipeline pause at next safe point
- **▶️ Resume** to continue

---

## 📋 Feature Overview

### Real-Time Logs & Activity Monitor

**What you'll see:**
- ✅ SUCCESS events (videos accepted, stages completed)
- ℹ️ INFO events (processing starts, discoveries)
- ⚠️ WARNING events (slow processing, missing data)
- ❌ ERROR events (failures with full details)
- 🐛 DEBUG events (detailed diagnostic info)

**In the UI:**
```
📋 Logs & Activity page shows:
├─ Live Activity Feed (all events, filterable)
├─ Per-Video Timeline (what happened to each video)
├─ Error Analysis (patterns, frequencies, affected videos)
└─ Export Options (CSV/JSON for external analysis)
```

**Try it:**
1. Go to **📋 Logs & Activity**
2. Filter by "ERROR" to see only failures
3. Expand an error to see full details
4. Export as CSV for spreadsheet analysis

### Pipeline Control Center

**What you can do:**
- Pause any active scan (returns to paused state)
- Resume paused scans (continues from where it left off)
- Stop scans permanently (different from pause)
- Remove videos from processing queue before they're accepted
- See real-time status of all scans

**In the UI:**
```
🎮 Pipeline Control page shows:
├─ Active Scans (progress, status, controls)
├─ Video Queue (awaiting processing)
├─ Processing Status by Stage (bar chart)
├─ Triage Summary (acceptance rates)
└─ Quick Actions (refresh, view other pages)
```

**Try it:**
1. Go to **🎮 Pipeline Control**
2. Start a scan with `kvault harvest [url]` in terminal
3. Watch it appear in "Active Scans"
4. Click **⏸️ Pause** to demonstrate pausing
5. Click **▶️ Resume** to continue

### Data Management Center

**What you can do:**
- Delete a specific video's data (chunks, claims, quotes)
- Delete all videos from a channel at once
- View deletion history and audit trail
- Understand what gets deleted vs what persists
- See storage estimates

**In the UI:**
```
🗑️ Data Management page shows:
├─ Delete Single Video (with preview)
├─ Delete All from Channel (with confirmation)
├─ Deletion History (audit trail)
└─ Storage Optimization Tips
```

**Try it:**
1. Go to **🗑️ Data Management**
2. Select a processed video
3. Click "Preview: What Will Be Deleted"
4. See the breakdown (chunks, claims, quotes, guests)
5. **Don't actually delete** unless you want to - just understand the impact

---

## 🔍 Understanding the Logging System

### 3-Tier Architecture

**Tier 1: File Logs** (`data/kvault.log`)
```
Rotating log file (5MB limit, 3 backups)
Captures: All DEBUG+ messages from all modules
Access: tail -f data/kvault.log
```

**Tier 2: SQLite Database** (`pipeline_logs` table)
```
Structured events with:
- Timestamp
- Level (SUCCESS, INFO, WARNING, ERROR, DEBUG)
- Content (message, error details)
- Context (scan_id, video_id, stage, etc.)
- Indexed for fast filtering
```

**Tier 3: UI Dashboard**
```
Real-time visualization of Tier 2 data:
- Live feed of all events
- Filtering and search
- Error analysis and patterns
- CSV/JSON export
```

### Sample Log Events

```
✅ SUCCESS | 2025-04-04 14:23:45 | TRIAGE
   "Triage: Introduction to Machine Learning → ACCEPTED (98%)"

ℹ️  INFO | 2025-04-04 14:23:12 | DISCOVERY
   "Discovered 42 videos from channel"

❌ ERROR | 2025-04-04 14:22:58 | TRANSCRIPT
   "Transcript fetch failed: Video not available"
   Error Detail: requests.exceptions.ConnectionError: [Errno -2] Name or service not known
```

---

## 🎮 Pipeline Control in Detail

### Pause vs Stop vs Skip

| Operation | Effect | Reversible? | Use Case |
|-----------|--------|------------|----------|
| **Pause** | Pipeline freezes at next safe point | Yes | Investigate, brief break |
| **Resume** | Continue from pause point | Yes | Resume after investigation |
| **Stop** | Graceful shutdown, mark as stopped | Yes | Permanent stop, resume later |
| **Remove from Queue** | Skip video before processing | No | Don't process this video |

### How Pause Works

```
Timeline:
├─ 14:00:00 - Pause requested
├─ 14:00:05 - Video 1 finishes → Pipeline sees pause flag → Stops
├─ 14:00:05 - Status: PAUSED
├─ 14:05:00 - User clicks Resume
├─ 14:05:00 - Pipeline continues from Video 2
└─ 14:00:05 - Status: RUNNING
```

**Important:** Pause happens between videos, NOT mid-video. Always safe.

---

## 🗑️ Data Deletion & Reprocessing

### Deletion Behavior

When you delete a video's data:

```
✂️ DELETED:
├─ Transcript chunks (42 records)
├─ Claims (12 records)
├─ Quotes (8 records)
├─ Guest appearances (5 records)
├─ Temporary processing state
└─ Video summary cache

🚫 NOT DELETED (causes duplicates on reprocess):
├─ Vector embeddings (in ChromaDB)
├─ Graph nodes (in Neo4j)
└─ File logs (in kvault.log)
```

### Reprocessing After Deletion

```
Scenario: Delete video, then reprocess same URL

Step 1: Delete video data
└─ Video moves to DISCOVERED state

Step 2: Run harvest again
├─ Discovery phase finds same video_id
├─ Skips re-discovery of existing video
├─ Processes from scratch
├─ Creates NEW chunks and embeddings
└─ Result: Duplicates exist (old + new)

⚠️ To avoid duplicates:
- Manually delete from ChromaDB before reprocessing
- Manually delete from Neo4j before reprocessing
- OR: Accept duplicates and clean later
```

### Deletion History

All deletions are logged with:
- Timestamp
- Type (video or channel)
- Reason provided by user
- Count of items deleted
- Full audit trail

```sql
-- Query deletion history
SELECT * FROM deletion_history 
WHERE deleted_at > datetime('now', '-30 days')
ORDER BY deleted_at DESC;
```

---

## 📊 Monitoring Your Pipeline Health

### Key Metrics to Watch

**1. Log Summary**
```
SUCCESS: 145 (videos accepted)
INFO: 892 (general operations)
WARNING: 34 (minor issues)
ERROR: 3 (failures to investigate)
```

**2. Processing Stages**
```
METADATA_HARVESTED: 200 (discovered videos)
TRANSCRIPT_FETCHED: 145 (got transcripts)
CHUNKED: 142 (split into chunks)
EMBEDDED: 140 (indexed vectors)
DONE: 138 (complete)
```

**3. Triage Results**
```
ACCEPTED: 138 (include in knowledge base)
REJECTED: 8 (videos not relevant)
PENDING_REVIEW: 3 (manual decision needed)
```

### When to Investigate

| Indicator | Action |
|-----------|--------|
| ERROR count > 5 | Click Error Analysis → See patterns → Fix root cause |
| WARNING count > 50 | May indicate slow processing or network issues |
| Stuck at one stage | Video may be corrupted → Consider deleting |
| Many REJECTED videos | Triage configuration may be too strict |

---

## 🚀 Advanced Usage

### Monitoring via CLI

```bash
# View recent logs
tail -100 data/kvault.log

# Filter for errors
grep ERROR data/kvault.log | tail -20

# Count events by level
grep -oE '(SUCCESS\|INFO\|WARNING\|ERROR)' data/kvault.log | sort | uniq -c
```

### Python API Usage

```python
from src.config import get_settings
from src.storage.sqlite_store import SQLiteStore

db = SQLiteStore(get_settings()["sqlite"]["path"])

# Get recent errors
errors = db.get_logs(level="ERROR", limit=20)
for err in errors:
    print(f"{err.timestamp} | {err.stage} | {err.message}")

# Get summary for a scan
summary = db.get_log_summary(scan_id="abc12345")
print(f"Success: {summary.get('SUCCESS', 0)}")
print(f"Errors: {summary.get('ERROR', 0)}")

# Delete video and log it
result = db.delete_video_data("video_id", reason="Corrupted file")
print(f"Deleted {result['chunks_deleted']} chunks")
```

---

## 🐛 Troubleshooting

### Scan Not Appearing in Logs
**Problem:** Started harvest but don't see it in Pipeline Monitor
**Fix:** 
1. Ensure scan progressed past discovery phase
2. Try refreshing the page
3. Check `data/kvault.log` for startup errors

### Pause Doesn't Work
**Problem:** Click pause but pipeline continues
**Fix:**
1. Pause only stops BETWEEN videos
2. If video is mid-processing, it will finish first
3. Wait 10+ seconds before expecting pause
4. Check logs for actual pause timestamp

### Data Deletion Fails
**Problem:** "Could not delete video" error
**Fix:**
1. Check video exists: Is it in the dropdown?
2. Is it in DISCOVERED state? (Only deletable before full save)
3. Try refreshing UI and retrying
4. Check `data/kvault.log` for detailed error

### Duplicates After Reprocessing
**Problem:** After deletion and reprocessing, old data + new data exist
**Expected:** This is normal! Vector/graph stores aren't auto-deleted.
**Fix:**
1. Manually delete from ChromaDB/Neo4j (planned feature)
2. OR: Accept duplicates and filter them out during queries
3. OR: Use full reset (delete everything, start fresh)

---

## 📞 Questions?

See full documentation: [`docs/LOGGING_AND_MONITORING.md`](../docs/LOGGING_AND_MONITORING.md)

Key sections:
- Data Persistence After Deletion
- Reprocessing Behavior
- API Reference
- Integration Examples

---

## ✅ What's Next?

Future enhancements planned:
- [ ] Batch deletion (select multiple videos at once)
- [ ] Auto-cleanup rules (delete videos older than 6 months)
- [ ] ChromaDB deduplication tool
- [ ] Neo4j duplicate detection
- [ ] Log analysis dashboard (trends, patterns)
- [ ] Real-time alerts (email on errors)

---

**Enjoy your new monitoring superpowers! 🚀**
