# Pass 111 — Runtime observability

## Scope

Pass 111 adds a shared operational observability boundary around the complete Crow Platform ASGI surface.
It does not add an external metrics stack, tracing backend or alert manager.

## Runtime contract

The production `crow-workbench` entry point now serves `crow_deployment.runtime_app:app`. That wrapper
keeps the existing Platform shell intact and adds:

- one `X-Request-ID` on every HTTP response;
- preservation of a caller-supplied request id only when it matches the bounded safe character set;
- generated UUID request ids for missing or unsafe values;
- one JSON request event on stdout containing timestamp, request id, method, path, status and duration;
- exception type on request events that escape the application;
- `/ready`, distinct from the existing `/health` liveness endpoint.

Query strings, request bodies, cookies, authorization headers and client addresses are deliberately not
written to the request event.

## Readiness

`/health` remains process liveness. `/ready` returns HTTP 200 only while both configured persistent
roots exist, are directories and are readable/writable/executable by the running process. It returns
HTTP 503 with per-root state otherwise.

Docker Compose now uses `/ready` for the Platform container healthcheck. Caddy therefore waits for a
runtime that can access its persistent Platform state rather than merely a live Python process.

## Logging

`CROW_LOG_LEVEL` defaults to `INFO`. Runtime request events are JSON on stdout and remain subject to
the bounded Docker `json-file` limits introduced by Pass 109/110.

## Evidence gate

The pass is not review-ready until CI verifies formatting, lint, typing, the full test suite, deployment
operations, the container readiness endpoint, request correlation and the existing end-to-end HTTPS
route.

## Non-goals

- Prometheus/OpenTelemetry export;
- centralized log shipping;
- alerting or dashboards;
- distributed trace propagation beyond the HTTP request id;
- dependency or base-image locking.
