from models.schemas import AgentResult, SessionState, TravelIntent

from .base import BaseTravelAgent


class DestinationAgent(BaseTravelAgent):
    name = "destination"

    def run(self, user_message: str, session: SessionState, intent: TravelIntent) -> AgentResult:
        profile = session.trip_profile
        destination = profile.destination or "未明确目的地"
        summary = f"围绕 {destination} 给出玩法、季节和适合人群建议。"
        if profile.skills:
            summary = f"围绕 {destination}，结合 {'、'.join(profile.skills)} 偏好给出玩法和体验建议。"
        if intent == TravelIntent.DESTINATION_CHOICE and not profile.destination:
            summary = "当前更适合先比较多个目的地，再给出选择建议。"
        return AgentResult(
            agent_name=self.name,
            summary=summary,
            confidence=0.72,
            agent_skills=self.agent_skill_names(),
            reasoning_trace=[
                f"根据当前目的地画像判断推荐重点: {destination}",
                "优先输出玩法、季节、适合人群和基础注意事项。",
                f"当前 destination agent skills: {self.agent_skill_names()}",
            ],
        )
