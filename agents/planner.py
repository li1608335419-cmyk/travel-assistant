from models.schemas import AgentResult, SessionState, TravelIntent

from .base import BaseTravelAgent


class PlannerAgent(BaseTravelAgent):
    name = "planner"

    def __init__(self) -> None:
        super().__init__(tool_names=["trip_structurer", "place_resolver"])

    def run(self, user_message: str, session: SessionState, intent: TravelIntent) -> AgentResult:
        structured = self.invoke_tool(
            "trip_structurer",
            {"message": user_message, "skills": session.trip_profile.skills},
        )
        trip_patch = structured.get("structured_trip", {})
        tool_calls = [{"tool_name": "trip_structurer", "arguments": {"message": user_message, "skills": session.trip_profile.skills}}]
        if not trip_patch.get("destination"):
            resolved = self.invoke_tool("place_resolver", {"text": user_message})
            primary = resolved.get("primary") or {}
            if primary.get("city"):
                trip_patch["destination"] = primary["city"]
            tool_calls.append(
                {
                    "tool_name": "place_resolver",
                    "arguments": {"text": user_message},
                    "result": {"primary": primary},
                }
            )
        follow_up_questions = []
        if not trip_patch.get("destination"):
            follow_up_questions.append("你更想去哪个城市或地区？")
        if not trip_patch.get("date_range") and not trip_patch.get("days"):
            follow_up_questions.append("预计什么时候出发，玩几天？")
        if not trip_patch.get("skills"):
            follow_up_questions.append("更偏向省钱、美食、拍照还是亲子友好？我可以按这个方向细化。")

        summary = "已提取旅行需求关键字段，并判断是否需要进一步澄清。"
        return AgentResult(
            agent_name=self.name,
            summary=summary,
            confidence=0.8,
            agent_skills=self.agent_skill_names(),
            follow_up_questions=follow_up_questions,
            tool_calls=tool_calls,
            trip_profile_updates=trip_patch,
            reasoning_trace=[
                f"读取用户需求并尝试抽取结构化旅行字段: {sorted([key for key, value in trip_patch.items() if value])}",
                "检查关键缺口，优先关注目的地、时间和天数是否缺失。",
                f"当前激活的旅行技能: {trip_patch.get('skills', []) or ['无']}",
                f"当前 planner agent skills: {self.agent_skill_names()}",
            ],
        )
