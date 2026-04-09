---
name: smart-stop-order
description: Reorder multiple attractions or stops into a more efficient visiting sequence. Use when the assistant has several POIs for one city and should reduce backtracking before generating a route, day plan, or citywalk suggestion.
---

# Smart Stop Order

Use this skill after attraction candidates are available and before presenting a route-like recommendation.

## Workflow

1. Start from the city anchor or a known origin.
2. Compare candidate stops by geographic proximity.
3. Build a lightweight nearest-neighbor visiting order.
4. Keep the ordered list small and practical for a single day or a short trip.
5. Surface the reordered stops back to route planning and final answer generation.

## Output Expectations

- Return an ordered stop list.
- Optimize for practical travel flow, not mathematical perfection.
- If coordinates are missing, fall back to the original order instead of inventing positions.

## Notes

- This skill is best for short city itineraries and citywalk-style plans.
- It should make route output feel more intentional without adding heavy optimization cost.
