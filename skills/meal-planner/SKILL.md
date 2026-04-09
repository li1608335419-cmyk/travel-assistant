---
name: meal-planner
description: Add meal planning into travel recommendations by pairing destinations, attractions, and local areas with breakfast, lunch, and dinner suggestions. Use when the assistant should make an itinerary feel more complete and lifestyle-oriented rather than only listing sights.
---

# Meal Planner

Use this skill when destination or attraction recommendations would benefit from food guidance.

## Workflow

1. Resolve the destination city first.
2. Fetch restaurant or food POIs for the destination.
3. Turn the results into simple meal slots such as `早餐`、`午餐`、`晚餐`.
4. Prefer restaurants near the recommended activity area when that context exists.
5. Keep the suggestions concise and route-friendly.

## Output Expectations

- Return a short meal plan with meal type, place name, area, and a map/detail link.
- Use meal suggestions to complement, not overwhelm, the attraction plan.
- If food data is weak, skip confidently rather than fabricating restaurant details.

## Notes

- This skill is especially useful for citywalk, weekend trip, and family-friendly planning.
- It can also be used to enrich recommendation cards in the frontend.
