import sys
import os
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from prometheus_client import REGISTRY, generate_latest
from flowsentinel.observability.metrics import events_ingested_total

# Increment metric
events_ingested_total.labels(source="test").inc()

# Print registry content
print("Latest metrics:")
print(generate_latest(REGISTRY).decode("utf-8"))
