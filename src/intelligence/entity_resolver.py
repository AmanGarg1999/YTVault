"""
Entity Resolution & Sanitization for KnowledgeVault-YT.
Handles guest deduplication, fuzzy record merging, and noise suppression.
"""

import logging
import json
import difflib
from typing import List, Dict, Set, Optional
from src.storage.sqlite_store import SQLiteStore
from src.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

# Entities that are frequently extracted by NER but are not actual people/guests
NOISE_GUEST_BLACKLIST = {
    "NVIDIA", "Open AI", "US", "Nazi", "North Korea", "Taiwan", "Ukraine", 
    "monkey", "myself", "you", "yourself", "the speaker", "speaker", 
    "Unknown American", "Unknown Japanese", "No person mentioned", "None",
    "a minister", "the president", "human populations", "infant", "mathematical logic"
}

class EntityResolver:
    """Orchestrates the cleanup and deduplication of the research graph."""

    def __init__(self, db: SQLiteStore, graph: Optional[GraphStore] = None):
        self.db = db
        self.graph = graph

    def sanitize_expert_network(self) -> Dict[str, int]:
        """
        Main entry point for graph hardening:
        1. Purges known noise entities.
        2. Merges fuzzy duplicates (e.g. 'Marx, Karl' -> 'Karl Marx').
        """
        stats = {"purged": 0, "merged": 0}
        
        # 1. Purge Noise
        stats["purged"] = self.purge_noise_entities()
        
        # 2. Resolve fuzzy duplicates
        stats["merged"] = self.resolve_fuzzy_duplicates()
        
        return stats

    def purge_noise_entities(self) -> int:
        """Remove explicit noise entities from the guests table."""
        count = 0
        all_guests = self.db.execute("SELECT guest_id, canonical_name FROM guests").fetchall()
        
        for guest_id, name in all_guests:
            if name in NOISE_GUEST_BLACKLIST or len(name) < 2:
                # Delete the guest and its appearances in SQLite
                self.db.execute("DELETE FROM guest_appearances WHERE guest_id = ?", [guest_id])
                self.db.execute("DELETE FROM guests WHERE guest_id = ?", [guest_id])
                
                # Sync: Delete from Graph (Neo4j)
                if self.graph:
                    try:
                        self.graph.delete_guest(name)
                    except Exception as e:
                        logger.warning(f"Could not purge guest '{name}' from graph: {e}")
                
                count += 1
        
        self.db.commit()
        logger.info(f"Purged {count} noise entities from the Expert Network (Sync: {True if self.graph else False})")
        return count

    def resolve_fuzzy_duplicates(self, threshold: float = 0.85) -> int:
        """
        Identify and merge guest records with high string similarity.
        Example: 'Lex Fridman' and 'Lex Friedman'.
        """
        merged_count = 0
        all_guests = self.db.execute("SELECT guest_id, canonical_name, mention_count FROM guests ORDER BY mention_count DESC").fetchall()
        
        if not all_guests:
            return 0

        # Build a mapping of name -> id
        name_to_id = {row[1]: row[0] for row in all_guests}
        names = list(name_to_id.keys())
        processed_ids = set()

        for gid, name, count in all_guests:
            if gid in processed_ids:
                continue
            
            # Find close matches in the remaining names
            matches = difflib.get_close_matches(name, names, n=5, cutoff=threshold)
            
            # Also handle common 'Last, First' vs 'First Last' flips
            if ", " in name:
                parts = name.split(", ")
                flipped = f"{parts[1]} {parts[0]}"
                if flipped in name_to_id:
                    matches.append(flipped)

            mergee_ids = []
            for m in matches:
                mid = name_to_id[m]
                if mid != gid and mid not in processed_ids:
                    mergee_ids.append(mid)
                    processed_ids.add(mid)
            
            if mergee_ids:
                # Get names for Neo4j sync before they are deleted from SQLite
                mergee_names = []
                for mid in mergee_ids:
                    row = self.db.execute("SELECT canonical_name FROM guests WHERE guest_id = ?", [mid]).fetchone()
                    if row:
                        mergee_names.append(row[0])

                success = self.db.merge_guests(gid, mergee_ids)
                if success:
                    merged_count += len(mergee_ids)
                    
                    # Sync: Merge in Graph (Neo4j)
                    if self.graph and mergee_names:
                        try:
                            self.graph.merge_guests(name, mergee_names)
                        except Exception as e:
                            logger.error(f"Graph merge sync failed for '{name}': {e}")
            
            processed_ids.add(gid)

        return merged_count
