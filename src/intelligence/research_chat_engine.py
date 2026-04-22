import json
import logging
import time
import ollama
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.intelligence.rag_engine import RAGEngine, RAGResponse, Citation
from src.config import get_settings, load_prompt

logger = logging.getLogger(__name__)

class ResearchChatEngine:
    """Conversational intelligence layer for the KnowledgeVault-YT Research Hub."""

    def __init__(self, db: SQLiteStore, vector_store: VectorStore):
        self.db = db
        self.vs = vector_store
        self.rag = RAGEngine(self.db, self.vs)
        self.settings = get_settings()
        self.suggestion_prompt = load_prompt("research_question_suggester")

    def create_session(self, initial_query: str) -> str:
        """Create a new session with an auto-generated title."""
        # Clean title from query
        title = initial_query[:40] + ("..." if len(initial_query) > 40 else "")
        return self.db.create_chat_session(title)

    def get_conversation_response(self, session_id: str, question: str) -> Dict[str, Any]:
        """
        Execute a multi-turn RAG query, save history, and generate discovery suggestions.
        """
        # 1. Load contextually relevant history
        history = self.db.get_chat_history(session_id)
        history_str = self._format_history(history)
        
        # 2. Execute RAG query with conversational context
        rag_response = self.rag.query(question, conversation_history=history_str)
        
        # 3. Generate autonomous "Suggested Next Steps"
        # We pass the RAG context and the answer to ensure relevance
        suggestions = self._generate_suggestions(rag_response)
        
        # 4. Save interactions to database
        self.db.insert_chat_message(
            session_id=session_id,
            role="user",
            content=question
        )
        
        citations_json = json.dumps([self._cit_to_dict(c) for c in rag_response.citations])
        self.db.insert_chat_message(
            session_id=session_id,
            role="assistant",
            content=rag_response.answer,
            suggested_json=json.dumps(suggestions),
            citations_json=citations_json
        )
        
        return {
            "answer": rag_response.answer,
            "citations": rag_response.citations,
            "suggestions": suggestions,
            "confidence": rag_response.confidence.overall if rag_response.confidence else 0.0
        }

    def _format_history(self, messages: List[Any], limit: int = 6) -> str:
        """Format last N messages for RAG context window."""
        from src.storage.sqlite_store import ChatMessage
        formatted = []
        for msg in messages[-limit:]:
            role = "Researcher" if msg.role == "user" else "Assistant"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)

    def _generate_suggestions(self, rag_response: RAGResponse) -> List[str]:
        """Generate 3-4 follow-up questions using the suggester prompt."""
        if not rag_response.citations:
            return ["Can you search for a different topic?", "Try broadening the search filters."]
            
        context_text = "\n".join([c.text_excerpt for c in rag_response.citations])
        prompt = self.suggestion_prompt.format(
            context=context_text,
            answer=rag_response.answer
        )
        
        from src.utils.llm_pool import LLMPool, LLMTask, LLMPriority
        
        def call_ollama(p):
            try:
                # Use system prompt for role definition, user prompt for context
                resp = ollama.chat(
                    model=self.settings["ollama"].get("deep_model", self.settings["ollama"].get("triage_model")),
                    messages=[
                        {"role": "system", "content": self.suggestion_prompt.split("CONTEXT:")[0].strip()},
                        {"role": "user", "content": p}
                    ],
                    options={"num_predict": 500, "temperature": 0.3},
                )
                text = resp["message"]["content"]
                
                # Robust parsing: Try to find a JSON array or a list of quoted strings
                import re
                # Try JSON array first
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        if isinstance(parsed, list):
                            return [str(s) for s in parsed]
                    except: pass
                
                # Fallback: Extract everything in quotes or starting with -
                extracted = re.findall(r'"([^"]+\?)"', text)
                if not extracted:
                    extracted = [l.strip("- ").strip() for l in text.split("\n") if "?" in l]
                
                return extracted[:4]
            except Exception as e:
                logger.warning(f"Failed to generate discovery suggestions: {e}")
                return []

        pool = LLMPool()
        task = LLMTask(
            task_id=f"suggestions_{int(time.time())}",
            fn=call_ollama,
            args=(prompt,),
            priority=LLMPriority.HIGH
        )
        
        try:
            logger.info(f"Submitting discovery pass for task {task.task_id}")
            future = pool.submit(task)
            result = future.result(timeout=20)
            logger.info(f"Discovery pass result: {result}")
            # Ensure we have a list of strings and exactly 3-4
            if isinstance(result, list) and len(result) > 0:
                return [str(s) for s in result[:4]]
            
            logger.warning("Discovery pass returned empty or invalid result, using fallback.")
            return ["What are the implications of this?", "Tell me more about the technical details.", "Are there any opposing views?"]
        except Exception as e:
            logger.error(f"Discovery pass failed or timed out: {e}")
            return ["What are the implications of this?", "Tell me more about the technical details.", "Are there any opposing views?"]

    def _cit_to_dict(self, c: Citation) -> Dict:
        """Helper for citation serialization."""
        return {
            "video_id": c.video_id,
            "video_title": c.video_title,
            "channel_name": c.channel_name,
            "timestamp": c.timestamp_str,
            "link": c.youtube_link,
            "excerpt": c.text_excerpt
        }
