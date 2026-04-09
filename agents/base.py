import json
import os
from typing import Iterable, List, Optional

from langchain_openai import ChatOpenAI

from core.agent_skills import get_agent_skill_names
from models.schemas import AgentResult, SessionState, SourceItem, TravelIntent
from tools.travel_tools import get_tool_by_name


class BaseTravelAgent:
    name = "base"

    def __init__(self, tool_names: Optional[Iterable[str]] = None) -> None:
        self.tool_names = list(tool_names or [])
        self.llm = self._build_llm()

    @staticmethod
    def _build_llm():
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return ChatOpenAI(
            model=os.getenv("MODEL_NAME", "deepseek-chat"),
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            temperature=0.2,
        )

    def invoke_tool(self, tool_name: str, tool_input: dict) -> dict:
        tool = get_tool_by_name(tool_name)
        result = tool.invoke(tool_input)
        return result if isinstance(result, dict) else {"result": result}

    @staticmethod
    def _tool_cache_key(tool_name: str, tool_input: dict) -> str:
        return f"{tool_name}:{json.dumps(tool_input, ensure_ascii=False, sort_keys=True)}"

    def invoke_tool_cached(self, session: SessionState, tool_name: str, tool_input: dict) -> tuple[dict, bool]:
        cache_key = self._tool_cache_key(tool_name, tool_input)
        cached = session.tool_memory.get(cache_key)
        if cached and isinstance(cached, dict) and "payload" in cached:
            payload = cached["payload"]
            if isinstance(payload, dict):
                return payload, True
        return self.invoke_tool(tool_name, tool_input), False

    def run(self, user_message: str, session: SessionState, intent: TravelIntent) -> AgentResult:
        raise NotImplementedError

    def agent_skill_names(self) -> List[str]:
        return get_agent_skill_names(self.name)

    @staticmethod
    def _sources_from_results(items: List[dict]) -> List[SourceItem]:
        sources: List[SourceItem] = []
        for item in items:
            url = item.get("url")
            if not url:
                continue
            sources.append(
                SourceItem(
                    title=item.get("title", url),
                    url=url,
                    snippet=item.get("snippet", ""),
                    source_type=item.get("source_type", "search"),
                )
            )
        return sources
