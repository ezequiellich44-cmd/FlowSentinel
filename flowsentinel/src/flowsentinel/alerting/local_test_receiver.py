import logging
from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)
app = FastAPI(title="FlowSentinel Webhook Receiver")

# Global list of received alert payloads
received_alerts = []

class WebhookPayload(BaseModel):
    severity: str
    rationale: str
    recommended_action: str
    narrative: str

@app.post("/webhook")
async def receive_webhook(payload: WebhookPayload):
    received_alerts.append(payload.model_dump())
    logger.info("Received webhook alert: severity=%s, rationale=%.50s...",
                payload.severity, payload.rationale)
    return {"status": "ok", "received_count": len(received_alerts)}

@app.get("/alerts")
async def get_alerts():
    return received_alerts

@app.post("/clear")
async def clear_alerts():
    received_alerts.clear()
    logger.info("Cleared webhook alerts")
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok"}
