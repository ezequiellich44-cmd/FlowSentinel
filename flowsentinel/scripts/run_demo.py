import os
import sys

# Force identical module import resolution for same-process uvicorn
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import time
import asyncio
import httpx
import uvicorn
import structlog
from typing import List

# Setup structured logging
from flowsentinel.observability.logging_setup import setup_logging
setup_logging()
logger = structlog.get_logger("flowsentinel.demo")

# Core flowsentinel imports
from flowsentinel.models import TxIntent, PoolState
from flowsentinel.config import settings
from flowsentinel.storage.redis_client import RedisClient
from flowsentinel.storage.timescale import TimescaleClient
from flowsentinel.detection.sandwich_detector import SandwichDetector
from flowsentinel.detection.liquidity_scorer import LiquidityScorer
from flowsentinel.detection.predictive import LiquidityPredictiveModel
from flowsentinel.llm.classifier import RiskClassifier
from flowsentinel.llm.narrative import NarrativeGenerator
from flowsentinel.pipeline import PipelineOrchestrator

# Simple Mocks for DB and Redis to ensure demo runs 100% offline/reliably
class MemoryRedisMock:
    def __init__(self):
        self.seen = set()
    async def is_duplicate(self, tx_hash: str, ttl_seconds: int = 60) -> bool:
        if tx_hash in self.seen:
            return True
        self.seen.add(tx_hash)
        return False
    async def close(self) -> None:
        pass

class MemoryDBMock:
    async def execute(self, query: str, *args):
        pass
    async def fetch(self, query: str, *args):
        return []
    async def close(self) -> None:
        pass

async def wait_for_port(url: str, timeout: float = 10.0):
    start = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start < timeout:
            try:
                resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for server at {url}")

async def run_demo():
    logger.info("Starting FlowSentinel Phase 3 E2E Demo...")

    # Port configurations
    receiver_port = 8002
    obs_port = 8000
    receiver_url = f"http://127.0.0.1:{receiver_port}"
    obs_url = f"http://127.0.0.1:{obs_port}"

    # 1. Start uvicorn webhook receiver programmatically in same process (for shared memory)
    logger.info("Launching local_test_receiver on port 8002...")
    from flowsentinel.alerting.local_test_receiver import app as rec_app
    config_rec = uvicorn.Config(
        rec_app, 
        host="127.0.0.1", 
        port=receiver_port,
        log_level="warning"
    )
    server_rec = uvicorn.Server(config_rec)
    task_rec = asyncio.create_task(server_rec.serve())

    # 2. Start uvicorn observability exporter programmatically in same process (for metrics shared memory)
    logger.info("Launching observability server on port 8000...")
    from flowsentinel.observability.server import app as obs_app
    config_obs = uvicorn.Config(
        obs_app, 
        host="127.0.0.1", 
        port=obs_port,
        log_level="warning"
    )
    server_obs = uvicorn.Server(config_obs)
    task_obs = asyncio.create_task(server_obs.serve())

    # Wait for servers to wake up and start responding
    logger.info("Waiting for background servers to start responding...")
    await wait_for_port(receiver_url)
    await wait_for_port(obs_url)
    logger.info("Background servers are ready")

    # Configure Webhook URL
    settings.webhook_url = f"{receiver_url}/webhook"

    try:
        # Clear receiver alerts first
        async with httpx.AsyncClient() as client:
            await client.post(f"{receiver_url}/clear")

        # 3. Instantiate pipeline orchestrator with memory mocks for 100% offline stability
        redis_client = MemoryRedisMock()
        timescale_client = MemoryDBMock()
        risk_classifier = RiskClassifier()
        narrative_generator = NarrativeGenerator()

        # Placeholders for detectors, callbacks are bound inside PipelineOrchestrator
        sandwich_detector = SandwichDetector(window_seconds=3.0, on_anomaly=lambda x: None)
        liquidity_scorer = LiquidityScorer(test_swap_size=10.0, impact_threshold=0.08, on_anomaly=lambda x: None)
        predictive_model = LiquidityPredictiveModel(lambda_decay=0.85, depletion_time_threshold_seconds=0.0, on_anomaly=lambda x: None)

        orchestrator = PipelineOrchestrator(
            redis_client=redis_client,
            timescale_client=timescale_client,
            sandwich_detector=sandwich_detector,
            liquidity_scorer=liquidity_scorer,
            predictive_model=predictive_model,
            risk_classifier=risk_classifier,
            narrative_generator=narrative_generator,
            backpressure_limit=100
        )

        await orchestrator.start()
        logger.info("Orchestration pipeline started")

        # 4. Deliberately inject 3 valid sandwich sequences and 1 liquidity drop sequence
        pool_a = "0xPoolA"
        now = time.time()

        logger.info("Injecting Sandwich Sequence 1...")
        s1_front = TxIntent(tx_hash="s1_front", gas_price=150.0, gas_limit=150000, target_address=pool_a, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=now + 1.0, nonce=100)
        s1_victim = TxIntent(tx_hash="s1_victim", gas_price=50.0, gas_limit=150000, target_address=pool_a, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=now + 1.1, nonce=500)
        s1_back = TxIntent(tx_hash="s1_back", gas_price=45.0, gas_limit=150000, target_address=pool_a, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=now + 1.2, nonce=101)
        
        await orchestrator.queue.put((s1_front, asyncio.Semaphore(10)))
        await orchestrator.queue.put((s1_victim, asyncio.Semaphore(10)))
        await orchestrator.queue.put((s1_back, asyncio.Semaphore(10)))

        logger.info("Injecting Sandwich Sequence 2...")
        s2_front = TxIntent(tx_hash="s2_front", gas_price=160.0, gas_limit=150000, target_address=pool_a, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=now + 5.0, nonce=200)
        s2_victim = TxIntent(tx_hash="s2_victim", gas_price=55.0, gas_limit=150000, target_address=pool_a, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=now + 5.1, nonce=600)
        s2_back = TxIntent(tx_hash="s2_back", gas_price=48.0, gas_limit=150000, target_address=pool_a, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=now + 5.2, nonce=201)

        await orchestrator.queue.put((s2_front, asyncio.Semaphore(10)))
        await orchestrator.queue.put((s2_victim, asyncio.Semaphore(10)))
        await orchestrator.queue.put((s2_back, asyncio.Semaphore(10)))

        logger.info("Injecting Sandwich Sequence 3...")
        s3_front = TxIntent(tx_hash="s3_front", gas_price=170.0, gas_limit=150000, target_address=pool_a, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=now + 10.0, nonce=300)
        s3_victim = TxIntent(tx_hash="s3_victim", gas_price=60.0, gas_limit=150000, target_address=pool_a, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=now + 10.1, nonce=700)
        s3_back = TxIntent(tx_hash="s3_back", gas_price=50.0, gas_limit=150000, target_address=pool_a, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=now + 10.2, nonce=301)

        await orchestrator.queue.put((s3_front, asyncio.Semaphore(10)))
        await orchestrator.queue.put((s3_victim, asyncio.Semaphore(10)))
        await orchestrator.queue.put((s3_back, asyncio.Semaphore(10)))

        logger.info("Injecting Liquidity Drop Sequence...")
        p1 = PoolState(pool_address=pool_a, exchange_name="UniswapV3", reserve0=200.0, reserve1=600000.0, token0="WETH", token1="USDT", timestamp=now + 15.0)
        p2 = PoolState(pool_address=pool_a, exchange_name="UniswapV3", reserve0=50.0, reserve1=150000.0, token0="WETH", token1="USDT", timestamp=now + 16.0)

        await orchestrator.queue.put((p1, asyncio.Semaphore(5)))
        await orchestrator.queue.put((p2, asyncio.Semaphore(5)))

        # 5. Wait for the orchestrator to drain the queue completely
        logger.info("Waiting for queue to drain...")
        while not orchestrator.queue.empty():
            await asyncio.sleep(0.5)
        # Extra buffer to complete processing of the last event
        await asyncio.sleep(2.0)

        # Stop orchestrator
        await orchestrator.stop()

        # 6. Verify programmatically that alerts are received via HTTP GET /alerts
        logger.info("Querying local_test_receiver alerts...")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{receiver_url}/alerts")
            resp.raise_for_status()
            alerts = resp.json()

        logger.info("Querying Prometheus metrics...")
        async with httpx.AsyncClient() as client:
            metrics_resp = await client.get(f"{obs_url}/metrics")
            metrics_text = metrics_resp.text
            
        # Programmatic Assertions
        logger.info("Running programmatic checks...")
        
        # We check metrics and webhook alerts
        assert len(alerts) == 4, f"Expected exactly 4 webhooks, got {len(alerts)}"
        
        # Verify metrics exist in the local registry
        from prometheus_client import generate_latest, REGISTRY
        local_metrics = generate_latest(REGISTRY).decode("utf-8")
        assert "events_ingested_total" in local_metrics, "events_ingested_total metric not found"
        assert "anomalies_detected_total" in local_metrics, "anomalies_detected_total metric not found"
        assert "pipeline_latency_seconds" in local_metrics, "pipeline_latency_seconds metric not found"
        
        print("\n=======================================================")
        print("4/4 anomalías detectadas, clasificadas y alertadas — OK")
        print("=======================================================\n")
        
        # Clean up background servers
        server_rec.should_exit = True
        server_obs.should_exit = True
        await asyncio.gather(task_rec, task_obs, return_exceptions=True)
        sys.exit(0)

    except Exception as e:
        logger.exception("Demo run failed with exception")
        server_rec.should_exit = True
        server_obs.should_exit = True
        await asyncio.gather(task_rec, task_obs, return_exceptions=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_demo())
