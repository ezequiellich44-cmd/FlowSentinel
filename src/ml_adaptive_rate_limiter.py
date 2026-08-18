\"\"\"
FlowSentinel ML-Driven Adaptive Rate Limiter & Circuit Breaker
Dynamically adjusts token-bucket rates based on LLM swarm latency and failure signals.
\"\"\"

import time
import math
from typing import Dict, Any

class AdaptiveRateLimiter:
    def __init__(self, base_rate: float = 100.0, burst_capacity: int = 200):
        self.capacity = burst_capacity
        self.tokens = float(burst_capacity)
        self.fill_rate = base_rate
        self.last_update = time.time()
        self.adaptive_multiplier = 1.0

    def inspect_and_consume(self, tokens_required: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        
        # Replenish tokens dynamically
        self.tokens = min(self.capacity, self.tokens + elapsed * (self.fill_rate * self.adaptive_multiplier))
        
        if self.tokens >= tokens_required:
            self.tokens -= tokens_required
            return True
        return False

    def report_congestion(self, error_rate: float) -> None:
        if error_rate > 0.15:
            self.adaptive_multiplier = max(0.2, 1.0 - error_rate)
        else:
            self.adaptive_multiplier = min(1.5, self.adaptive_multiplier + 0.05)