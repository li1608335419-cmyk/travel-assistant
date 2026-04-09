from datetime import UTC, date, datetime

from tools.travel_tools import (
    _extract_area_hint,
    _extract_price_hint,
    extract_city_from_text,
    get_current_date_info,
    meal_planner,
    place_resolver,
    resolve_weather_target,
    smart_stop_order,
    trip_structurer,
)


def test_trip_structurer_extracts_basic_fields():
    result = trip_structurer("五一从上海出发去杭州玩2天，预算3000左右")
    trip = result["structured_trip"]
    assert trip["origin"] == "上海"
    assert trip["destination"] == "杭州"
    assert trip["days"] == 2
    assert "3000" in trip["budget"]


def test_trip_structurer_merges_selected_and_inferred_skills():
    result = trip_structurer("想去成都吃点好的，顺便拍照出片", skills=["budget_optimizer"])
    trip = result["structured_trip"]
    assert "budget_optimizer" in trip["skills"]
    assert "food_hunter" in trip["skills"]
    assert "photo_route" in trip["skills"]


def test_extract_hotel_hints():
    assert _extract_price_hint("西湖边高分酒店，¥568起，步行到湖边 8 分钟") == "¥568"
    assert _extract_area_hint("杭州西湖商圈高分酒店，交通方便", "杭州", ["西湖", "东站"]) == "西湖"


def test_resolve_weather_target_outside_window():
    result = resolve_weather_target("上海五一的天气怎么样", today=date(2026, 4, 8))
    assert result["label"] == "2026年5月1日"
    assert result["within_forecast_window"] is False


def test_extract_city_from_weather_question():
    assert extract_city_from_text("今天杭州天气怎么样") == "杭州"


def test_get_current_date_info():
    result = get_current_date_info(datetime(2026, 4, 8, 10, 0, tzinfo=UTC))
    assert result["display_date"] == "2026年4月8日"


def test_place_resolver(monkeypatch):
    monkeypatch.setattr(
        "tools.travel_tools.amap_geocode",
        lambda place: {
            "success": True,
            "name": f"{place} resolved",
            "city": "杭州",
            "adcode": "330100",
            "latitude": 30.27,
            "longitude": 120.15,
        },
    )
    result = place_resolver("住在西湖附近方便吗")
    assert result["success"] is True
    assert result["primary"]["city"] == "杭州"


def test_smart_stop_order(monkeypatch):
    monkeypatch.setattr(
        "tools.travel_tools.amap_geocode",
        lambda city: {"success": True, "longitude": 120.10, "latitude": 30.20},
    )
    result = smart_stop_order(
        "杭州",
        [
            {"name": "A", "location": "120.30,30.30"},
            {"name": "B", "location": "120.12,30.22"},
            {"name": "C", "location": "120.18,30.24"},
        ],
    )
    assert result["success"] is True
    assert result["ordered_stops"][0]["name"] == "B"


def test_meal_planner():
    result = meal_planner(
        "杭州",
        restaurants=[
            {"name": "早餐店", "description": "粥和包子", "business_area": "西湖", "detail_url": "https://example.com/a"},
            {"name": "午餐馆", "description": "杭帮菜", "business_area": "湖滨", "detail_url": "https://example.com/b"},
            {"name": "晚餐店", "description": "夜景餐厅", "business_area": "钱江新城", "detail_url": "https://example.com/c"},
        ],
    )
    assert result["success"] is True
    assert [item["meal_type"] for item in result["meals"]] == ["早餐", "午餐", "晚餐"]
