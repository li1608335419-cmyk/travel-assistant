from models.schemas import AgentResult, SessionState, TravelIntent

from .base import BaseTravelAgent


class TransportStayAgent(BaseTravelAgent):
    name = "transport_stay"

    def run(self, user_message: str, session: SessionState, intent: TravelIntent) -> AgentResult:
        profile = session.trip_profile
        origin = profile.origin or "你的出发地"
        destination = profile.destination or "目的地"
        summary = f"为 {origin} 到 {destination} 提供交通方式和住宿区域建议。"
        if profile.skills and "budget_optimizer" in profile.skills:
            summary = f"为 {origin} 到 {destination} 提供更重视性价比的交通方式和住宿区域建议。"
        return AgentResult(
            agent_name=self.name,
            summary=summary,
            confidence=0.7,
            agent_skills=self.agent_skill_names(),
            reasoning_trace=[
                f"交通住宿建议围绕路线 {origin} -> {destination} 展开。",
                "优先考虑城市间到达方式和住宿区域选择，而不是具体预订。",
                f"当前 transport_stay agent skills: {self.agent_skill_names()}",
            ],
        )
