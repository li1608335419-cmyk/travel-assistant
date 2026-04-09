from fastapi.testclient import TestClient

from api.app import app
from core.orchestrator import TravelOrchestrator
from models.schemas import (
    Message,
    MessageRole,
    OrchestratorResult,
    SessionState,
    StructuredTripRequest,
    TravelIntent,
)


class StubOrchestrator:
    def run(self, user_id, user_message, session_id=None, skills=None):
        session = SessionState(
            session_id=session_id or "SESSION-TEST",
            user_id=user_id,
            messages=[
                Message(role=MessageRole.USER, content=user_message),
                Message(role=MessageRole.ASSISTANT, content="可以去杭州西湖和灵隐寺"),
            ],
            trip_profile=StructuredTripRequest(destination="杭州", days=2, skills=skills or []),
        )
        result = OrchestratorResult(
            answer="可以去杭州西湖和灵隐寺",
            sources=[],
            follow_up_questions=["你想住西湖边还是东站附近？"],
            trip_summary="目的地：杭州 | 天数：2天",
            tool_calls=[],
            intent=TravelIntent.ITINERARY_GENERATION,
            confidence=0.88,
            agent_sequence=["planner", "destination", "transport_stay", "info"],
            rich_content={"hotels": [{"name": "西湖酒店", "booking_url": "https://example.com"}], "attractions": [], "attraction_images": [], "route": {}},
        )
        return session, result

    def available_skills(self):
        return [{"id": "budget_optimizer", "name": "预算优化", "tagline": "更省钱"}]


def test_chat_endpoint(monkeypatch):
    from api.routes import chat as chat_module

    monkeypatch.setattr(chat_module, "_orchestrator", StubOrchestrator())
    client = TestClient(app)
    response = client.post("/api/chat", json={"user_id": "u1", "message": "杭州两天怎么玩"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "SESSION-TEST"
    assert payload["metadata"]["intent"] == "itinerary_generation"
    assert payload["metadata"]["rich_content"]["hotels"][0]["name"] == "西湖酒店"


def test_skills_endpoint(monkeypatch):
    from api.routes import chat as chat_module

    monkeypatch.setattr(chat_module, "_orchestrator", StubOrchestrator())
    client = TestClient(app)
    response = client.get("/api/skills")
    assert response.status_code == 200
    payload = response.json()
    assert payload["skills"][0]["id"] == "budget_optimizer"
