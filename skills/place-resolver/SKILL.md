---
name: place-resolver
description: Resolve fuzzy place mentions, district names, nearby-area phrases, and city aliases in travel queries. Use when the assistant needs to turn natural-language location references into stable destinations, origins, or route anchors before weather, POI, hotel, or route tools run.
---

# Place Resolver

Use this skill when user input contains partial place names, nearby-area wording, or ambiguous location references.

## Workflow

1. Prefer explicit cities already present in the user message.
2. If the user uses phrases like `附近`、`周边`、`一带`、`边上`, extract the place phrase before the suffix.
3. Resolve the candidate through a geocoding tool before passing it to weather, POI, hotel, or route tools.
4. When multiple candidates exist, keep the first stable city-level result as primary and retain others as fallbacks.
5. If no place can be resolved confidently, ask a short follow-up instead of guessing.

## Output Expectations

- Return one primary resolved place when possible.
- Preserve city/adcode/coordinates when available.
- Keep the result lightweight so downstream tools can reuse it directly.

## Notes

- This skill is a guardrail for real-time tools.
- Prefer a stable city-level resolution over an over-specific but uncertain guess.
