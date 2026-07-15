# Backward compatibility layer for legacy test suite
import threading

_limiter_store = {}
_lock = threading.Lock()
