"""
REST API for knowledgeVault-YT.

Exposes intelligence engines (RAG, Epiphany) and pipeline controls
to external agents and applications.
"""

import logging
import json
import time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.storage.graph_store import GraphStore
from src.intelligence.rag_engine import RAGEngine
from src.intelligence.epiphany_engine import EpiphanyEngine
from src.config import get_settings

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kvault_api")

app = FastAPI(
    title="KnowledgeVault Intelligence API",
    description="Research-grade intelligence engine for YouTube content.",
    version="1.0.0"
)

# Global Resources (Initialized once)
settings = get_settings()
db = SQLiteStore(settings["sqlite"]["path"])
vs = VectorStore()
graph = GraphStore()
rag = RAGEngine(db, vs)
epiphany = EpiphanyEngine(db, graph, rag)

# Data Models
class QueryRequest(BaseModel):
    question: str
    top_k: int = 15

class Citation(BaseModel):
    source_id: str
    video_id: str
    video_title: str
    channel_name: str
    timestamp: str
    youtube_link: str
    text_excerpt: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]
    confidence: float
    latency_ms: float

@app.get("/")
async def root():
    """Service health and discovery."""
    return {
        "app": "KnowledgeVault-YT",
        "status": "operational",
        "api_version": "1.0.0"
    }

@app.get("/stats")
async def get_stats():
    """Retrieve high-level vault statistics."""
    try:
        row = db.conn.execute("""
            SELECT 
                (SELECT COUNT(*) FROM channels) as channels,
                (SELECT COUNT(*) FROM videos WHERE triage_status='ACCEPTED') as videos,
                (SELECT COUNT(*) FROM transcript_chunks) as chunks,
                (SELECT COUNT(*) FROM claims) as claims
        """).fetchone()
        return dict(row) if row else {}
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def ask_vault(request: QueryRequest):
    """Ask a research question against the stored knowledge."""
    start_time = time.perf_counter()
    try:
        response = rag.query(request.question)
        
        citations = [
            Citation(
                source_id=c.source_id,
                video_id=c.video_id,
                video_title=c.video_title,
                channel_name=c.channel_name,
                timestamp=c.timestamp_str,
                youtube_link=c.youtube_link,
                text_excerpt=c.text_excerpt
            ) for c in response.citations
        ]
        
        latency = (time.perf_counter() - start_time) * 1000
        
        return QueryResponse(
            query=response.query,
            answer=response.answer,
            citations=citations,
            confidence=response.confidence.overall if response.confidence else 0.0,
            latency_ms=latency
        )
    except Exception as e:
        logger.error(f"RAG API Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/intelligence/briefing")
async def daily_briefing():
    """Generate or retrieve the latest cross-channel epiphany briefing."""
    try:
        briefings = epiphany.generate_daily_briefing()
        # Convert dataclasses to dicts
        return {"briefings": [b.__dict__ if hasattr(b, '__dict__') else b for b in briefings]}
    except Exception as e:
        logger.error(f"Epiphany API Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest")
async def trigger_ingest(url: str, background_tasks: BackgroundTasks):
    """Queue a new video or channel for ingestion."""
    from src.pipeline.orchestrator import PipelineOrchestrator
    
    def run_pipeline_task(target_url: str):
        # Fresh store for background thread
        orch = PipelineOrchestrator()
        try:
            orch.run(target_url)
        except Exception as err:
            logger.error(f"Background Ingest Failed: {err}")
        finally:
            orch.close()
            
    background_tasks.add_task(run_pipeline_task, url)
    return {"message": "Ingestion job queued", "target": url}
