import time
import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from flowsentinel.alerting.base import AlertSink
from flowsentinel.llm.schemas import AnomalyRiskAssessment

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Raised when the circuit breaker is open and blocks outgoing requests."""
    pass

class WebhookSink(AlertSink):
    def __init__(self, url: str | None = None, circuit_breaker_cooldown: float = 30.0, max_failures: int = 5):
        self.url = url
        self.cooldown = circuit_breaker_cooldown
        self.max_failures = max_failures
        self.failures_count = 0
        self.circuit_open_until = 0.0

    async def send(self, assessment: AnomalyRiskAssessment, narrative: str) -> None:
        if not self.url:
            logger.debug("Webhook URL not configured, skipping alert")
            return

        now = time.time()
        if now < self.circuit_open_until:
            logger.warning("Circuit breaker is OPEN. Skipping webhook alert.")
            raise CircuitBreakerOpenException("Circuit is open")

        try:
            await self._send_with_retry(assessment, narrative)
            # Reset failure count on successful webhook delivery
            self.failures_count = 0
        except Exception as e:
            self.failures_count += 1
            logger.error("Webhook execution failed. Failures: %d/%d. Error: %s",
                         self.failures_count, self.max_failures, str(e))
            if self.failures_count >= self.max_failures:
                self.circuit_open_until = time.time() + self.cooldown
                logger.error("Circuit breaker tripped! Webhook alerts disabled for %.1f seconds", self.cooldown)
            raise e

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True
    )
    async def _send_with_retry(self, assessment: AnomalyRiskAssessment, narrative: str) -> None:
        payload = {
            "severity": assessment.severity,
            "rationale": assessment.rationale,
            "recommended_action": assessment.recommended_action,
            "narrative": narrative
        }
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(self.url, json=payload)
            response.raise_for_status()
