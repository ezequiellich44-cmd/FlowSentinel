import json
import asyncio
import time
import uuid
import structlog
from typing import List, Dict, Union, Tuple, Optional
from flowsentinel.models import TxIntent, PoolState, OrderBookSnapshot, AnomalyCandidate
from flowsentinel.feeds.base import Feed
from flowsentinel.config import settings
from flowsentinel.alerting.base import AlertSink
from flowsentinel.observability.metrics import events_ingested_total, pipeline_latency_seconds, anomalies_detected_total

logger = structlog.get_logger(__name__)

class PipelineOrchestrator:
    def __init__(self,
                 redis_client,
                 timescale_client,
                 sandwich_detector,
                 liquidity_scorer,
                 predictive_model,
                 risk_classifier,
                 narrative_generator,
                 backpressure_limit: int = 100,
                 alert_sinks: Optional[List[AlertSink]] = None):
        self.redis_client = redis_client
        self.timescale_client = timescale_client
        self.sandwich_detector = sandwich_detector
        self.liquidity_scorer = liquidity_scorer
        self.predictive_model = predictive_model
        self.risk_classifier = risk_classifier
        self.narrative_generator = narrative_generator
        
        # Intercept anomalies detected by sub-engines (if provided)
        if self.sandwich_detector:
            self.sandwich_detector.on_anomaly = self._handle_anomaly
        if self.liquidity_scorer:
            self.liquidity_scorer.on_anomaly = self._handle_anomaly
        if self.predictive_model:
            self.predictive_model.on_anomaly = self._handle_anomaly
        
        # Initialize Alert Sinks from settings if not explicitly provided
        if alert_sinks is None:
            self.alert_sinks = []
            if settings.webhook_url:
                from flowsentinel.alerting.webhook_sink import WebhookSink
                self.alert_sinks.append(WebhookSink(
                    url=settings.webhook_url,
                    circuit_breaker_cooldown=settings.circuit_breaker_cooldown,
                    max_failures=settings.circuit_breaker_max_failures
                ))
            if settings.telegram_token and settings.telegram_chat_id:
                from flowsentinel.alerting.telegram_sink import TelegramSink
                self.alert_sinks.append(TelegramSink(
                    token=settings.telegram_token,
                    chat_id=settings.telegram_chat_id
                ))
        else:
            self.alert_sinks = alert_sinks
        
        # Central queue with backpressure limit
        self.queue: asyncio.Queue[Tuple[Union[TxIntent, PoolState, OrderBookSnapshot], asyncio.Semaphore]] = asyncio.Queue(maxsize=backpressure_limit)
        
        self.feeds: List[Tuple[Feed, asyncio.Semaphore]] = []
        self.ingest_tasks: List[asyncio.Task] = []
        self.consumer_task: Optional[asyncio.Task] = None
        self.running = False
        self.processed_events_count = 0

    def register_feed(self, feed: Feed, semaphore_limit: int) -> None:
        semaphore = asyncio.Semaphore(semaphore_limit)
        self.feeds.append((feed, semaphore))
        logger.info("Registered feed %s with semaphore limit %d", feed.__class__.__name__, semaphore_limit)

    async def start(self) -> None:
        self.running = True
        # Start consumer
        self.consumer_task = asyncio.create_task(self._consumer_loop())
        # Start ingestors
        for feed, semaphore in self.feeds:
            task = asyncio.create_task(self._ingest_loop(feed, semaphore))
            self.ingest_tasks.append(task)
        logger.info("Pipeline orchestrator started.")

    async def stop(self) -> None:
        self.running = False
        # Cancel all ingest tasks
        for task in self.ingest_tasks:
            task.cancel()
        await asyncio.gather(*self.ingest_tasks, return_exceptions=True)
        self.ingest_tasks.clear()

        # Wait until queue is empty or cancel consumer
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
            self.consumer_task = None
        logger.info("Pipeline orchestrator stopped.")

    async def _ingest_loop(self, feed: Feed, semaphore: asyncio.Semaphore) -> None:
        try:
            async for event in feed.stream():
                if not self.running:
                    break
                # Acquire semaphore before putting into the queue to limit concurrent inflight processing
                await semaphore.acquire()
                try:
                    # Put event into queue (blocks if queue is full - backpressure)
                    await self.queue.put((event, semaphore))
                except Exception:
                    semaphore.release()
                    raise
        except asyncio.CancelledError:
            logger.info("Ingest loop for %s cancelled.", feed.__class__.__name__)
        except Exception as e:
            logger.error("Error in ingest loop for %s: %s", feed.__class__.__name__, str(e))

    async def _consumer_loop(self) -> None:
        try:
            while self.running:
                event, semaphore = await self.queue.get()
                
                # Bind trace_id for current event context
                trace_id = str(uuid.uuid4())
                structlog.contextvars.bind_contextvars(trace_id=trace_id)
                
                # Increment ingested events counter
                source = "mempool" if isinstance(event, TxIntent) else ("liquidity" if isinstance(event, PoolState) else "orderbook")
                events_ingested_total.labels(source=source).inc()
                
                start_time = time.perf_counter()
                try:
                    await self._process_event(event)
                except Exception as e:
                    logger.error("Error processing event", error=str(e))
                finally:
                    # Record total latency of processing event
                    duration = time.perf_counter() - start_time
                    pipeline_latency_seconds.labels(stage="process_event").observe(duration)
                    
                    # Clear event trace context
                    structlog.contextvars.clear_contextvars()
                    
                    # Release semaphore to allow new events to be ingested
                    semaphore.release()
                    self.queue.task_done()
        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled.")

    async def _process_event(self, event: Union[TxIntent, PoolState, OrderBookSnapshot]) -> None:
        self.processed_events_count += 1
        
        # 1. Deduplication using Redis (for transaction intents)
        if isinstance(event, TxIntent):
            # Check duplicates in Redis (skip duplicate transaction hashes)
            is_dup = await self.redis_client.is_duplicate(event.tx_hash)
            if is_dup:
                logger.debug("Deduplicated transaction: %s", event.tx_hash)
                return

            # Store in TimescaleDB
            try:
                # Insert gas price data
                # Convert time to timestamp string for Postgres timestamptz
                import datetime
                dt = datetime.datetime.fromtimestamp(event.timestamp, tz=datetime.timezone.utc)
                await self.timescale_client.execute(
                    "INSERT INTO gas_prices (time, chain_id, tx_hash, gas_price, target_address) VALUES ($1, $2, $3, $4, $5)",
                    dt, event.chain_id, event.tx_hash, event.gas_price, event.target_address
                )
            except Exception as e:
                logger.debug("Failed database insert (gas_prices): %s. Check DB connection.", str(e))

            # Pass to detectors (if provided)
            if self.sandwich_detector:
                await self.sandwich_detector.process_intent(event)

        elif isinstance(event, PoolState):
            # Store in TimescaleDB
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(event.timestamp, tz=datetime.timezone.utc)
                await self.timescale_client.execute(
                    "INSERT INTO pool_depth (time, pool_address, exchange_name, reserve0, reserve1) VALUES ($1, $2, $3, $4, $5)",
                    dt, event.pool_address, event.exchange_name, event.reserve0, event.reserve1
                )
            except Exception as e:
                logger.debug("Failed database insert (pool_depth): %s. Check DB connection.", str(e))

            # Pass to detectors (if provided)
            if self.liquidity_scorer:
                await self.liquidity_scorer.process_pool_state(event)
            if self.predictive_model:
                await self.predictive_model.process_pool_state(event)

        elif isinstance(event, OrderBookSnapshot):
            # Store in TimescaleDB
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(event.timestamp, tz=datetime.timezone.utc)
                # Compute mid_price and spread
                bids = event.bids
                asks = event.asks
                mid_price = 0.0
                spread = 0.0
                if bids and asks:
                    best_bid = bids[0][0]
                    best_ask = asks[0][0]
                    mid_price = (best_bid + best_ask) / 2.0
                    spread = best_ask - best_bid
                
                await self.timescale_client.execute(
                    "INSERT INTO orderbook_snapshots (time, pair, mid_price, spread, bids, asks) VALUES ($1, $2, $3, $4, $5, $6)",
                    dt, event.pair, mid_price, spread, json.dumps(bids), json.dumps(asks)
                )
            except Exception as e:
                logger.debug("Failed database insert (orderbook_snapshots): %s. Check DB connection.", str(e))

    async def _handle_anomaly(self, anomaly: AnomalyCandidate) -> None:
        logger.warn("Anomaly candidate detected", type=anomaly.pattern_type, pool=anomaly.pool_address)
        
        # 1. Classification stage
        start_time = time.perf_counter()
        try:
            assessment = await self.risk_classifier.classify(anomaly)
            logger.info("Anomaly classified", severity=assessment.severity, rationale=assessment.rationale)
        except Exception as e:
            logger.error("Failed to classify anomaly", error=str(e))
            return
        finally:
            duration = time.perf_counter() - start_time
            pipeline_latency_seconds.labels(stage="classification").observe(duration)
            
        # 2. Narrative generation stage
        start_time = time.perf_counter()
        try:
            narrative = await self.narrative_generator.generate(assessment, language="es")
            logger.info("Incident report narrative generated")
        except Exception as e:
            logger.error("Failed to generate narrative", error=str(e))
            return
        finally:
            duration = time.perf_counter() - start_time
            pipeline_latency_seconds.labels(stage="narrative").observe(duration)
            
        # Record anomaly detection counter
        anomalies_detected_total.labels(pattern_type=anomaly.pattern_type).inc()
        
        # 3. Alerting sinks stage
        for sink in self.alert_sinks:
            try:
                await sink.send(assessment, narrative)
            except Exception as e:
                logger.error("Failed to send alert to sink", sink=sink.__class__.__name__, error=str(e))
