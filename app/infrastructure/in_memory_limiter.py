import time
import threading
from collections import deque
from app.domain.ports import RateLimiter
from app.services.rate_limiter import _limiter_store

class InMemoryRateLimiter(RateLimiter):
    def __init__(self):
        self._limiter_store = _limiter_store
        self._lock = threading.Lock()

    def is_rate_limited(self, client_id: str, limit_tps: int) -> bool:
        now = time.time()
        with self._lock:
            if client_id not in self._limiter_store:
                self._limiter_store[client_id] = deque()
            history = self._limiter_store[client_id]
            # Prune requests older than 1 second
            while history and history[0] < now - 1.0:
                history.popleft()
                
            if len(history) >= limit_tps:
                return True
            history.append(now)
            return False

    def clear(self) -> None:
        with self._lock:
            self._limiter_store.clear()
