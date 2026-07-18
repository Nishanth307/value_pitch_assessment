import time
import threading
from collections import deque

# Global store for in-memory rate limiting: {client_id: deque([timestamps])}
_limiter_store = {}
_lock = threading.Lock()

class InMemoryRateLimiter:
    """Simple in-memory rate limiter using a sliding window of request timestamps."""
    def __init__(self):
        self._store = _limiter_store
        self._lock = _lock

    def is_rate_limited(self, client_id: str, limit_tps: int) -> bool:
        """
        Checks if a client has exceeded their TPS limit.
        Returns True if rate limited, False if allowed.
        """
        now = time.time()
        with self._lock:
            if client_id not in self._store:
                self._store[client_id] = deque()
            
            history = self._store[client_id]
            
            # Prune timestamps older than 1 second from the front
            while history and history[0] < now - 1.0:
                history.popleft()
                
            # If the number of requests in the last second exceeds limit_tps, they are limited
            if len(history) >= limit_tps:
                return True
                
            # Otherwise, log the current request timestamp and allow it
            history.append(now)
            return False

    def clear(self) -> None:
        """Clear all rate limit histories."""
        with self._lock:
            self._store.clear()
