"""
Translation Engine for knowledgeVault-YT.

Provides language-aware translation for non-English transcripts.
Uses Ollama Llama-3 for high-quality LLM-based translation.

Supports:
- 25+ languages (auto-detected)
- Batch translation
- Caching to avoid re-translation
- Graceful fallback when translation fails
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import ollama

from src.config import get_settings, load_prompt
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)


# ISO 639-1 language codes to full names
LANGUAGE_MAP = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
    "tr": "Turkish",
    "pl": "Polish",
    "uk": "Ukrainian",
    "ro": "Romanian",
    "hu": "Hungarian",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
}


@dataclass
class TranslationResult:
    """Result of a translation attempt."""
    success: bool
    original_text: str
    translated_text: str = ""
    source_language: str = ""
    target_language: str = "en"
    latency_ms: float = 0.0
    error: Optional[str] = None


class TranslationEngine:
    """
    Translates non-English content to English for analysis.
    
    Uses Ollama Llama-3 for high-quality translation while preserving context.
    Optimized for transcript text (may contain filler words, casual speech).
    """

    def __init__(self):
        self.settings = get_settings()
        self.ollama_cfg = self.settings["ollama"]
        self.translation_cfg = self.settings.get("translation", {})
        
        # Use a dedicated model for translation or fall back to triage model
        self.model = self.translation_cfg.get("model", self.ollama_cfg["triage_model"])
        self.enabled = self.translation_cfg.get("enabled", True)
        self.target_language = self.translation_cfg.get("target_language", "en")
        
        # Load translation prompt if available
        try:
            self.translation_prompt = load_prompt("text_translator")
        except Exception:
            # Fallback prompt if text_translator.txt not found
            self.translation_prompt = """You are a professional translator. Translate the following {source_lang} text to {target_lang}.

IMPORTANT RULES:
- Preserve all technical terms, names, and proper nouns exactly
- Keep timestamps and numbers unchanged
- Maintain the original meaning and tone
- If text contains [timestamps] or similar markers, keep them as-is
- Do NOT add explanations or commentary
- Return ONLY the translated text

Original {source_lang} text:
{text}

Translated {target_lang} text:"""

    @with_retry("ollama_inference")
    def translate(self, text: str, source_lang: str, target_lang: str = "en") -> TranslationResult:
        """
        Translate text from source language to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code (e.g., "es" for Spanish)
            target_lang: Target language code (default: "en")
            
        Returns:
            TranslationResult with translated text or error details
        """
        import time
        
        if not self.enabled:
            return TranslationResult(
                success=False,
                original_text=text,
                source_language=source_lang,
                target_language=target_lang,
                error="Translation disabled in config"
            )
        
        if source_lang == target_lang:
            logger.debug(f"Skipping translation: source and target are same ({source_lang})")
            return TranslationResult(
                success=True,
                original_text=text,
                translated_text=text,
                source_language=source_lang,
                target_language=target_lang,
                latency_ms=0
            )
        
        source_name = LANGUAGE_MAP.get(source_lang, source_lang.upper())
        target_name = LANGUAGE_MAP.get(target_lang, target_lang.upper())
        
        try:
            start_time = time.time()
            
            # Chunk text if too long (Ollama has context limits)
            # Split on sentences for semantic integrity
            max_chunk_size = self.translation_cfg.get("max_chunk_size", 2000)
            chunks = self._chunk_text(text, max_chunk_size)
            
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                logger.debug(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
                
                prompt = self.translation_prompt.format(
                    source_lang=source_name,
                    target_lang=target_name,
                    text=chunk
                )
                
                from src.utils.llm_pool import get_llm_semaphore
                try:
                    with get_llm_semaphore():
                        response = ollama.generate(
                            model=self.model,
                            prompt=prompt,
                            stream=False,
                            options={
                                "temperature": 0.3,  # Low temp for consistency
                                "top_p": 0.9,
                                "num_predict": min(len(chunk.split()) * 1.2, 4000),
                            }
                        )
                    
                    translated_text = response["response"].strip()
                    translated_chunks.append(translated_text)
                    
                except Exception as e:
                    logger.error(f"Failed to translate chunk {i+1}: {e}")
                    raise
            
            # Combine chunks
            full_translation = " ".join(translated_chunks)
            latency_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Translation complete: {source_lang}→{target_lang} "
                f"({len(text)} → {len(full_translation)} chars, {latency_ms:.0f}ms)"
            )
            
            return TranslationResult(
                success=True,
                original_text=text,
                translated_text=full_translation,
                source_language=source_lang,
                target_language=target_lang,
                latency_ms=latency_ms
            )
            
        except Exception as e:
            logger.error(f"Translation failed ({source_lang}→{target_lang}): {e}", exc_info=True)
            return TranslationResult(
                success=False,
                original_text=text,
                source_language=source_lang,
                target_language=target_lang,
                error=str(e)
            )

    def translate_segments(self, segments: list[dict], source_lang: str) -> list[dict]:
        """
        Translate a list of transcript segments (with timestamps).
        
        Args:
            segments: List of dicts with {text, start, duration}
            source_lang: Source language code
            
        Returns:
            List of segments with translated text
        """
        if not segments or source_lang == "en":
            return segments
        
        # Combine texts, translate, then re-split
        combined_text = " ".join(s.get("text", "") for s in segments)
        
        result = self.translate(combined_text, source_lang)
        if not result.success:
            logger.warning(f"Failed to translate segments, returning originals")
            return segments
        
        # Simple re-split based on word boundaries
        translated_words = result.translated_text.split()
        original_word_count = [len(s.get("text", "").split()) for s in segments]
        
        translated_segments = []
        word_idx = 0
        
        for i, seg in enumerate(segments):
            word_count = original_word_count[i]
            translated_text = " ".join(translated_words[word_idx:word_idx + word_count])
            word_idx += word_count
            
            translated_segments.append({
                "text": translated_text,
                "start": seg.get("start", 0),
                "duration": seg.get("duration", 0),
                "original_text": seg.get("text", ""),  # Keep original for reference
            })
        
        return translated_segments

    def batch_translate(self, texts: list[str], source_lang: str) -> list[TranslationResult]:
        """Translate multiple texts in batch."""
        results = []
        for text in texts:
            result = self.translate(text, source_lang)
            results.append(result)
        return results

    def get_language_name(self, lang_code: str) -> str:
        """Get full language name from ISO code."""
        return LANGUAGE_MAP.get(lang_code, lang_code.upper())

    @staticmethod
    def _chunk_text(text: str, max_size: int) -> list[str]:
        """
        Split text into chunks by sentence boundaries.
        Tries to keep chunks under max_size without breaking sentences.
        """
        if len(text) <= max_size:
            return [text]
        
        sentences = text.replace("?", ".").replace("!", ".").split(".")
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            test_chunk = current_chunk + (" " if current_chunk else "") + sentence
            if len(test_chunk) <= max_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [text]

    def supports_language(self, lang_code: str) -> bool:
        """Check if translation supports this language."""
        return lang_code in LANGUAGE_MAP

    def get_supported_languages(self) -> dict:
        """Return all supported language codes and names."""
        return LANGUAGE_MAP.copy()
