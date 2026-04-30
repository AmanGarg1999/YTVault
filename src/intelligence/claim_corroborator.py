"""
Claim Corroborator for knowledgeVault-YT.

Processes extracted claims, groups them by semantic similarity using 
ChromaDB, and calculates corroboration scores (consensus tracking).
"""

import logging
import uuid
import time
from typing import List, Dict, Any, Optional

from src.storage.sqlite_store import SQLiteStore, Claim
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ClaimCorroborator:
    """Groups similar claims and calculates corroboration scores."""

    def __init__(self, db: SQLiteStore, vector_store: VectorStore):
        self.db = db
        self.vs = vector_store
        self.similarity_threshold = 0.85

    def index_all_claims(self) -> int:
        """Embed and index all existing claims into the claims collection."""
        claims = self.db.execute("SELECT * FROM claims").fetchall()
        if not claims:
            return 0

        ids = [f"claim_{c['claim_id']}" for c in claims]
        texts = [c['claim_text'] for c in claims]
        metadatas = [{
            "claim_id": c['claim_id'],
            "video_id": c['video_id'],
            "speaker": c['speaker'],
            "topic": c['topic'],
        } for c in claims]

        self.vs.claims_collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        logger.info(f"Indexed {len(claims)} claims for corroboration analysis.")
        return len(claims)

    def corroborate_all(self):
        """Identify clusters of similar claims and update scores."""
        # 1. Fetch all claims sorted by created_at
        claims_rows = self.db.execute(
            "SELECT * FROM claims WHERE cluster_id IS NULL"
        ).fetchall()
        
        if not claims_rows:
            logger.info("No unclustered claims found.")
            return

        logger.info(f"Corroborating {len(claims_rows)} new claims...")

        for row in claims_rows:
            claim = Claim(**dict(row))
            
            # 2. Search for existing clusters (claims with cluster_id)
            query_embeddings = self.vs.embedding_fn([claim.claim_text])
            results = self.vs.claims_collection.query(
                query_embeddings=query_embeddings,
                n_results=5,
                where={"video_id": {"$ne": claim.video_id}}  # Don't match self or same video
            )

            matched_cluster_id = None
            if results['distances'] and results['distances'][0]:
                for i, dist in enumerate(results['distances'][0]):
                    similarity = 1.0 - dist
                    if similarity >= self.similarity_threshold:
                        # Found a match! Use its cluster_id if it has one
                        match_meta = results['metadatas'][0][i]
                        match_id = match_meta['claim_id']
                        
                        # Fetch match from DB to get its cluster_id
                        match_row = self.db.execute(
                            "SELECT cluster_id FROM claims WHERE claim_id = ?", 
                            (match_id,)
                        ).fetchone()
                        
                        if match_row and match_row['cluster_id']:
                            matched_cluster_id = match_row['cluster_id']
                            break
            
            # 3. Assign or create cluster_id
            if not matched_cluster_id:
                matched_cluster_id = str(uuid.uuid4())
            
            # 4. Update current claim
            self.db.execute(
                "UPDATE claims SET cluster_id = ? WHERE claim_id = ?",
                (matched_cluster_id, claim.claim_id)
            )
            
            # 5. Also index this claim so future ones can find it
            self.vs.claims_collection.upsert(
                ids=[f"claim_{claim.claim_id}"],
                documents=[claim.claim_text],
                metadatas={
                    "claim_id": claim.claim_id,
                    "video_id": claim.video_id,
                    "speaker": claim.speaker,
                    "topic": claim.topic,
                }
            )

        self.db.conn.commit()
        
        # 6. Final Pass: Update corroboration counts for all clusters
        self._update_all_counts()

    def _update_all_counts(self):
        """Update corroboration_count based on unique channels in each cluster."""
        clusters = self.db.execute(
            "SELECT cluster_id FROM claims WHERE cluster_id IS NOT NULL GROUP BY cluster_id"
        ).fetchall()
        
        for row in clusters:
            cid = row['cluster_id']
            # Count unique channels that mention this claim cluster
            count_row = self.db.execute("""
                SELECT COUNT(DISTINCT v.channel_id) as ch_count
                FROM claims c
                JOIN videos v ON c.video_id = v.video_id
                WHERE c.cluster_id = ?
            """, (cid,)).fetchone()
            
            ch_count = count_row['ch_count'] if count_row else 1
            
            self.db.execute(
                "UPDATE claims SET corroboration_count = ? WHERE cluster_id = ?",
                (ch_count, cid)
            )
            
        self.db.conn.commit()
        logger.info(f"Updated corroboration counts for {len(clusters)} clusters.")
