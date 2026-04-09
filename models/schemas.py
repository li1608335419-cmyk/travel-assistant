from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TravelIntent(str, Enum):
    QA = "qa"
    DESTINATION_CHOICE = "destination_choice"
    ITINERARY_GENERATION = "itinerary_generation"
    BUDGET_PLANNING = "budget_planning"
    WEATHER_CHECK = "weather_check"
    TRANSPORT_ADVICE = "transport_advice"


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceItem(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_type: str = "search"


class StructuredTripRequest(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    date_range: Optional[str] = None
    days: Optional[int] = None
    budget: Optional[str] = None
    travelers: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    user_id: str
    messages: List[Message] = Field(default_factory=list)
    trip_profile: StructuredTripRequest = Field(default_factory=StructuredTripRequest)
    tool_memory: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None
    skills: List[str] = Field(default_factory=list)


class ChatMetadata(BaseModel):
    intent: TravelIntent
    confidence: float
    agent_sequence: List[str] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    trip_summary: str = ""
    rich_content: Dict[str, Any] = Field(default_factory=dict)
    debug: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    sources: List[SourceItem] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    metadata: ChatMetadata


class AgentResult(BaseModel):
    agent_name: str
    summary: str
    confidence: float = 0.7
    agent_skills: List[str] = Field(default_factory=list)
    sources: List[SourceItem] = Field(default_factory=list)
    needs_clarification: bool = False
    follow_up_questions: List[str] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    trip_profile_updates: Dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: List[str] = Field(default_factory=list)
    rich_content: Dict[str, Any] = Field(default_factory=dict)


class OrchestratorResult(BaseModel):
    answer: str
    sources: List[SourceItem] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    trip_summary: str = ""
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    intent: TravelIntent
    confidence: float
    agent_sequence: List[str] = Field(default_factory=list)
    agent_details: List[Dict[str, Any]] = Field(default_factory=list)
    rich_content: Dict[str, Any] = Field(default_factory=dict)
