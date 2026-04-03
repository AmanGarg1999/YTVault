"""
Health check utilities for knowledgeVault-YT.

Provides startup-time availability checks for external services
(Ollama, Neo4j) with graceful degradation.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ServiceStatus:
    """Status of an external service dependency."""

    def __init__(self, name: str, available: bool, detail: str = ""):
        self.name = name
        self.available = available
        self.detail = detail

    def __repr__(self):
        status = "✅" if self.available else "❌"
        return f"{status} {self.name}: {self.detail}"


def check_ollama(host: str = "http://localhost:11434") -> ServiceStatus:
    """Check if Ollama is running and responsive.

    Tests the /api/tags endpoint which lists available models.

    Returns:
        ServiceStatus with available=True if Ollama responds,
        plus list of loaded models in detail field.
    """
    try:
        import requests
        resp = requests.get(f"{host}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return ServiceStatus(
                "Ollama",
                available=True,
                detail=f"Connected ({len(models)} models: {', '.join(models[:5])})",
            )
        return ServiceStatus(
            "Ollama",
            available=False,
            detail=f"HTTP {resp.status_code}",
        )
    except Exception as e:
        return ServiceStatus("Ollama", available=False, detail=str(e))


def check_neo4j(uri: str, user: str, password: str) -> ServiceStatus:
    """Check if Neo4j is running and accepting connections.

    Returns:
        ServiceStatus with available=True if connection succeeds.
    """
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 AS n")
            result.single()
        driver.close()
        return ServiceStatus("Neo4j", available=True, detail=f"Connected ({uri})")
    except Exception as e:
        return ServiceStatus("Neo4j", available=False, detail=str(e))


def check_all_services(settings: dict) -> dict[str, ServiceStatus]:
    """Run health checks on all external dependencies.

    Returns:
        Dictionary of service name -> ServiceStatus.
    """
    results = {}

    # Ollama
    ollama_host = settings.get("ollama", {}).get("host", "http://localhost:11434")
    results["ollama"] = check_ollama(ollama_host)

    # Neo4j
    neo4j_cfg = settings.get("neo4j", {})
    results["neo4j"] = check_neo4j(
        uri=neo4j_cfg.get("uri", "bolt://localhost:7687"),
        user=neo4j_cfg.get("user", "neo4j"),
        password=neo4j_cfg.get("password", ""),
    )

    for name, status in results.items():
        if status.available:
            logger.info(str(status))
        else:
            logger.warning(str(status))

    return results


def require_ollama(settings: dict) -> bool:
    """Check Ollama and return True if available.

    Logs a clear warning if unavailable so the user knows
    LLM-dependent features won't work.
    """
    status = check_ollama(
        settings.get("ollama", {}).get("host", "http://localhost:11434")
    )
    if not status.available:
        logger.warning(
            "⚠️  Ollama is not available. LLM features (triage, normalization, "
            "topic extraction, entity resolution, RAG) will not work. "
            "Start Ollama with: ollama serve"
        )
    return status.available
