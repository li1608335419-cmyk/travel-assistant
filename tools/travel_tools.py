import os
import re
from datetime import UTC, date, datetime
from typing import Any, Dict, List

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from core.skills import infer_skills_from_text, normalize_skill_ids
from models.schemas import StructuredTripRequest

CITY_COORDINATES = {
    "北京": {"latitude": 39.9042, "longitude": 116.4074},
    "上海": {"latitude": 31.2304, "longitude": 121.4737},
    "杭州": {"latitude": 30.2741, "longitude": 120.1551},
    "成都": {"latitude": 30.5728, "longitude": 104.0668},
    "广州": {"latitude": 23.1291, "longitude": 113.2644},
    "深圳": {"latitude": 22.5431, "longitude": 114.0579},
    "重庆": {"latitude": 29.5630, "longitude": 106.5516},
    "西安": {"latitude": 34.3416, "longitude": 108.9398},
}


def extract_city_from_text(text: str) -> str | None:
    for city in CITY_COORDINATES:
        if city in text:
            return city
    city_match = re.search(r"([一-龥]{2,8})(天气|酒店|住宿|景点|路线|攻略|怎么玩)", text)
    if city_match:
        return city_match.group(1)
    return None


def _safe_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _amap_key() -> str:
    return os.getenv("AMAP_WEB_API_KEY", "").strip()


def _amap_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    key = _amap_key()
    if not key:
        raise RuntimeError("AMAP_WEB_API_KEY 未配置")
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, params={**params, "key": key})
        response.raise_for_status()
        return response.json()


class SearchInput(BaseModel):
    query: str = Field(description="旅行相关搜索词")
    limit: int = Field(default=5, ge=1, le=10)


class WeatherInput(BaseModel):
    city: str = Field(description="城市名称或 adcode")
    extensions: str = Field(default="all", description="base 表示实况，all 表示未来天气预报")


class TripStructurerInput(BaseModel):
    message: str = Field(description="用户旅行需求原文")
    skills: List[str] = Field(default_factory=list, description="用户主动选择的旅行技能")


class HotelSearchInput(BaseModel):
    city: str = Field(description="目的地城市")
    limit: int = Field(default=4, ge=1, le=8)


class RestaurantSearchInput(BaseModel):
    city: str = Field(description="目的地城市")
    limit: int = Field(default=6, ge=1, le=10)


class ImageSearchInput(BaseModel):
    query: str = Field(description="景点或目的地图片搜索词")
    limit: int = Field(default=6, ge=1, le=10)


class RoutePlanInput(BaseModel):
    origin: str = Field(description="出发地")
    destination: str = Field(description="目的地")
    mode: str = Field(default="driving", description="路线模式 driving 或 walking")


class PlaceResolverInput(BaseModel):
    text: str = Field(description="包含地名、片区或模糊地点表达的原始文本")


class StopOrderInput(BaseModel):
    city: str = Field(description="城市名称")
    stops: List[Dict[str, Any]] = Field(description="待排序的景点或停靠点列表")


def web_search(query: str, limit: int = 5) -> Dict[str, Any]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {
            "success": False,
            "message": "SERPER_API_KEY 未配置，无法执行实时搜索。",
            "results": [],
        }

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": limit, "gl": "cn", "hl": "zh-cn"}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post("https://google.serper.dev/search", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        return {"success": False, "message": f"搜索失败: {exc}", "results": []}

    organic = data.get("organic", [])
    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "source_type": "search",
        }
        for item in organic[:limit]
    ]
    return {"success": True, "message": f"找到 {len(results)} 条结果", "results": results}


def amap_geocode(place: str) -> Dict[str, Any]:
    try:
        data = _amap_get(
            "https://restapi.amap.com/v3/geocode/geo",
            {"address": place, "output": "json"},
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        return {"success": False, "message": f"高德地理编码失败: {exc}"}

    if data.get("status") != "1" or not data.get("geocodes"):
        return {"success": False, "message": data.get("info", f"无法定位 {place}")}

    first = data["geocodes"][0]
    location = first.get("location", "")
    longitude, latitude = location.split(",") if "," in location else ("", "")
    return {
        "success": True,
        "name": first.get("formatted_address", place),
        "city": first.get("city") or place,
        "adcode": first.get("adcode"),
        "latitude": float(latitude) if latitude else None,
        "longitude": float(longitude) if longitude else None,
    }


def amap_poi_search(city: str, keywords: str, limit: int = 4) -> Dict[str, Any]:
    city_geo = amap_geocode(city)
    if not city_geo.get("success"):
        return {"success": False, "message": city_geo.get("message", "城市定位失败"), "pois": []}
    try:
        data = _amap_get(
            "https://restapi.amap.com/v3/place/around",
            {
                "location": f"{city_geo['longitude']},{city_geo['latitude']}",
                "keywords": keywords,
                "radius": 25000,
                "offset": limit,
                "page": 1,
                "extensions": "all",
                "output": "json",
            },
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        return {"success": False, "message": f"高德 POI 查询失败: {exc}", "pois": []}

    if data.get("status") != "1":
        return {"success": False, "message": data.get("info", "POI 查询失败"), "pois": []}
    return {"success": True, "pois": data.get("pois", [])}


def image_search(query: str, limit: int = 6) -> Dict[str, Any]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {
            "success": False,
            "message": "SERPER_API_KEY 未配置，无法执行图片搜索。",
            "images": [],
        }

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": limit, "gl": "cn", "hl": "zh-cn"}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post("https://google.serper.dev/images", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        return {"success": False, "message": f"图片搜索失败: {exc}", "images": []}

    images = [
        {
            "title": item.get("title", ""),
            "image_url": item.get("imageUrl", ""),
            "thumbnail_url": item.get("thumbnailUrl", item.get("imageUrl", "")),
            "source_url": item.get("link", ""),
            "source_type": "image",
        }
        for item in data.get("images", [])[:limit]
        if item.get("imageUrl")
    ]
    return {"success": True, "message": f"找到 {len(images)} 张图片", "images": images}


def hotel_search(city: str, limit: int = 4) -> Dict[str, Any]:
    payload = amap_poi_search(city, "酒店", limit=limit)
    hotels = []
    for item in payload.get("pois", [])[:limit]:
        hotels.append(
            {
                "name": item.get("name", ""),
                "description": item.get("address") or item.get("type", ""),
                "booking_url": _amap_poi_url(item.get("id"), item.get("location"), item.get("name")),
                "area_hint": item.get("business_area") or city,
                "price_hint": "",
                "distance_m": item.get("distance", ""),
                "location": item.get("location", ""),
            }
        )
    return {
        "success": payload.get("success", False),
        "message": payload.get("message", ""),
        "hotels": hotels,
    }


def _clean_hotel_name(title: str) -> str:
    for marker in ["- 携程", "_携程", "- 去哪儿", "- 马蜂窝", "- Booking", "- Agoda"]:
        if marker in title:
            title = title.split(marker, 1)[0].strip()
    return title.strip()


def _extract_price_hint(text: str) -> str:
    match = re.search(r"(¥|￥)\s?\d{2,4}", text)
    if match:
        return match.group(0)
    match = re.search(r"\d{2,4}\s?元", text)
    if match:
        return match.group(0)
    return ""


def _extract_area_hint(text: str, default: str, area_keywords: List[str]) -> str:
    for keyword in area_keywords:
        if keyword in text:
            return keyword
    return default


def attraction_search(city: str, limit: int = 4) -> Dict[str, Any]:
    payload = amap_poi_search(city, "景点", limit=limit)
    attractions = []
    for item in payload.get("pois", [])[:limit]:
        attractions.append(
            {
                "name": item.get("name", ""),
                "description": item.get("address") or item.get("type", ""),
                "detail_url": _amap_poi_url(item.get("id"), item.get("location"), item.get("name")),
                "location": item.get("location", ""),
                "business_area": item.get("business_area", ""),
            }
        )
    return {
        "success": payload.get("success", False),
        "message": payload.get("message", ""),
        "attractions": attractions,
    }


def restaurant_search(city: str, limit: int = 6) -> Dict[str, Any]:
    payload = amap_poi_search(city, "美食", limit=limit)
    restaurants = []
    for item in payload.get("pois", [])[:limit]:
        restaurants.append(
            {
                "name": item.get("name", ""),
                "description": item.get("address") or item.get("type", ""),
                "detail_url": _amap_poi_url(item.get("id"), item.get("location"), item.get("name")),
                "business_area": item.get("business_area", "") or city,
                "distance_m": item.get("distance", ""),
                "location": item.get("location", ""),
            }
        )
    return {
        "success": payload.get("success", False),
        "message": payload.get("message", ""),
        "restaurants": restaurants,
    }


def _clean_attraction_name(title: str, city: str) -> str:
    title = re.sub(r"\s*[-|_].*$", "", title).strip()
    if city and city not in title and "景点" in title:
        return f"{city} {title}"
    return title


def _amap_poi_url(poi_id: str | None, location: str | None, name: str | None) -> str:
    if location and name:
        return f"https://uri.amap.com/marker?position={location}&name={name}&src=travel-assistant"
    if poi_id:
        return f"https://www.amap.com/detail/{poi_id}"
    return "https://www.amap.com/"


def weather_lookup(city: str, extensions: str = "all") -> Dict[str, Any]:
    adcode = city if city.isdigit() else amap_geocode(city).get("adcode")
    if not adcode:
        return {"success": False, "message": f"无法获取 {city} 的 adcode", "forecast": []}
    try:
        data = _amap_get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            {"city": adcode, "extensions": extensions, "output": "json"},
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        return {"success": False, "message": f"天气查询失败: {exc}", "forecast": []}

    if data.get("status") != "1":
        return {"success": False, "message": data.get("info", "天气查询失败"), "forecast": []}

    lives = data.get("lives", [])
    forecasts = data.get("forecasts", [])
    if extensions == "base" and lives:
        live = lives[0]
        return {
            "success": True,
            "mode": "live",
            "city": live.get("city"),
            "adcode": live.get("adcode"),
            "weather": live.get("weather"),
            "temperature": live.get("temperature"),
            "winddirection": live.get("winddirection"),
            "windpower": live.get("windpower"),
            "humidity": live.get("humidity"),
            "reporttime": live.get("reporttime"),
        }

    casts = forecasts[0].get("casts", []) if forecasts else []
    return {
        "success": True,
        "mode": "forecast",
        "city": forecasts[0].get("city") if forecasts else city,
        "adcode": forecasts[0].get("adcode") if forecasts else adcode,
        "reporttime": forecasts[0].get("reporttime") if forecasts else None,
        "forecast": [
            {
                "date": item.get("date"),
                "week": item.get("week"),
                "dayweather": item.get("dayweather"),
                "nightweather": item.get("nightweather"),
                "daytemp": item.get("daytemp"),
                "nighttemp": item.get("nighttemp"),
                "daywind": item.get("daywind"),
                "nightwind": item.get("nightwind"),
            }
            for item in casts
        ],
    }


def trip_structurer(message: str, skills: List[str] | None = None) -> Dict[str, Any]:
    profile = StructuredTripRequest()
    text = message.replace("，", " ").replace(",", " ")
    if "从" in text and "出发" in text:
        origin = text.split("从", 1)[1].split("出发", 1)[0].strip()
        if origin:
            profile.origin = origin
    if "去" in text:
        destination = text.split("去", 1)[1]
        for marker in ["玩", "旅游", "旅行", "看看", "逛", "待", "住", "预算", "大概", "怎么样", "如何", "吗", "？", "?"]:
            if marker in destination:
                destination = destination.split(marker, 1)[0]
        destination = destination.strip()
        if destination:
            profile.destination = destination
    if not profile.destination:
        inferred_city = extract_city_from_text(message)
        if inferred_city:
            profile.destination = inferred_city
    if "天" in text:
        import re

        day_match = re.search(r"(\d+)\s*天", text)
        if day_match:
            profile.days = int(day_match.group(1))
    budget_markers = ["预算", "花费", "人均"]
    for marker in budget_markers:
        if marker in text:
            after = text.split(marker, 1)[1][:12].strip()
            if after:
                profile.budget = after
                break
    profile.skills = normalize_skill_ids((skills or []) + infer_skills_from_text(message))
    return {"success": True, "structured_trip": profile.model_dump()}


def resolve_weather_target(message: str, today: date | None = None) -> Dict[str, Any]:
    today = today or date.today()
    if "五一" in message:
        year = today.year if today <= date(today.year, 5, 1) else today.year + 1
        target = date(year, 5, 1)
        delta = (target - today).days
        return {
            "success": True,
            "target_date": target.isoformat(),
            "within_forecast_window": 0 <= delta <= 4,
            "label": f"{year}年5月1日",
        }

    md = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", message)
    if md:
        month = int(md.group(1))
        day = int(md.group(2))
        year = today.year
        target = date(year, month, day)
        if target < today:
            year += 1
            target = date(year, month, day)
        delta = (target - today).days
        return {
            "success": True,
            "target_date": target.isoformat(),
            "within_forecast_window": 0 <= delta <= 4,
            "label": f"{year}年{month}月{day}日",
        }
    return {"success": False}


def get_current_date_info(now: datetime | None = None) -> Dict[str, Any]:
    now = now or datetime.now(UTC)
    weekday_map = {
        0: "星期一",
        1: "星期二",
        2: "星期三",
        3: "星期四",
        4: "星期五",
        5: "星期六",
        6: "星期日",
    }
    return {
        "success": True,
        "iso_date": now.date().isoformat(),
        "display_date": f"{now.year}年{now.month}月{now.day}日",
        "weekday": weekday_map[now.weekday()],
    }


def resolve_city_coordinates(city_name: str) -> Dict[str, Any]:
    city_name = city_name.strip()
    exact = CITY_COORDINATES.get(city_name)
    if exact:
        return {"success": True, "city": city_name, **exact}
    for known_city, coords in CITY_COORDINATES.items():
        if known_city in city_name:
            return {"success": True, "city": known_city, **coords}
    return {"success": False, "message": f"暂时没有 {city_name} 的内置经纬度映射"}


def geocode_place(place: str) -> Dict[str, Any]:
    amap_result = amap_geocode(place)
    if amap_result.get("success"):
        return amap_result
    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": "travel-assistant/0.1"}) as client:
            response = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": place, "format": "jsonv2", "limit": 1},
            )
            response.raise_for_status()
            results = response.json()
    except httpx.HTTPError as exc:
        return {"success": False, "message": f"地理编码失败: {exc}"}
    if not results:
        return {"success": False, "message": f"无法定位 {place}"}
    first = results[0]
    return {
        "success": True,
        "name": first.get("display_name", place),
        "latitude": float(first["lat"]),
        "longitude": float(first["lon"]),
    }


def route_plan(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    origin_geo = geocode_place(origin)
    destination_geo = geocode_place(destination)
    if not origin_geo.get("success") or not destination_geo.get("success"):
        return {
            "success": False,
            "message": "路线规划前需要先成功定位起点和终点。",
            "origin": origin_geo,
            "destination": destination_geo,
        }

    amap_mode = "walking" if mode == "walking" else "driving"
    try:
        data = _amap_get(
            f"https://restapi.amap.com/v3/direction/{amap_mode}",
            {
                "origin": f"{origin_geo['longitude']},{origin_geo['latitude']}",
                "destination": f"{destination_geo['longitude']},{destination_geo['latitude']}",
                "output": "json",
                "extensions": "base",
            },
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        return {"success": False, "message": f"路线规划失败: {exc}"}

    route = data.get("route", {})
    paths = route.get("paths", [])
    if data.get("status") != "1" or not paths:
        return {"success": False, "message": data.get("info", "未获取到可用路线。")}

    first_path = paths[0]
    steps: List[Dict[str, Any]] = []
    for step in first_path.get("steps", [])[:8]:
        steps.append(
            {
                "instruction": step.get("instruction", "继续前进"),
                "distance_m": round(float(step.get("distance", 0)), 1),
                "duration_s": round(float(step.get("duration", 0)), 1),
            }
        )

    map_url = (
        "https://uri.amap.com/navigation?"
        f"from={origin_geo['longitude']},{origin_geo['latitude']},{origin}"
        f"&to={destination_geo['longitude']},{destination_geo['latitude']},{destination}"
        f"&mode={(0 if amap_mode == 'driving' else 2)}&src=travel-assistant"
    )
    return {
        "success": True,
        "origin": origin_geo,
        "destination": destination_geo,
        "mode": mode,
        "distance_km": round(float(first_path.get("distance", 0)) / 1000, 1),
        "duration_min": round(float(first_path.get("duration", 0)) / 60),
        "steps": steps,
        "map_url": map_url,
    }


def place_resolver(text: str) -> Dict[str, Any]:
    candidates = []
    seen = set()
    for city in CITY_COORDINATES:
        if city in text and city not in seen:
            seen.add(city)
            candidates.append({"name": city, "source": "builtin"})

    for match in re.findall(r"([一-龥]{2,12})(附近|周边|一带|边上|这边)", text):
        name = match[0]
        if name not in seen:
            seen.add(name)
            candidates.append({"name": name, "source": "phrase"})

    resolved = []
    for item in candidates[:4]:
        geo = amap_geocode(item["name"])
        if geo.get("success"):
            resolved.append(
                {
                    "name": item["name"],
                    "formatted_name": geo.get("name", item["name"]),
                    "city": geo.get("city") or item["name"],
                    "adcode": geo.get("adcode"),
                    "latitude": geo.get("latitude"),
                    "longitude": geo.get("longitude"),
                    "source": item["source"],
                }
            )

    primary = resolved[0] if resolved else None
    return {
        "success": bool(primary),
        "primary": primary,
        "candidates": resolved,
    }


def smart_stop_order(city: str, stops: List[Dict[str, Any]]) -> Dict[str, Any]:
    city_geo = amap_geocode(city)
    if not city_geo.get("success"):
        return {"success": False, "message": city_geo.get("message", "城市定位失败"), "ordered_stops": stops}

    remaining = []
    for stop in stops:
        location = stop.get("location", "")
        if "," not in location:
            continue
        longitude, latitude = location.split(",", 1)
        try:
            enriched = {
                **stop,
                "_longitude": float(longitude),
                "_latitude": float(latitude),
            }
        except ValueError:
            continue
        remaining.append(enriched)

    if len(remaining) < 2:
        return {"success": True, "ordered_stops": stops}

    ordered = []
    current_longitude = city_geo.get("longitude") or remaining[0]["_longitude"]
    current_latitude = city_geo.get("latitude") or remaining[0]["_latitude"]

    while remaining:
        next_stop = min(
            remaining,
            key=lambda item: ((item["_longitude"] - current_longitude) ** 2 + (item["_latitude"] - current_latitude) ** 2),
        )
        remaining.remove(next_stop)
        current_longitude = next_stop["_longitude"]
        current_latitude = next_stop["_latitude"]
        ordered.append({key: value for key, value in next_stop.items() if not key.startswith("_")})

    return {"success": True, "ordered_stops": ordered}


def meal_planner(city: str, limit: int = 6, restaurants: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    restaurants = restaurants or restaurant_search(city, limit=limit).get("restaurants", [])
    meal_labels = ["早餐", "午餐", "晚餐"]
    meals = []
    for index, restaurant in enumerate(restaurants[:3]):
        meals.append(
            {
                "meal_type": meal_labels[index],
                "name": restaurant.get("name", ""),
                "description": restaurant.get("description", ""),
                "business_area": restaurant.get("business_area", city),
                "detail_url": restaurant.get("detail_url", "https://www.amap.com/"),
            }
        )
    return {"success": bool(meals), "city": city, "meals": meals}


TOOLS = [
    StructuredTool.from_function(
        func=web_search,
        name="web_search",
        description="搜索最新旅行资讯、景点开放信息、交通动态和攻略",
        args_schema=SearchInput,
    ),
    StructuredTool.from_function(
        func=weather_lookup,
        name="weather_lookup",
        description="根据城市名或 adcode 查询高德天气实况或预报",
        args_schema=WeatherInput,
    ),
    StructuredTool.from_function(
        func=trip_structurer,
        name="trip_structurer",
        description="将用户旅行需求整理为结构化参数",
        args_schema=TripStructurerInput,
    ),
    StructuredTool.from_function(
        func=hotel_search,
        name="hotel_search",
        description="根据目的地搜索酒店推荐线索和预订入口",
        args_schema=HotelSearchInput,
    ),
    StructuredTool.from_function(
        func=restaurant_search,
        name="restaurant_search",
        description="根据目的地搜索餐厅、美食和用餐线索",
        args_schema=RestaurantSearchInput,
    ),
    StructuredTool.from_function(
        func=attraction_search,
        name="attraction_search",
        description="根据目的地搜索热门景点和详情入口",
        args_schema=HotelSearchInput,
    ),
    StructuredTool.from_function(
        func=image_search,
        name="image_search",
        description="搜索景点或目的地的图片结果，适合前端展示",
        args_schema=ImageSearchInput,
    ),
    StructuredTool.from_function(
        func=route_plan,
        name="route_plan",
        description="基于起点和终点生成地图路线规划摘要与跳转链接",
        args_schema=RoutePlanInput,
    ),
    StructuredTool.from_function(
        func=place_resolver,
        name="place_resolver",
        description="解析模糊地点、片区或城市表达，输出更稳定的地点结果",
        args_schema=PlaceResolverInput,
    ),
    StructuredTool.from_function(
        func=smart_stop_order,
        name="smart_stop_order",
        description="对多景点进行顺路排序，减少重复折返",
        args_schema=StopOrderInput,
    ),
    StructuredTool.from_function(
        func=meal_planner,
        name="meal_planner",
        description="按城市生成早餐、午餐、晚餐建议，适合补全旅行体验",
        args_schema=RestaurantSearchInput,
    ),
]


def get_tool_by_name(name: str) -> StructuredTool:
    for tool in TOOLS:
        if tool.name == name:
            return tool
    raise KeyError(name)
