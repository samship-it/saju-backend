import time
from typing import Callable, Any

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = time.time()

    def call(self, func: Callable, fallback_func: Callable, *args, **kwargs) -> tuple[Any, bool]:
        now = time.time()

        # OPEN 상태에서 서킷 쿨다운 시간 체크
        if self.state == 'OPEN':
            if now - self.last_state_change > self.recovery_time:
                self.state = 'HALF-OPEN'
            else:
                # 서킷 열림 -> 즉시 폴백(Fallback) 반환
                return fallback_func(*args, **kwargs), True

        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF-OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result, False
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.last_state_change = time.time()
            return fallback_func(*args, **kwargs), True

# 글로벌 Gemini 서킷 브레이커 인스턴스
gemini_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_time=30)
