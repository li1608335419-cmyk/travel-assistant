from __future__ import annotations

from typing import Dict, List


AGENT_SKILLS: Dict[str, List[Dict[str, str]]] = {
    "planner": [
        {"id": "demand_structuring", "name": "需求结构化", "description": "把自然语言需求整理成结构化旅行画像。"},
        {"id": "gap_detection", "name": "缺口识别", "description": "优先识别目的地、时间、预算和同行人等关键缺口。"},
        {"id": "preference_routing", "name": "偏好路由", "description": "识别旅行偏好并将其传递给后续 agent。"},
        {
            "id": "place_resolver",
            "name": "Place Resolver",
            "description": "解析模糊地点表达、区域词和别名，提高目的地与起终点识别准确率。",
            "skill_path": "skills/place-resolver/SKILL.md",
        },
    ],
    "destination": [
        {"id": "seasonality_advice", "name": "季节判断", "description": "围绕目的地季节性和适合玩法给出建议。"},
        {"id": "traveler_fit", "name": "人群匹配", "description": "根据旅行偏好判断更适合的景点与节奏。"},
        {"id": "experience_styling", "name": "体验定调", "description": "把推荐风格调成更贴近用户预期的旅行体验。"},
        {
            "id": "meal_planner",
            "name": "Meal Planner",
            "description": "把餐饮建议纳入目的地体验设计，补充片区和用餐时段思路。",
            "skill_path": "skills/meal-planner/SKILL.md",
        },
    ],
    "transport_stay": [
        {"id": "arrival_strategy", "name": "到达策略", "description": "优先判断城市间到达方式和到站后的落点。"},
        {"id": "area_selection", "name": "片区选址", "description": "根据行程重心推荐更合适的住宿片区。"},
        {"id": "cost_convenience_balance", "name": "成本便利平衡", "description": "在预算、通勤便利和体验之间做平衡。"},
    ],
    "info": [
        {"id": "weather_guardrail", "name": "天气护栏", "description": "天气必须优先走实时接口，并拒绝使用过期网页信息。"},
        {"id": "poi_enrichment", "name": "POI 增强", "description": "补充景点、酒店、图片和地图路线等实时工具结果。"},
        {"id": "tool_cache_reuse", "name": "工具复用", "description": "优先复用 Redis 里的工具缓存，减少重复外部请求。"},
        {
            "id": "smart_stop_order",
            "name": "Smart Stop Order",
            "description": "自动对多景点进行顺路排序，减少折返并便于生成动线。",
            "skill_path": "skills/smart-stop-order/SKILL.md",
        },
        {
            "id": "meal_planner",
            "name": "Meal Planner",
            "description": "结合景点片区给出早餐、午餐、晚餐建议，让路线更完整。",
            "skill_path": "skills/meal-planner/SKILL.md",
        },
    ],
}


def get_agent_skill_specs(agent_name: str) -> List[Dict[str, str]]:
    return [item.copy() for item in AGENT_SKILLS.get(agent_name, [])]


def get_agent_skill_names(agent_name: str) -> List[str]:
    return [item["name"] for item in AGENT_SKILLS.get(agent_name, [])]
