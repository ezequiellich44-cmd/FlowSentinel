import httpx
import logging
from flowsentinel.alerting.base import AlertSink
from flowsentinel.llm.schemas import AnomalyRiskAssessment

logger = logging.getLogger(__name__)

class TelegramSink(AlertSink):
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token
        self.chat_id = chat_id

    async def send(self, assessment: AnomalyRiskAssessment, narrative: str) -> None:
        if not self.token or not self.chat_id:
            logger.debug("Telegram credentials not fully configured, skipping alert")
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        text_message = (
            f"🚨 *FlowSentinel Alert* ({assessment.severity.upper()})\n\n"
            f"*Rationale:*\n{assessment.rationale}\n\n"
            f"*Action:*\n{assessment.recommended_action}\n\n"
            f"*Report:*\n{narrative}"
        )
        payload = {
            "chat_id": self.chat_id,
            "text": text_message,
            "parse_mode": "Markdown"
        }

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            logger.info("Sent Telegram alert successfully")
        except Exception as e:
            logger.error("Failed to send Telegram alert: %s", str(e))
