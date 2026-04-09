from __future__ import annotations

from typing import Dict, List


SKILL_CATALOG: List[Dict[str, str]] = [
    {
        "id": "budget_optimizer",
        "name": "预算优化",
        "tagline": "优先控制花费，给出更省钱的路线、住宿和吃喝建议。",
        "prompt_hint": "优先考虑性价比，尽量给出预算友好的交通、住宿和玩法建议。",
    },
    {
        "id": "food_hunter",
        "name": "美食雷达",
        "tagline": "多补充本地值得吃的馆子、夜宵区和避坑建议。",
        "prompt_hint": "适当加入当地美食、餐饮片区和排队避坑建议。",
    },
    {
        "id": "photo_route",
        "name": "出片路线",
        "tagline": "优先推荐更好拍、更有氛围感的景点和动线。",
        "prompt_hint": "优先考虑景观、氛围和拍照体验，推荐更适合出片的路线。",
    },
    {
        "id": "family_friendly",
        "name": "亲子友好",
        "tagline": "强调轻松节奏、儿童友好景点和休息安排。",
        "prompt_hint": "优先考虑亲子友好、节奏轻松、适合带小孩的行程建议。",
    },
    {
        "id": "citywalk",
        "name": "Citywalk",
        "tagline": "更强调步行街区、咖啡馆、书店和城市气质。",
        "prompt_hint": "增加适合步行探索的街区、咖啡馆、书店和城市漫游建议。",
    },
    {
        "id": "rainy_day_backup",
        "name": "雨天备选",
        "tagline": "主动补充雨天可替代的室内去处和 Plan B。",
        "prompt_hint": "适当补充雨天可替代方案，尤其是室内景点和备选动线。",
    },
]

SKILL_LOOKUP = {item["id"]: item for item in SKILL_CATALOG}

SKILL_KEYWORDS = {
    "budget_optimizer": ["穷游", "省钱", "预算有限", "便宜点", "性价比", "花少点"],
    "food_hunter": ["美食", "吃什么", "好吃", "吃点好的", "夜宵", "小吃", "餐厅"],
    "photo_route": ["拍照", "出片", "机位", "打卡", "摄影"],
    "family_friendly": ["亲子", "带娃", "小朋友", "儿童", "家庭游"],
    "citywalk": ["citywalk", "散步", "压马路", "逛街区", "街区漫游", "城市漫游"],
    "rainy_day_backup": ["雨天", "下雨怎么办", "室内备选", "plan b", "备选方案"],
}


def list_skills() -> List[Dict[str, str]]:
    return [item.copy() for item in SKILL_CATALOG]


def normalize_skill_ids(skill_ids: List[str] | None) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for skill_id in skill_ids or []:
        if skill_id in SKILL_LOOKUP and skill_id not in seen:
            normalized.append(skill_id)
            seen.add(skill_id)
    return normalized


def infer_skills_from_text(text: str) -> List[str]:
    lowered = text.lower()
    matches: List[str] = []
    for skill_id, keywords in SKILL_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            matches.append(skill_id)
    return normalize_skill_ids(matches)


def describe_skills(skill_ids: List[str] | None) -> List[str]:
    return [SKILL_LOOKUP[skill_id]["prompt_hint"] for skill_id in normalize_skill_ids(skill_ids)]


def display_skill_names(skill_ids: List[str] | None) -> List[str]:
    return [SKILL_LOOKUP[skill_id]["name"] for skill_id in normalize_skill_ids(skill_ids)]
