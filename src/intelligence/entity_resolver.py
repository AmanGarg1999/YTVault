"""
Entity resolver for knowledgeVault-YT.

Identifies and deduplicates Guest entities across videos and channels
using NER extraction, fuzzy matching, and LLM disambiguation.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import ollama as ollama_api
from rapidfuzz import fuzz

from src.config import get_settings, load_prompt
from src.storage.sqlite_store import Guest, SQLiteStore

logger = logging.getLogger(__name__)

# Noise list to filter out common false positives from NER
ENTITY_IGNORE_LIST = {
    "you", "he", "she", "it", "they", "we", "i", "me", "him", "her", "us", "them",
    "assistant", "speaker", "host", "guest", "expert", "narrator",
    "india", "usa", "china", "london", "mars", "earth", # Skip pure locations if mis-tagged
    "youtube", "google", "openai", "anthropic", "meta", "tesla",
    "unknown", "someone", "somebody", "anyone", "everyone",
    "a", "the", "an", "this", "that", "there", "here"
}

@dataclass
class ExtractedEntity:
    """An entity extracted from a transcript chunk."""
    name: str
    role: str
    context: str


class EntityResolver:
    """Resolves guest entities across channels using NER + fuzzy matching + LLM.

    Pipeline:
        1. Extract person entities from transcript via LLM NER (with improved filtering)
        2. Attempt exact match against canonical names and aliases
        3. Attempt fuzzy match (Levenshtein similarity ≥ 85%)
        4. LLM disambiguation for multiple candidates
        5. Create new guest record if no match found
    """

    def __init__(self, db: SQLiteStore):
        self.db = db
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.ner_prompt = load_prompt("entity_extractor")
        self.fuzzy_threshold = 85  # rapidfuzz score threshold
        self._guests_cache: Optional[list[Guest]] = None  # Populated per batch

    def extract_entities(self, text: str) -> list[ExtractedEntity]:
        """Extract person entities from a transcript chunk using LLM NER.

        Args:
            text: Cleaned transcript text (first ~2000 chars used).

        Returns:
            List of extracted entities with names, roles, and context.
        """
        truncated = text[:2000]

        try:
            response = ollama_api.chat(
                model=self.ollama_cfg["triage_model"],  # Reuse fast model
                messages=[
                    {"role": "system", "content": self.ner_prompt},
                    {"role": "user", "content": truncated},
                ],
                options={
                    "num_predict": 500,
                    "temperature": 0.1,
                },
            )

            raw = response["message"]["content"].strip()
            entities = self._parse_entity_response(raw)
            
            # Additional filtering for quality
            filtered = []
            for e in entities:
                name_clean = e.name.lower().strip().strip('.,!?"')
                # Skip if too short, single character, or in noise list
                if len(name_clean) < 3: continue
                if name_clean in ENTITY_IGNORE_LIST: continue
                if any(word in ENTITY_IGNORE_LIST for word in name_clean.split()):
                    # Avoid skipping "Sam Altman" just because "Sam" is short, 
                    # but skip "Sam" if it's the only word and short.
                    if len(name_clean.split()) == 1: continue

                filtered.append(e)
                
            logger.debug(f"Extracted {len(filtered)} quality entities from chunk (filtered from {len(entities)})")
            return filtered

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    def resolve(self, entity_name: str) -> Guest:
        """Resolve an extracted name to a canonical Guest record."""
        # Normalize name for matching
        clean_name = entity_name.strip()
        
        # Step 1: Exact match
        guest = self.db.find_guest_exact(clean_name)
        if guest:
            logger.debug(f"Exact match: '{clean_name}' → '{guest.canonical_name}'")
            return guest

        # Step 2: Fuzzy match against cached guests
        candidates = self._fuzzy_match(clean_name)

        if len(candidates) == 1:
            # Single fuzzy match — add as alias
            guest = candidates[0]
            # Avoid adding tiny name fragments as aliases
            if len(clean_name) >= 4:
                self.db.add_guest_alias(guest.guest_id, clean_name)
            logger.info(
                f"Fuzzy match: '{clean_name}' → '{guest.canonical_name}'"
            )
            return guest

        if len(candidates) > 1:
            # Multiple matches — LLM disambiguation
            guest = self._llm_disambiguate(clean_name, candidates)
            if guest:
                return guest

        # Step 3: Create new guest and refresh cache
        guest = self.db.upsert_guest(clean_name)
        if self._guests_cache is not None:
            self._guests_cache.append(guest)
        logger.info(f"New guest created: '{clean_name}'")
        return guest

    def process_video_entities(
        self, video_id: str, transcript_text: str
    ) -> list[Guest]:
        """Full pipeline: extract entities from transcript and resolve them."""
        # Pre-load all guests for this batch
        self._guests_cache = self.db.get_all_guests()

        entities = self.extract_entities(transcript_text)
        resolved_guests = []
        seen_names = set()

        for entity in entities:
            if entity.name.lower().strip() in seen_names:
                continue
            seen_names.add(entity.name.lower().strip())

            guest = self.resolve(entity.name)
            resolved_guests.append(guest)

            # Record the appearance
            self.db.add_guest_appearance(
                guest_id=guest.guest_id,
                video_id=video_id,
                context=entity.context[:200],
            )

        self._guests_cache = None
        return resolved_guests

    def _fuzzy_match(self, name: str) -> list[Guest]:
        """Find guests with similar names."""
        all_guests = self._guests_cache if self._guests_cache is not None else self.db.get_all_guests()
        matches = []
        name_lower = name.lower()

        for guest in all_guests:
            score = fuzz.ratio(name_lower, guest.canonical_name.lower())
            if score >= self.fuzzy_threshold:
                matches.append(guest)
                continue

            for alias in guest.aliases:
                score = fuzz.ratio(name_lower, alias.lower())
                if score >= self.fuzzy_threshold:
                    matches.append(guest)
                    break
        return matches

    def _llm_disambiguate(
        self, name: str, candidates: list[Guest]
    ) -> Optional[Guest]:
        """Use LLM to disambiguate between multiple fuzzy-match candidates."""
        candidate_list = "\n".join(
            f"- {g.canonical_name} (aliases: {g.aliases}, mentions: {g.mention_count})"
            for g in candidates
        )

        prompt = (
            f'Is "{name}" the same person as any of these existing records?\n\n'
            f"{candidate_list}\n\n"
            f'Respond with ONLY the matching canonical name if it is definitely the same person, '
            f'or "NEW" if you are unsure or it is a different person.'
        )

        try:
            response = ollama_api.chat(
                model=self.ollama_cfg["triage_model"],
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": 50, "temperature": 0.0},
            )

            answer = response["message"]["content"].strip().strip('"').strip("'")

            if answer.upper() == "NEW":
                return None

            for guest in candidates:
                if fuzz.ratio(answer.lower(), guest.canonical_name.lower()) >= 90:
                    self.db.add_guest_alias(guest.guest_id, name)
                    return guest
            return None
        except Exception as e:
            logger.error(f"LLM disambiguation failed: {e}")
            return None

    def _parse_entity_response(self, raw: str) -> list[ExtractedEntity]:
        """Parse LLM NER response."""
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean
                clean = clean.rsplit("```", 1)[0].strip()

            data = json.loads(clean)
            if isinstance(data, list):
                return [
                    ExtractedEntity(
                        name=e.get("name", ""),
                        role=e.get("role", "unknown"),
                        context=e.get("context", ""),
                    )
                    for e in data
                    if e.get("name", "").strip()
                ]
        except Exception:
            pass
        return []
