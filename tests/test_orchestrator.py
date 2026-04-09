from core.orchestrator import TravelOrchestrator
from models.schemas import TravelIntent


class StubLLM:
    def invoke(self, prompt):
        class Response:
            content = "杭州两天适合轻松休闲游，建议尽早确认出发时间。"
        return Response()


class StubIntentLLM:
    def __init__(self, content):
        self.content = content

    def invoke(self, prompt):
        class Response:
            pass

        response = Response()
        response.content = self.content
        return response


def test_detect_intent(memory_store):
    orchestrator = TravelOrchestrator(memory_store=memory_store)
    intent, confidence = orchestrator.detect_intent("最近杭州天气怎么样")
    assert intent == TravelIntent.WEATHER_CHECK
    assert confidence > 0.8


def test_detect_intent_uses_llm_when_ambiguous(memory_store, monkeypatch):
    orchestrator = TravelOrchestrator(memory_store=memory_store)
    monkeypatch.setattr(
        orchestrator,
        "llm",
        StubIntentLLM('{"intent":"transport_advice","confidence":0.91,"reason":"用户同时问交通和住宿，主意图更接近出行建议"}'),
    )
    intent, confidence = orchestrator.detect_intent("去杭州高铁方便吗，住哪里比较合适")
    assert intent == TravelIntent.TRANSPORT_ADVICE
    assert confidence == 0.91


def test_detect_intent_falls_back_to_rule_when_llm_invalid(memory_store, monkeypatch):
    orchestrator = TravelOrchestrator(memory_store=memory_store)
    monkeypatch.setattr(orchestrator, "llm", StubIntentLLM("not-json"))
    intent, confidence = orchestrator.detect_intent("杭州行程怎么安排")
    assert intent == TravelIntent.ITINERARY_GENERATION
    assert confidence >= 0.78


def test_run_persists_session(memory_store, monkeypatch):
    orchestrator = TravelOrchestrator(memory_store=memory_store)
    monkeypatch.setattr(orchestrator, "llm", StubLLM())
    session, result = orchestrator.run("u1", "五一从上海出发去杭州玩2天怎么样")
    loaded = memory_store.get_session(session.session_id)
    assert loaded is not None
    assert len(loaded.messages) == 2
    assert result.answer.startswith("杭州两天")
    assert result.trip_summary
    assert result.agent_details[0]["agent_skills"]


def test_merge_rich_content_dedupes():
    merged = TravelOrchestrator._merge_rich_content(
        [
            type("R", (), {"rich_content": {"hotels": [{"name": "A", "booking_url": "u1"}], "attractions": [{"name": "西湖", "detail_url": "a1"}], "attraction_images": [], "route": {}}})(),
            type("R", (), {"rich_content": {"hotels": [{"name": "A", "booking_url": "u1"}], "attractions": [{"name": "西湖", "detail_url": "a1"}], "attraction_images": [], "route": {}}})(),
        ]
    )
    assert len(merged["hotels"]) == 1
    assert len(merged["attractions"]) == 1


def test_compose_weather_answer_with_notice():
    session = type("S", (), {"trip_profile": type("P", (), {"destination": "上海"})()})()
    answer = TravelOrchestrator._compose_weather_answer(
        session,
        [
            type(
                "R",
                (),
                {
                    "rich_content": {
                        "weather_notice": "高德天气当前还不能提供 2026年5月1日 的精确预报。",
                        "weather": {},
                    }
                },
            )()
        ],
    )
    assert "不能提供 2026年5月1日 的精确预报" in answer


def test_compose_time_and_weather_answer_for_date_only():
    session = type("S", (), {"trip_profile": type("P", (), {"destination": "杭州"})()})()
    answer = TravelOrchestrator._compose_time_and_weather_answer("今天是多少号", session, [])
    assert "今天是" in answer


def test_compose_time_and_weather_answer_for_combined_query():
    session = type("S", (), {"trip_profile": type("P", (), {"destination": "杭州"})()})()
    agent_results = [
        type(
            "R",
            (),
            {
                "rich_content": {
                    "weather": {
                        "mode": "live",
                        "city": "杭州",
                        "weather": "多云",
                        "temperature": "24",
                        "humidity": "60",
                        "winddirection": "东南",
                        "windpower": "3",
                        "reporttime": "2026-04-08 10:00:00",
                    }
                }
            },
        )()
    ]
    answer = TravelOrchestrator._compose_time_and_weather_answer("今天多少号。杭州天气怎么样", session, agent_results)
    assert "今天是" in answer
    assert "杭州 当前天气为 多云" in answer


def test_run_persists_selected_preferences(memory_store, monkeypatch):
    orchestrator = TravelOrchestrator(memory_store=memory_store)
    monkeypatch.setattr(orchestrator, "llm", StubLLM())
    session, _ = orchestrator.run("u1", "杭州怎么玩", skills=["food_hunter"])
    loaded = memory_store.get_session(session.session_id)
    assert loaded is not None
    assert "food_hunter" in loaded.trip_profile.skills
