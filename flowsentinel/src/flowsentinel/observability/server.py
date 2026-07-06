from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(title="FlowSentinel Observability Exporter")

# Expose Prometheus /metrics endpoint via ASGIApp
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.get("/health")
async def health():
    return {"status": "healthy"}
