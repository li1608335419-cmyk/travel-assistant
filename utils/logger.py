from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from models.schemas import AgentResult, OrchestratorResult, SessionState

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(name: str = "travel_assistant") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


class ExecutionTraceLogger:
    def __init__(self) -> None:
        self.logger = get_logger()
        self.execution_log_path = LOG_DIR / f"execution_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **payload,
        }
        with self.execution_log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_orchestrator_start(self, user_id: str, session_id: str, user_message: str) -> None:
        self.logger.info("chat start | user=%s session=%s message=%s", user_id, session_id, user_message[:120])
        self.log_event(
            "chat_start",
            {"user_id": user_id, "session_id": session_id, "user_message": user_message},
        )

    def log_intent(self, session_id: str, intent: str, confidence: float) -> None:
        self.logger.info("intent detected | session=%s intent=%s confidence=%.2f", session_id, intent, confidence)
        self.log_event(
            "intent_detected",
            {"session_id": session_id, "intent": intent, "confidence": confidence},
        )

    def log_agent_result(self, session_id: str, result: AgentResult) -> None:
        self.logger.info(
            "agent finished | session=%s agent=%s confidence=%.2f tools=%s",
            session_id,
            result.agent_name,
            result.confidence,
            len(result.tool_calls),
        )
        for line in result.reasoning_trace:
            self.logger.info("agent trace | session=%s agent=%s %s", session_id, result.agent_name, line)
        self.log_event(
            "agent_result",
            {
                "session_id": session_id,
                "agent_name": result.agent_name,
                "summary": result.summary,
                "confidence": result.confidence,
                "reasoning_trace": result.reasoning_trace,
                "follow_up_questions": result.follow_up_questions,
                "tool_calls": result.tool_calls,
                "trip_profile_updates": result.trip_profile_updates,
            },
        )

    def log_tool_memory_write(self, session_id: str, tool_name: str, payload: Dict[str, Any]) -> None:
        self.logger.info("tool memory saved | session=%s tool=%s", session_id, tool_name)
        self.log_event(
            "tool_memory_saved",
            {"session_id": session_id, "tool_name": tool_name, "payload": payload},
        )

    def log_chat_complete(self, session: SessionState, result: OrchestratorResult) -> None:
        self.logger.info(
            "chat complete | session=%s intent=%s sources=%s followups=%s",
            session.session_id,
            result.intent.value,
            len(result.sources),
            len(result.follow_up_questions),
        )
        self.log_event(
            "chat_complete",
            {
                "session_id": session.session_id,
                "intent": result.intent.value,
                "confidence": result.confidence,
                "trip_summary": result.trip_summary,
                "tool_calls": result.tool_calls,
                "follow_up_questions": result.follow_up_questions,
                "answer_preview": result.answer[:500],
            },
        )

    def log_error(self, event_type: str, session_id: str | None, error: str) -> None:
        self.logger.error("%s | session=%s error=%s", event_type, session_id, error)
        self.log_event(event_type, {"session_id": session_id, "error": error})
