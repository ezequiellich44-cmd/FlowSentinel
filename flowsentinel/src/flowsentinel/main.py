import asyncio
import logging
import sys
import time
from flowsentinel.config import settings
from flowsentinel.storage.redis_client import RedisClient
from flowsentinel.storage.timescale import TimescaleClient
from flowsentinel.feeds.simulated import SimulatedMempoolFeed, SimulatedLiquidityFeed
from flowsentinel.detection.sandwich_detector import SandwichDetector
from flowsentinel.detection.liquidity_scorer import LiquidityScorer
from flowsentinel.detection.predictive import LiquidityPredictiveModel
from flowsentinel.llm.classifier import RiskClassifier
from flowsentinel.llm.narrative import NarrativeGenerator
from flowsentinel.pipeline import PipelineOrchestrator

from flowsentinel.observability.logging_setup import setup_logging
import structlog

setup_logging()
logger = structlog.get_logger("flowsentinel.main")

async def main():
    logger.info("Initializing FlowSentinel Watchtower...")
    
    # 1. Initialize storage clients
    redis_client = RedisClient(settings.redis_url)
    timescale_client = TimescaleClient(settings.database_url)
    
    # Try connecting, fall back gracefully if Docker services are not running
    try:
        await redis_client.connect()
        logger.info("Successfully connected to Redis.")
    except Exception as e:
        logger.warning("Could not connect to Redis: %s. Using in-memory fallback for deduplication.", str(e))
        # Add simple in-memory fallback mock to prevent runtime crashes
        class MemoryRedisMock:
            def __init__(self):
                self.seen = set()
            async def is_duplicate(self, tx_hash: str, ttl_seconds: int = 60) -> bool:
                if tx_hash in self.seen:
                    return True
                self.seen.add(tx_hash)
                return False
        redis_client = MemoryRedisMock()

    try:
        await timescale_client.connect()
        logger.info("Successfully connected to TimescaleDB.")
        # Attempt to run migrations
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        migration_path = os.path.join(current_dir, "storage", "migrations", "001_init.sql")
        await timescale_client.run_migrations(migration_path)
    except Exception as e:
        logger.warning("Could not connect to TimescaleDB: %s. Continuing with database writes skipped.", str(e))
        # Add simple fallback to prevent crashes
        class MemoryDBMock:
            async def execute(self, query: str, *args):
                pass
            async def fetch(self, query: str, *args):
                return []
        timescale_client = MemoryDBMock()

    # 2. Setup classifier and narrative generators
    risk_classifier = RiskClassifier()
    narrative_generator = NarrativeGenerator()

    # Callback when detectors identify an anomaly
    async def on_anomaly_detected(anomaly):
        logger.warning("\n[ANOMALY CANDIDATE DETECTED] Type: %s | Pool: %s", anomaly.pattern_type, anomaly.pool_address)
        
        # Classify the anomaly
        assessment = await risk_classifier.classify(anomaly)
        logger.info("[ASSESSMENT] Severity: %s", assessment.severity)
        logger.info("[ASSESSMENT] Rationale: %s", assessment.rationale)
        
        # Generate narrative (in Spanish as per Phase 2 compliance showcase)
        narrative = await narrative_generator.generate(assessment, language="es")
        logger.info("[INCIDENT REPORT (ES)]:\n%s\n", narrative)

    # 3. Initialize detector engines
    sandwich_detector = SandwichDetector(window_seconds=3.0, on_anomaly=on_anomaly_detected)
    liquidity_scorer = LiquidityScorer(test_swap_size=10.0, impact_threshold=0.08, on_anomaly=on_anomaly_detected)
    predictive_model = LiquidityPredictiveModel(lambda_decay=0.85, depletion_time_threshold_seconds=50.0, on_anomaly=on_anomaly_detected)

    # 4. Initialize feeds
    # Set interval small enough to get > 20 events in 15 seconds
    mempool_feed = SimulatedMempoolFeed(interval=0.2, include_sandwich=True)
    liquidity_feed = SimulatedLiquidityFeed(interval=0.3)

    # 5. Initialize pipeline orchestrator
    orchestrator = PipelineOrchestrator(
        redis_client=redis_client,
        timescale_client=timescale_client,
        sandwich_detector=sandwich_detector,
        liquidity_scorer=liquidity_scorer,
        predictive_model=predictive_model,
        risk_classifier=risk_classifier,
        narrative_generator=narrative_generator,
        backpressure_limit=settings.pipeline_backpressure_limit
    )

    # Register feeds
    orchestrator.register_feed(mempool_feed, settings.mempool_semaphore_limit)
    orchestrator.register_feed(liquidity_feed, settings.liquidity_semaphore_limit)

    # 6. Run the watchtower engine
    await orchestrator.start()
    
    logger.info("Watchtower engine running. Simulating events for 15 seconds...")
    try:
        await asyncio.sleep(15.0)
    finally:
        logger.info("Stopping watchtower feeds and tasks...")
        mempool_feed.stop()
        liquidity_feed.stop()
        await sandwich_detector.stop()
        await orchestrator.stop()
        
        # Clean up connections if they have acleanup/aclose
        if hasattr(redis_client, "close"):
            await redis_client.close()
        if hasattr(timescale_client, "close"):
            await timescale_client.close()

        logger.info("Watchtower stopped. Total events processed: %d", orchestrator.processed_events_count)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Engine terminated by user.")
