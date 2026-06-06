# LLM Gateway — Archived

> Archived: 2026-06-05
> Replaced by: NewAPI (:3000)
> LOC: 1453
> Reason: Never deployed to production. NewAPI covers all routing, key management,
  and fallback functionality with a proven production track record.

## History

LLM Gateway was built as a kairon package to manage LLM API routing.
It was never connected to the runtime matrix or health monitoring.
NewAPI (:3000) was deployed as an alternative and has been handling
all API traffic since.

## Recovery

If NewAPI becomes unavailable, LLM Gateway can be re-activated:
1. Register in ~/runtime/matrix.yaml
2. Add to health-scan.sh
3. Wire up environment variables for provider API keys
