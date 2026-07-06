from prometheus_client import Counter, Histogram, REGISTRY

# Counter of all ingested events by feed source
events_ingested_total = Counter(
    "events_ingested_total",
    "Total count of events ingested into the FlowSentinel pipeline.",
    ["source"]
)

# Histogram of latency per pipeline stage
pipeline_latency_seconds = Histogram(
    "pipeline_latency_seconds",
    "Latency of processing stages in seconds.",
    ["stage"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Counter of anomalies detected by type
anomalies_detected_total = Counter(
    "anomalies_detected_total",
    "Total count of MEV anomalies detected.",
    ["pattern_type"]
)
