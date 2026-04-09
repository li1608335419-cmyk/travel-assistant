from typing import List

from models.schemas import AgentResult, SessionState, TravelIntent

from .base import BaseTravelAgent
from tools.travel_tools import extract_city_from_text, resolve_weather_target


class InfoAgent(BaseTravelAgent):
    name = "info"

    def __init__(self) -> None:
        super().__init__(
            tool_names=[
                "weather_lookup",
                "hotel_search",
                "restaurant_search",
                "attraction_search",
                "image_search",
                "route_plan",
                "smart_stop_order",
            ]
        )

    def run(self, user_message: str, session: SessionState, intent: TravelIntent) -> AgentResult:
        query = user_message
        results: List[dict] = []
        weather_sources: List[dict] = []
        attractions: List[dict] = []
        attraction_images: List[dict] = []
        hotels: List[dict] = []
        meals: List[dict] = []
        route: dict = {}
        weather_data: dict = {}
        weather_notice = ""
        tool_calls = []
        destination = session.trip_profile.destination
        origin = session.trip_profile.origin
        inferred_destination = destination or extract_city_from_text(user_message)
        is_weather_query = "天气" in user_message
        if is_weather_query and inferred_destination:
            target = resolve_weather_target(user_message)
            if target.get("success") and not target.get("within_forecast_window"):
                weather_notice = (
                    f"高德天气当前还不能提供 {target['label']} 的精确预报。"
                    " 这类时间点超出短期天气预报窗口，不能再用旧网页文章代替实时结果。"
                )
                summary = "已识别目标日期超出实时预报窗口，改为返回保守天气说明。"
            else:
                extensions = "base" if any(token in user_message for token in ["今天", "现在", "此刻"]) else "all"
                weather_data, cache_hit = self.invoke_tool_cached(
                    session,
                    "weather_lookup",
                    {"city": inferred_destination, "extensions": extensions},
                )
                tool_calls.append(
                    {
                        "tool_name": "weather_lookup",
                        "arguments": {"city": inferred_destination, "extensions": extensions},
                        "result": weather_data,
                        "cache_key": self._tool_cache_key("weather_lookup", {"city": inferred_destination, "extensions": extensions}),
                        "cache_hit": cache_hit,
                    }
                )
                weather_sources.append(
                    {
                        "title": f"{inferred_destination} 实时天气",
                        "url": "https://lbs.amap.com/api/webservice/guide/api/weatherinfo",
                        "snippet": "来自高德开放平台天气查询接口",
                        "source_type": "weather",
                    }
                )
                summary = "天气问题已改走高德实时天气接口，不再依赖旧网页搜索。"
        else:
            summary = "本轮问题优先使用结构化旅行工具，而非通用网页搜索。"

        if destination and intent in [TravelIntent.ITINERARY_GENERATION, TravelIntent.TRANSPORT_ADVICE, TravelIntent.DESTINATION_CHOICE]:
            hotel_payload, hotel_cache_hit = self.invoke_tool_cached(session, "hotel_search", {"city": destination, "limit": 4})
            hotels = hotel_payload.get("hotels", [])
            tool_calls.append(
                {
                    "tool_name": "hotel_search",
                    "arguments": {"city": destination, "limit": 4},
                    "result_count": len(hotels),
                    "items": hotels,
                    "cache_key": self._tool_cache_key("hotel_search", {"city": destination, "limit": 4}),
                    "cache_hit": hotel_cache_hit,
                }
            )

            attraction_payload, attraction_cache_hit = self.invoke_tool_cached(
                session,
                "attraction_search",
                {"city": destination, "limit": 4},
            )
            attractions = attraction_payload.get("attractions", [])
            raw_attractions = list(attractions)
            tool_calls.append(
                {
                    "tool_name": "attraction_search",
                    "arguments": {"city": destination, "limit": 4},
                    "result_count": len(attractions),
                    "items": attractions,
                    "cache_key": self._tool_cache_key("attraction_search", {"city": destination, "limit": 4}),
                    "cache_hit": attraction_cache_hit,
                }
            )
            if len(attractions) > 1:
                ordered_payload, ordered_cache_hit = self.invoke_tool_cached(
                    session,
                    "smart_stop_order",
                    {"city": destination, "stops": raw_attractions},
                )
                if ordered_payload.get("success") and ordered_payload.get("ordered_stops"):
                    attractions = ordered_payload.get("ordered_stops", attractions)
                tool_calls.append(
                    {
                        "tool_name": "smart_stop_order",
                        "arguments": {"city": destination, "stops": raw_attractions},
                        "result_count": len(attractions),
                        "items": attractions[:4],
                        "cache_key": self._tool_cache_key("smart_stop_order", {"city": destination, "stops": raw_attractions}),
                        "cache_hit": ordered_cache_hit,
                    }
                )

            image_payload, image_cache_hit = self.invoke_tool_cached(session, "image_search", {"query": f"{destination} 景点 旅游 图片", "limit": 6})
            attraction_images = image_payload.get("images", [])
            tool_calls.append(
                {
                    "tool_name": "image_search",
                    "arguments": {"query": f"{destination} 景点 旅游 图片", "limit": 6},
                    "result_count": len(attraction_images),
                    "items": attraction_images[:4],
                    "cache_key": self._tool_cache_key("image_search", {"query": f"{destination} 景点 旅游 图片", "limit": 6}),
                    "cache_hit": image_cache_hit,
                }
            )
            restaurant_payload, restaurant_cache_hit = self.invoke_tool_cached(
                session,
                "meal_planner",
                {"city": destination, "limit": 6},
            )
            meals = restaurant_payload.get("meals", [])
            tool_calls.append(
                {
                    "tool_name": "meal_planner",
                    "arguments": {"city": destination, "limit": 6},
                    "result_count": len(meals),
                    "items": meals,
                    "cache_key": self._tool_cache_key("meal_planner", {"city": destination, "limit": 6}),
                    "cache_hit": restaurant_cache_hit,
                }
            )
            summary = f"{summary} 已通过高德补充景点与酒店 POI。"
            if meals:
                summary = f"{summary} 同时补充了分时段餐饮建议。"

        if origin and destination and intent in [TravelIntent.ITINERARY_GENERATION, TravelIntent.TRANSPORT_ADVICE]:
            route_mode = "walking" if any(token in user_message for token in ["步行", "walking", "走路"]) else "driving"
            route, route_cache_hit = self.invoke_tool_cached(
                session,
                "route_plan",
                {"origin": origin, "destination": destination, "mode": route_mode},
            )
            tool_calls.append(
                {
                    "tool_name": "route_plan",
                    "arguments": {"origin": origin, "destination": destination, "mode": route_mode},
                    "result": {
                        "success": route.get("success"),
                        "distance_km": route.get("distance_km"),
                        "duration_min": route.get("duration_min"),
                    },
                    "cache_key": self._tool_cache_key("route_plan", {"origin": origin, "destination": destination, "mode": route_mode}),
                    "cache_hit": route_cache_hit,
                }
            )
            if route.get("success") and route.get("steps"):
                summary = f"{summary} 已生成 {origin} 到 {destination} 的路线摘要。"
        return AgentResult(
            agent_name=self.name,
            summary=summary,
            confidence=0.75,
            agent_skills=self.agent_skill_names(),
            sources=self._sources_from_results(results + weather_sources),
            tool_calls=tool_calls,
            reasoning_trace=[
                "天气类问题优先走高德实时接口，而不是抓取通用网页结果。",
                "如果用户问的是超出预报窗口的日期，则明确说明当前没有精确实时天气。",
                "行程规划类问题使用高德 POI 和路径规划补齐景点、酒店和路线信息。",
                "优先复用同会话内已查询过的工具结果，减少重复外部请求。",
                f"当前 info agent skills: {self.agent_skill_names()}",
                f"餐饮建议数量: {len(meals)}，景点排序后数量: {len(attractions)}",
            ],
            rich_content={
                "hotels": hotels,
                "attractions": attractions,
                "attraction_images": attraction_images,
                "meals": meals,
                "route": route if route.get("success") else {},
                "weather": weather_data,
                "weather_notice": weather_notice,
            },
        )
