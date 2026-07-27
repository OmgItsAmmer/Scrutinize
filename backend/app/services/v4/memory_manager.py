import asyncio
import json
import logging
import os
import threading
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.schemas.search import SearchSource
from app.models.file import FileModality

logger = logging.getLogger(__name__)

# Try to import Letta
try:
    from letta_client import Letta
    HAS_LETTA = True
except ImportError:
    Letta = None
    HAS_LETTA = False

# Try to import Graphiti
try:
    from graphiti_core import Graphiti
    HAS_GRAPHITI = True
except ImportError:
    Graphiti = None
    HAS_GRAPHITI = False


class MemoryManager:
    """Manages long-term user memory via Letta and temporal knowledge graph memory via Graphiti."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback_dir = os.path.dirname(os.path.abspath(__file__))
        self.letta_fallback_path = os.path.join(self.fallback_dir, "letta_fallback.json")
        self.graphiti_fallback_path = os.path.join(self.fallback_dir, "graphiti_fallback.json")
        
        self.letta_client = None
        self.graphiti_client = None

        # Initialize Letta if available and configured
        if HAS_LETTA and self.settings.letta_api_url:
            try:
                self.letta_client = Letta(
                    base_url=self.settings.letta_api_url,
                    api_key=self.settings.letta_api_key or "mock-key",
                )
                logger.info("Letta client initialized successfully.")
            except Exception as e:
                logger.warning("Failed to initialize Letta client: %s", e)

        # Initialize Graphiti if available and configured
        if HAS_GRAPHITI and self.settings.graphiti_neo4j_uri:
            try:
                self.graphiti_client = Graphiti(
                    uri=self.settings.graphiti_neo4j_uri,
                    user=self.settings.graphiti_neo4j_user,
                    password=self.settings.graphiti_neo4j_password,
                )
                logger.info("Graphiti client initialized successfully.")
            except Exception as e:
                logger.warning("Failed to initialize Graphiti client: %s", e)

    def get_user_memory(self, project_id: UUID) -> str:
        """Retrieve the long-term context/memory summary for a project/user."""
        if self.letta_client:
            try:
                # Find an agent for this project
                agent_name = f"project_{project_id}"
                agents = self.letta_client.agents.list()
                target_agent = None
                for agent in agents:
                    if agent.name == agent_name:
                        target_agent = agent
                        break
                
                if not target_agent:
                    # Create a new agent if not found
                    target_agent = self.letta_client.agents.create(
                        name=agent_name,
                        memory_blocks=[
                            {"label": "human", "value": "User project context."},
                            {"label": "persona", "value": "You are a stateful assistant remembering project details."}
                        ]
                    )
                
                # Fetch memory
                agent_state = self.letta_client.agents.retrieve(agent_id=target_agent.id)
                human_memory = ""
                for block in agent_state.memory_blocks:
                    if block.label == "human":
                        human_memory = block.value
                        break
                return human_memory
            except Exception as e:
                logger.warning("Letta get_user_memory failed, falling back: %s", e)

        # Fallback local JSON implementation
        return self._get_fallback_memory(project_id)

    def update_user_memory(self, project_id: UUID, query: str, answer: str) -> None:
        """Update the long-term context/memory based on the latest exchange."""
        if self.letta_client:
            try:
                agent_name = f"project_{project_id}"
                agents = self.letta_client.agents.list()
                target_agent = None
                for agent in agents:
                    if agent.name == agent_name:
                        target_agent = agent
                        break
                
                if not target_agent:
                    target_agent = self.letta_client.agents.create(
                        name=agent_name,
                        memory_blocks=[
                            {"label": "human", "value": f"Key project facts:\n- Query: {query}\n- Answer: {answer}"},
                            {"label": "persona", "value": "You are a stateful assistant remembering project details."}
                        ]
                    )
                else:
                    # Update Letta agent's memory by sending a message so it can update its memory
                    self.letta_client.agents.messages.create(
                        agent_id=target_agent.id,
                        messages=[
                            {"role": "user", "content": f"Update memory with this exchange:\nUser: {query}\nAssistant: {answer}"}
                        ]
                    )
                return
            except Exception as e:
                logger.warning("Letta update_user_memory failed, falling back: %s", e)

        # Fallback local JSON implementation
        self._update_fallback_memory(project_id, query, answer)

    def index_file(self, project_id: UUID, filename: str, content: str) -> None:
        """Index document content into the Graphiti temporal knowledge graph."""
        if self.graphiti_client:
            try:
                self._run_async(self._index_graphiti_file, filename, content)
                return
            except Exception as e:
                logger.warning("Graphiti index_file failed, falling back: %s", e)

        # Fallback local JSON implementation
        self._index_fallback_file(project_id, filename, content)

    def query_temporal_graph(self, project_id: UUID, query: str) -> list[SearchSource]:
        """Query Graphiti temporal knowledge graph for context related to query."""
        if self.graphiti_client:
            try:
                results = self._run_async(self.graphiti_client.search, query)
                sources = []
                # Map Graphiti search outputs to SearchSources
                if results and isinstance(results, list):
                    for i, res in enumerate(results):
                        # Safely extract text summary or representation
                        content = str(res.get("summary") if isinstance(res, dict) else res)
                        sources.append(
                            SearchSource(
                                segment_id=project_id,
                                file_id=project_id,
                                modality=FileModality.TEXT,
                                title="Graphiti Memory",
                                content=content,
                                source_path="graphiti://memory",
                                score=0.020 - (i * 0.001),
                            )
                        )
                return sources
            except Exception as e:
                logger.warning("Graphiti query_temporal_graph failed, falling back: %s", e)

        # Fallback local JSON implementation
        return self._query_fallback_graph(project_id, query)

    # Letta Fallback Helpers
    def _get_fallback_memory(self, project_id: UUID) -> str:
        data = self._read_json(self.letta_fallback_path)
        return data.get(str(project_id), "")

    def _update_fallback_memory(self, project_id: UUID, query: str, answer: str) -> None:
        data = self._read_json(self.letta_fallback_path)
        pid = str(project_id)
        current = data.get(pid, "")
        
        # Simple rule-based extraction of potential memory updates (e.g. "I am working on X", "We use Y")
        lines = []
        for line in query.split("."):
            line_strip = line.strip()
            if any(term in line_strip.lower() for term in ("work on", "use", "prefer", "always", "database", "euros", "currency", "prices")):
                lines.append(f"- {line_strip}")
                
        if lines:
            new_facts = "\n".join(lines)
            if current:
                updated = f"{current}\n{new_facts}"
            else:
                updated = f"Key facts learned:\n{new_facts}"
            
            # De-duplicate lines
            unique_lines = []
            for l in updated.split("\n"):
                if l not in unique_lines:
                    unique_lines.append(l)
            data[pid] = "\n".join(unique_lines)
            self._write_json(self.letta_fallback_path, data)

    # Graphiti Fallback Helpers
    def _index_fallback_file(self, project_id: UUID, filename: str, content: str) -> None:
        data = self._read_json(self.graphiti_fallback_path)
        pid = str(project_id)
        if pid not in data:
            data[pid] = []
        data[pid].append({"filename": filename, "content": content})
        self._write_json(self.graphiti_fallback_path, data)

    def _query_fallback_graph(self, project_id: UUID, query: str) -> list[SearchSource]:
        data = self._read_json(self.graphiti_fallback_path)
        pid = str(project_id)
        files = data.get(pid, [])
        sources = []
        
        # Simple substring search to mimic graph entity lookup
        words = [w.lower() for w in query.split() if len(w) >= 3]
        match_count = 0
        for f in files:
            content = f["content"]
            if any(word in content.lower() for word in words):
                match_count += 1
                sources.append(
                    SearchSource(
                        segment_id=project_id,
                        file_id=project_id,
                        modality=FileModality.TEXT,
                        title=f"Fallback Graphiti: {f['filename']}",
                        content=content[:500] + ("..." if len(content) > 500 else ""),
                        source_path=f"graphiti://fallback/{f['filename']}",
                        score=0.018 - (match_count * 0.001),
                    )
                )
            if len(sources) >= 2:
                break
        return sources

    async def _index_graphiti_file(self, filename: str, content: str):
        if not self.graphiti_client:
            return
        await self.graphiti_client.build_indices_and_constraints()
        await self.graphiti_client.add_episode(
            name=filename,
            episode_body=content,
            source="file"
        )

    def _read_json(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_json(self, path: str, data: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to write fallback memory store to %s: %s", path, e)

    def _run_async(self, func, *args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            result = None
            exception = None

            def target():
                 nonlocal result, exception
                 try:
                     result = asyncio.run(func(*args, **kwargs))
                 except Exception as e:
                     exception = e

            t = threading.Thread(target=target)
            t.start()
            t.join()
            if exception:
                raise exception
            return result
        else:
            return asyncio.run(func(*args, **kwargs))
