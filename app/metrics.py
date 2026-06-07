import time
import threading
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.routing import Route


class MetricsCollector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._request_count: defaultdict[str, int] = defaultdict(int)
        self._request_duration: defaultdict[str, list[float]] = defaultdict(lambda: [])
        self._error_count: defaultdict[str, int] = defaultdict(int)
        self._active_requests: int = 0
        self._start_time = time.time()

    def record_request(self, method: str, path: str, status: int, duration_ms: float):
        key = f"{method} {path}"
        self._request_count[key] += 1
        self._request_duration[key].append(duration_ms)
        if status >= 400:
            self._error_count[f"{status}"] += 1

    def increment_active(self):
        self._active_requests += 1

    def decrement_active(self):
        self._active_requests = max(0, self._active_requests - 1)

    def get_prometheus_metrics(self) -> str:
        lines = []
        lines.append("# HELP http_requests_total Total HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        for key, count in self._request_count.items():
            method, path = key.split(" ", 1)
            lines.append(f'http_requests_total{{method="{method}",path="{path}"}} {count}')

        lines.append("# HELP http_request_duration_seconds HTTP request duration")
        lines.append("# TYPE http_request_duration_seconds histogram")
        for key, durations in self._request_duration.items():
            if durations:
                method, path = key.split(" ", 1)
                avg_ms = sum(durations) / len(durations)
                p99_ms = sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0]
                lines.append(f'http_request_duration_seconds{{method="{method}",path="{path}",quantile="0.5"}} {avg_ms / 1000:.3f}')
                lines.append(f'http_request_duration_seconds{{method="{method}",path="{path}",quantile="0.99"}} {p99_ms / 1000:.3f}')

        lines.append("# HELP http_errors_total HTTP errors by status code")
        lines.append("# TYPE http_errors_total counter")
        for status, count in self._error_count.items():
            lines.append(f'http_errors_total{{status="{status}"}} {count}')

        lines.append("# HELP http_active_requests Active HTTP requests")
        lines.append("# TYPE http_active_requests gauge")
        lines.append(f"http_active_requests {self._active_requests}")

        lines.append("# HELP uptime_seconds Process uptime in seconds")
        lines.append("# TYPE uptime_seconds gauge")
        lines.append(f"uptime_seconds {time.time() - self._start_time:.0f}")

        return "\n".join(lines) + "\n"


metrics = MetricsCollector()


def setup_metrics(app: FastAPI):
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        metrics.increment_active()
        start_time = time.time()
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            path = request.url.path
            for route in app.routes:
                if isinstance(route, Route) and route.path_regex.match(request.url.path):
                    path = route.path
                    break
            metrics.record_request(request.method, path, response.status_code, duration_ms)
            return response
        except Exception:
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_request(request.method, request.url.path, 500, duration_ms)
            raise
        finally:
            metrics.decrement_active()

    @app.get("/metrics", include_in_schema=False)
    def get_metrics():
        return PlainTextResponse(content=metrics.get_prometheus_metrics(), media_type="text/plain")
