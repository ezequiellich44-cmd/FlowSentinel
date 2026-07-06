import time
import math
import logging
from typing import Dict, Optional, Callable, Awaitable
from flowsentinel.models import PoolState, AnomalyCandidate

logger = logging.getLogger(__name__)

class ExponentialWeightedRegression:
    def __init__(self, lambda_decay: float = 0.9):
        self.lambda_decay = lambda_decay
        self.sw = 0.0
        self.sx = 0.0
        self.sy = 0.0
        self.sxx = 0.0
        self.sxy = 0.0
        self.initialized = False

    def update(self, x: float, y: float) -> None:
        if not self.initialized:
            self.sw = 1.0
            self.sx = x
            self.sy = y
            self.sxx = x * x
            self.sxy = x * y
            self.initialized = True
        else:
            self.sw = self.lambda_decay * self.sw + 1.0
            self.sx = self.lambda_decay * self.sx + x
            self.sy = self.lambda_decay * self.sy + y
            self.sxx = self.lambda_decay * self.sxx + (x * x)
            self.sxy = self.lambda_decay * self.sxy + (x * y)

    def get_coefficients(self) -> Optional[tuple[float, float]]:
        """
        Returns (slope, intercept) of the regression line y = slope * x + intercept.
        """
        if not self.initialized or self.sw <= 1.0:
            return None
            
        denominator = self.sw * self.sxx - (self.sx * self.sx)
        if abs(denominator) < 1e-9:
            return None
            
        slope = (self.sw * self.sxy - self.sx * self.sy) / denominator
        intercept = (self.sy - slope * self.sx) / self.sw
        return slope, intercept


class LiquidityPredictiveModel:
    def __init__(self,
                 lambda_decay: float = 0.9,
                 depletion_time_threshold_seconds: float = 60.0,
                 on_anomaly: Optional[Callable[[AnomalyCandidate], Awaitable[None]]] = None):
        self.lambda_decay = lambda_decay
        self.depletion_time_threshold = depletion_time_threshold_seconds
        self.on_anomaly = on_anomaly
        # Map of pool_address -> ExponentialWeightedRegression for reserve0
        self.regressions: Dict[str, ExponentialWeightedRegression] = {}
        self.start_times: Dict[str, float] = {}

    async def process_pool_state(self, state: PoolState) -> None:
        pool = state.pool_address
        now = time.time()
        
        if pool not in self.start_times:
            self.start_times[pool] = now
            self.regressions[pool] = ExponentialWeightedRegression(lambda_decay=self.lambda_decay)
            
        elapsed = now - self.start_times[pool]
        # Track reserve0 as proxy for pool liquidity
        y = state.reserve0
        
        reg = self.regressions[pool]
        reg.update(elapsed, y)
        
        coeffs = reg.get_coefficients()
        if not coeffs:
            return
            
        slope, intercept = coeffs
        
        # If slope is negative, liquidity is depletion/decreasing
        if slope < -0.01:
            # Predict when reserve0 will fall below 10% of its initial value (represented by intercept at elapsed=0)
            target_liquidity = 0.1 * intercept
            # y_target = slope * t_target + intercept
            # t_target = (y_target - intercept) / slope
            t_target = (target_liquidity - intercept) / slope
            time_to_depletion = t_target - elapsed
            
            logger.info("Pool %s | Slope: %.4f | Est. depletion time: %.2f seconds", pool, slope, time_to_depletion)

            if 0 < time_to_depletion < self.depletion_time_threshold:
                logger.warning("CRITICAL LIQUIDITY DEPLETION PREDICTED for pool %s: %.2f seconds left", pool, time_to_depletion)
                
                anomaly = AnomalyCandidate(
                    anomaly_id=f"pred_{int(time.time())}_{pool[:6]}",
                    pattern_type="liquidity_depletion_prediction",
                    severity="high" if time_to_depletion < 20 else "medium",
                    pool_address=pool,
                    related_txs=[],
                    timestamp=now,
                    metadata={
                        "slope": slope,
                        "intercept": intercept,
                        "current_elapsed": elapsed,
                        "time_to_depletion": time_to_depletion,
                        "threshold": self.depletion_time_threshold,
                        "current_liquidity": y
                    }
                )
                if self.on_anomaly:
                    await self.on_anomaly(anomaly)
