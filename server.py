"""
mock_servers.py — Lightweight mock backend servers for proxy testing.

Each server simulates one of the TARGET_HOSTS in the Locust file.
Their only job is to respond correctly and fast so that the proxy
under test is the sole bottleneck.

Usage (run each in a separate terminal):
    python mock_servers.py --service a --port 8181
    python mock_servers.py --service b --port 8282
    python mock_servers.py --service c --port 8383

Then point your proxy at these ports and Locust at the proxy.
"""

import argparse
import logging
import random
import time
import uvicorn

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Mock backend server")
parser.add_argument(
    "--service",
    default="a",
    required=True,
    help="Which service identity to adopt (a / b / c / ...)",
)
parser.add_argument(
    "--port",
    type=int,
    default=8181,
    help="Port to listen on (default: 8181)",
)
parser.add_argument(
    "--host",
    default="0.0.0.0",
    help="Bind address (default: 0.0.0.0)",
)
parser.add_argument(
    "--latency-min",
    type=float,
    default=0.005,
    dest="latency_min",
    help="Minimum simulated processing latency in seconds (default: 0.005)",
)
parser.add_argument(
    "--latency-max",
    type=float,
    default=0.030,
    dest="latency_max",
    help="Maximum simulated processing latency in seconds (default: 0.030)",
)
parser.add_argument(
    "--error-rate",
    type=float,
    default=0.0,
    dest="error_rate",
    help="Fraction of requests to fail with 500 (0.0–1.0, default: 0.0)",
)

args = parser.parse_args()

SERVICE_ID = args.service.upper()
SERVICE_NAME = f"service-{args.service}"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format=f"[{SERVICE_NAME}] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(SERVICE_NAME)

app = FastAPI(title=f"Mock backend — {SERVICE_NAME}", docs_url=None, redoc_url=None)

# In-memory counters (per-process, reset on restart)
_stats: dict[str, int] = {
    "requests_total": 0,
    "requests_success": 0,
    "requests_error": 0,
}


def _simulate_work() -> None:
    """Block for a realistic processing duration."""
    delay = random.uniform(args.latency_min, args.latency_max)
    time.sleep(delay)


def _maybe_inject_error() -> bool:
    """Return True if this request should be failed intentionally."""
    return args.error_rate > 0 and random.random() < args.error_rate


def _base_headers() -> dict:
    return {
        "X-Service-Id": SERVICE_ID,
        "X-Service-Name": SERVICE_NAME,
    }


# ---------------------------------------------------------------------------
# Middleware — count every request
# ---------------------------------------------------------------------------

@app.middleware("http")
async def count_requests(request: Request, call_next):
    _stats["requests_total"] += 1
    response = await call_next(request)
    if response.status_code < 500:
        _stats["requests_success"] += 1
    else:
        _stats["requests_error"] += 1
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """
    Health check — always 200 unless --error-rate forces a fault.
    The Locust task expects: { "status": "ok" }
    """
    _simulate_work()
    if _maybe_inject_error():
        log.warning("Injecting 500 on /health")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "service": SERVICE_NAME},
            headers=_base_headers(),
        )
    log.info('GET /health [200]')
    return JSONResponse(
        content={"status": "ok", "service": SERVICE_NAME},
        headers=_base_headers(),
    )


@app.get("/api/resource/{resource_id}")
async def get_resource(resource_id: int):
    """
    Resource fetch.
    - IDs 1–900   → 200 with a synthetic payload
    - IDs 901–1000 → 404 (expected by the Locust task)
    - Random 500 if --error-rate is set
    """
    _simulate_work()

    if _maybe_inject_error():
        log.warning("Injecting 500 on /api/resource/%d", resource_id)
        return JSONResponse(
            status_code=500,
            content={"error": "internal server error", "service": SERVICE_NAME},
            headers=_base_headers(),
        )

    if resource_id > 900:
        log.info('GET /api/resource/{} [404]'.format(resource_id))
        return JSONResponse(
            status_code=404,
            content={"error": "not found", "resource_id": resource_id},
            headers=_base_headers(),
        )

    log.info('GET /api/resource/{} [200]'.format(resource_id))
    return JSONResponse(
        content={
            "resource_id": resource_id,
            "service": SERVICE_NAME,
            "value": round(random.random() * 1000, 2),
            "tags": random.sample(["alpha", "beta", "gamma", "delta", "epsilon"], k=2),
        },
        headers=_base_headers(),
    )


@app.post("/api/events")
async def post_event(request: Request):
    """
    Event ingestion — accepts any JSON body, echoes it back with a timestamp.
    Returns 202 Accepted (the Locust task accepts 200/201/202).
    """
    _simulate_work()

    if _maybe_inject_error():
        log.warning("Injecting 500 on /api/events")
        return JSONResponse(
            status_code=500,
            content={"error": "internal server error"},
            headers=_base_headers(),
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    log.info('POST /api/events [202]')
    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "service": SERVICE_NAME,
            "received": body,
            "server_ts": time.time(),
        },
        headers=_base_headers(),
    )


@app.get("/_stats")
async def stats():
    """
    Internal stats endpoint — not called by Locust, useful for observing
    how many requests the proxy forwarded to each backend.
    """
    log.info('GET /_stats [200]')
    return JSONResponse(
        content={
            "service": SERVICE_NAME,
            "uptime_note": "counters reset on restart",
            **_stats,
        },
        headers=_base_headers(),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(
        "Starting %s on %s:%d | latency=[%.0fms–%.0fms] error_rate=%.0f%%",
        SERVICE_NAME,
        args.host,
        args.port,
        args.latency_min * 1000,
        args.latency_max * 1000,
        args.error_rate * 100,
    )
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",     # suppress uvicorn access logs; our middleware logs instead
        access_log=False,
    )
