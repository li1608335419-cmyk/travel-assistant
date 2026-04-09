from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import List

from langchain_openai import ChatOpenAI

from agents.destination import DestinationAgent
from agents.info import InfoAgent
from agents.planner import PlannerAgent
from agents.transport_stay import TransportStayAgent
from core.skills import describe_skills, display_skill_names, list_skills, normalize_skill_ids
from data.redis_memory import RedisMemoryStore
from models.schemas import (
    AgentResult,
    Message,
    MessageRole,
    OrchestratorResult,
    SessionState,
    SourceItem,
    TravelIntent,
)
from utils.logger import ExecutionTraceLogger
from tools.travel_tools import get_current_date_info


INTENT_KEYWORDS = {
    TravelIntent.WEATHER_CHECK: ["天气", "气温", "下雨"],
    TravelIntent.ITINERARY_GENERATION: ["行程", "攻略", "安排", "怎么玩"],
    TravelIntent.BUDGET_PLANNING: ["预算", "花费", "人均", "贵不贵"],
    TravelIntent.TRANSPORT_ADVICE: ["交通", "高铁", "飞机", "住宿", "酒店"],
    TravelIntent.DESTINATION_CHOICE: ["去哪", "推荐城市", "选哪里", "哪个地方"],
}

INTENT_DESCRIPTIONS = {
    TravelIntent.QA: "普通问答、咨询、解释性问题，无法明显归入其他类别时使用",
    TravelIntent.DESTINATION_CHOICE: "用户在比较去哪、选哪个城市、让系统推荐目的地",
    TravelIntent.ITINERARY_GENERATION: "用户要求生成行程、攻略、路线安排、怎么玩",
    TravelIntent.BUDGET_PLANNING: "用户关注预算、花费、人均成本、贵不贵",
    TravelIntent.WEATHER_CHECK: "用户询问天气、气温、降雨、穿衣建议",
    TravelIntent.TRANSPORT_ADVICE: "用户询问交通方式、怎么去、酒店住宿、到达方式",
}


class TravelOrchestrator:
    def __init__(self, memory_store: RedisMemoryStore | None = None) -> None:
        self.memory_store = memory_store or RedisMemoryStore()
        self.trace_logger = ExecutionTraceLogger()
        self.agents = [
            PlannerAgent(),
            DestinationAgent(),
            TransportStayAgent(),
            InfoAgent(),
        ]
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
            temperature=0.3,
        )

    def detect_intent(self, user_message: str) -> tuple[TravelIntent, float]:
        scored = self._rule_intent_scores(user_message)
        if not scored:
            llm_result = self._detect_intent_with_llm(user_message)
            if llm_result:
                return llm_result
            return TravelIntent.QA, 0.65

        best_intent, best_score = scored[0]
        runner_up_score = scored[1][1] if len(scored) > 1 else 0
        is_ambiguous = best_score == runner_up_score or (best_score == 1 and runner_up_score >= 1)

        if best_score >= 2 and not is_ambiguous:
            return best_intent, 0.9

        llm_result = self._detect_intent_with_llm(user_message, rule_candidates=scored[:3])
        if llm_result:
            return llm_result

        return best_intent, 0.82 if not is_ambiguous else 0.72

    def _rule_intent_scores(self, user_message: str) -> list[tuple[TravelIntent, int]]:
        scores: list[tuple[TravelIntent, int]] = []
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in user_message)
            if score > 0:
                scores.append((intent, score))
        scores.sort(key=lambda item: item[1], reverse=True)
        return scores

    def _detect_intent_with_llm(
        self,
        user_message: str,
        rule_candidates: list[tuple[TravelIntent, int]] | None = None,
    ) -> tuple[TravelIntent, float] | None:
        if self.llm is None:
            return None

        candidate_text = "\n".join(
            f"- {intent.value}: {INTENT_DESCRIPTIONS[intent]} (rule_score={score})"
            for intent, score in (rule_candidates or [])
        ) or "- 无明显规则命中，需模型判断"

        prompt = f"""
你是旅行助手系统的意图识别器。请只在以下意图中选择一个最主要的意图：

{chr(10).join(f"- {intent.value}: {desc}" for intent, desc in INTENT_DESCRIPTIONS.items())}

规则系统的候选结果：
{candidate_text}

用户输入：
{user_message}

请只返回 JSON，格式如下：
{{
  "intent": "qa | destination_choice | itinerary_generation | budget_planning | weather_check | transport_advice",
  "confidence": 0.0,
  "reason": "一句话说明"
}}
"""
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_intent_response(content)
        except Exception:
            return None

        if not parsed:
            return None

        intent_value = parsed.get("intent")
        confidence = float(parsed.get("confidence", 0.74))
        try:
            return TravelIntent(intent_value), max(0.55, min(confidence, 0.95))
        except ValueError:
            return None

    @staticmethod
    def _parse_intent_response(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    return {}
        return {}

    def run(
        self,
        user_id: str,
        user_message: str,
        session_id: str | None = None,
        skills: list[str] | None = None,
    ) -> tuple[SessionState, OrchestratorResult]:
        session = self.memory_store.require_session(user_id=user_id, session_id=session_id)
        self.trace_logger.log_orchestrator_start(user_id, session.session_id, user_message)
        session = self.memory_store.add_message(
            session.session_id,
            Message(role=MessageRole.USER, content=user_message),
        )
        active_skills = normalize_skill_ids((session.trip_profile.skills or []) + (skills or []))
        if active_skills != session.trip_profile.skills:
            session = self.memory_store.update_profile(session.session_id, {"skills": active_skills})

        intent, confidence = self.detect_intent(user_message)
        self.trace_logger.log_intent(session.session_id, intent.value, confidence)
        agent_results: List[AgentResult] = []
        for agent in self.agents:
            result = agent.run(user_message=user_message, session=session, intent=intent)
            agent_results.append(result)
            self.trace_logger.log_agent_result(session.session_id, result)
            if result.trip_profile_updates:
                session = self.memory_store.update_profile(session.session_id, result.trip_profile_updates)
            for tool_call in result.tool_calls:
                tool_name = tool_call["tool_name"]
                cache_key = tool_call.get("cache_key", tool_name)
                payload = {
                    "arguments": tool_call.get("arguments", {}),
                    "result": tool_call.get("result"),
                    "result_count": tool_call.get("result_count"),
                    "items": tool_call.get("items"),
                }
                self.memory_store.remember_tool_result(
                    session.session_id,
                    tool_name=cache_key,
                    payload=payload,
                )
                self.trace_logger.log_tool_memory_write(session.session_id, cache_key, payload)
            session = self.memory_store.get_session(session.session_id) or session

        final_answer = self._compose_answer(user_message, session, intent, agent_results)
        trip_summary = self._build_trip_summary(session, agent_results)
        session = self.memory_store.update_summary(session.session_id, trip_summary)
        session = self.memory_store.add_message(
            session.session_id,
            Message(
                role=MessageRole.ASSISTANT,
                content=final_answer,
                metadata={"intent": intent.value, "trip_summary": trip_summary},
            ),
        )
        all_sources = self._dedupe_sources(agent_results)
        tool_calls = [call for result in agent_results for call in result.tool_calls]
        follow_up = self._collect_follow_ups(agent_results)
        result = OrchestratorResult(
            answer=final_answer,
            sources=all_sources,
            follow_up_questions=follow_up,
            trip_summary=trip_summary,
            tool_calls=tool_calls,
            intent=intent,
            confidence=confidence,
            agent_sequence=[agent.name for agent in self.agents],
            rich_content=self._merge_rich_content(agent_results),
            agent_details=[
                {
                    "agent_name": item.agent_name,
                    "summary": item.summary,
                    "confidence": item.confidence,
                    "agent_skills": item.agent_skills,
                    "reasoning_trace": item.reasoning_trace,
                    "follow_up_questions": item.follow_up_questions,
                    "tool_calls": item.tool_calls,
                    "trip_profile_updates": item.trip_profile_updates,
                    "rich_content": item.rich_content,
                }
                for item in agent_results
            ],
        )
        self.trace_logger.log_chat_complete(session, result)
        return session, result

    def _compose_answer(
        self,
        user_message: str,
        session: SessionState,
        intent: TravelIntent,
        agent_results: List[AgentResult],
    ) -> str:
        profile = session.trip_profile
        destination = profile.destination or "目的地"
        summary_text = "\n".join(f"- {item.summary}" for item in agent_results)
        context = "\n".join(
            f"{message.role.value}: {message.content}" for message in session.messages[-6:]
        )
        prompt = f"""
你是中文旅行顾问。请基于用户问题、会话上下文和多 Agent 摘要，生成简洁但实用的旅行建议。

要求：
1. 先直接回答用户问题。
2. 若信息不足，用一句话指出仍缺什么。
3. 若有实时信息源，适度引用“我查到/最新信息显示”。
4. 用中文输出，不要编造不存在的来源链接。
5. 如果用户开启了旅行技能，请明显体现这些偏好，但不要生硬罗列内部字段名。

当前意图：{intent.value}
结构化画像：{json.dumps(profile.model_dump(), ensure_ascii=False)}
当前激活技能：{json.dumps(describe_skills(profile.skills), ensure_ascii=False)}
会话上下文：
{context}

Agent 摘要：
{summary_text}

用户问题：{user_message}
"""
        combined_answer = self._compose_time_and_weather_answer(user_message, session, agent_results)
        if combined_answer:
            return combined_answer
        if self.llm is None:
            return self._fallback_answer(user_message, session, intent, agent_results)
        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    @staticmethod
    def _compose_weather_answer(session: SessionState, agent_results: List[AgentResult]) -> str:
        weather_content = {}
        for item in agent_results:
            content = item.rich_content or {}
            if content.get("weather") or content.get("weather_notice"):
                weather_content = content
                break
        if not weather_content:
            return ""

        destination = session.trip_profile.destination or "该城市"
        notice = weather_content.get("weather_notice")
        if notice:
            return (
                f"{notice}\n\n"
                f"如果你计划去 {destination}，我现在可以先给你出行层面的保守建议：\n"
                f"- 临近出发前 3 到 4 天再查看高德实时预报\n"
                f"- 五一这类节假日通常人流大，建议提前订酒店和车票\n"
                f"- 出行前准备一件轻薄外套和雨具会更稳妥"
            )

        weather = weather_content.get("weather", {})
        if weather.get("mode") == "live":
            return (
                f"{weather.get('city', destination)} 当前天气为 {weather.get('weather', '未知')}，"
                f"气温 {weather.get('temperature', '-') }°C，湿度 {weather.get('humidity', '-') }%，"
                f"风向 {weather.get('winddirection', '-') }，风力 {weather.get('windpower', '-') } 级。"
                f"\n数据时间：{weather.get('reporttime', '-')}"
            )

        forecast = weather.get("forecast", [])
        if forecast:
            lines = [
                f"{weather.get('city', destination)} 未来天气预报如下：",
            ]
            for item in forecast[:4]:
                lines.append(
                    f"- {item.get('date')}: 白天 {item.get('dayweather')} {item.get('daytemp')}°C，"
                    f"夜间 {item.get('nightweather')} {item.get('nighttemp')}°C"
                )
            reporttime = weather.get("reporttime")
            if reporttime:
                lines.append(f"数据时间：{reporttime}")
            return "\n".join(lines)
        return ""

    @classmethod
    def _compose_time_and_weather_answer(
        cls,
        user_message: str,
        session: SessionState,
        agent_results: List[AgentResult],
    ) -> str:
        asks_date = any(token in user_message for token in ["今天多少号", "今天几号", "今天是几号", "今天是多少号", "今天几月几号", "今天星期几", "今天周几"])
        asks_weather = "天气" in user_message
        date_info = get_current_date_info(datetime.now(UTC)) if asks_date else None
        weather_answer = cls._compose_weather_answer(session, agent_results) if asks_weather else ""

        if asks_date and asks_weather and weather_answer:
            return (
                f"今天是{date_info['display_date']}，{date_info['weekday']}。\n\n"
                f"{weather_answer}"
            )
        if asks_date:
            return f"今天是{date_info['display_date']}，{date_info['weekday']}。"
        if asks_weather and weather_answer:
            return weather_answer
        return ""

    @staticmethod
    def _fallback_answer(
        user_message: str,
        session: SessionState,
        intent: TravelIntent,
        agent_results: List[AgentResult],
    ) -> str:
        profile = session.trip_profile
        destination = profile.destination or "目的地"
        follow_up = "；".join(
            q for result in agent_results for q in result.follow_up_questions[:1]
        )
        if intent == TravelIntent.WEATHER_CHECK:
            prefix = f"{destination} 的天气建议需要结合实时预报来看。"
        elif intent == TravelIntent.ITINERARY_GENERATION:
            prefix = f"{destination} 适合按你的时间做轻量行程规划。"
        else:
            prefix = f"我已经基于你的问题整理了 {destination} 相关建议。"
        extra = f" 如果你愿意，我可以继续根据出发地、预算和天数细化。" if follow_up else ""
        return prefix + extra

    def _build_trip_summary(self, session: SessionState, agent_results: List[AgentResult]) -> str:
        profile = session.trip_profile
        bits = []
        if profile.origin:
            bits.append(f"出发地：{profile.origin}")
        if profile.destination:
            bits.append(f"目的地：{profile.destination}")
        if profile.days:
            bits.append(f"天数：{profile.days}天")
        if profile.budget:
            bits.append(f"预算：{profile.budget}")
        if profile.skills:
            bits.append(f"偏好技能：{'、'.join(display_skill_names(profile.skills))}")
        if not bits:
            bits.append("当前仍在收集旅行关键信息。")
        bits.extend(result.summary for result in agent_results[:2])
        return " | ".join(bits)

    @staticmethod
    def _collect_follow_ups(agent_results: List[AgentResult]) -> List[str]:
        seen = set()
        questions = []
        for result in agent_results:
            for question in result.follow_up_questions:
                if question not in seen:
                    questions.append(question)
                    seen.add(question)
        if not questions:
            questions = ["告诉我你的出发地和时间，我可以继续细化建议。"]
        return questions[:3]

    @staticmethod
    def available_skills() -> list[dict]:
        return list_skills()

    @staticmethod
    def _dedupe_sources(agent_results: List[AgentResult]) -> List[SourceItem]:
        seen = set()
        sources: List[SourceItem] = []
        for result in agent_results:
            for source in result.sources:
                if source.url in seen:
                    continue
                seen.add(source.url)
                sources.append(source)
        return sources

    @staticmethod
    def _merge_rich_content(agent_results: List[AgentResult]) -> dict:
        merged = {"hotels": [], "attractions": [], "attraction_images": [], "meals": [], "route": {}, "weather": {}, "weather_notice": ""}
        seen_hotels = set()
        seen_attractions = set()
        seen_images = set()
        seen_meals = set()
        for result in agent_results:
            content = result.rich_content or {}
            for hotel in content.get("hotels", []):
                key = hotel.get("booking_url") or hotel.get("name")
                if key and key not in seen_hotels:
                    seen_hotels.add(key)
                    merged["hotels"].append(hotel)
            for attraction in content.get("attractions", []):
                key = attraction.get("detail_url") or attraction.get("name")
                if key and key not in seen_attractions:
                    seen_attractions.add(key)
                    merged["attractions"].append(attraction)
            for image in content.get("attraction_images", []):
                key = image.get("image_url") or image.get("source_url")
                if key and key not in seen_images:
                    seen_images.add(key)
                    merged["attraction_images"].append(image)
            for meal in content.get("meals", []):
                key = meal.get("name") or f"{meal.get('meal_type')}:{meal.get('business_area')}"
                if key and key not in seen_meals:
                    seen_meals.add(key)
                    merged["meals"].append(meal)
            if not merged["route"] and content.get("route"):
                merged["route"] = content["route"]
            if not merged["weather"] and content.get("weather"):
                merged["weather"] = content["weather"]
            if not merged["weather_notice"] and content.get("weather_notice"):
                merged["weather_notice"] = content["weather_notice"]
        merged["hotels"] = merged["hotels"][:4]
        merged["attractions"] = merged["attractions"][:4]
        merged["attraction_images"] = merged["attraction_images"][:6]
        merged["meals"] = merged["meals"][:3]
        return merged
