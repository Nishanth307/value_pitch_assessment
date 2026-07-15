# Design Assumptions & Metrics Definitions

This document details key architectural decisions, metric calculations, and design calls made in VeriGate.

## 1. TPS Metrics Calculations

### Average TPS (`avg_tps`)
* **Choice**: We calculate average TPS as **total requests in a day divided by the number of seconds that actually experienced traffic**, rather than dividing by the total seconds in a day (86400).
* **Rationale**: In real-world gateways, traffic is bursty. Dividing total requests by 86400 during low-volume days yields near-zero numbers (e.g. 0.00 TPS) that hide actual active throughput rates. Dividing by active traffic seconds provides a representation of the server's true average workload when under load.

### Peak TPS (`peak_tps`)
* **Choice**: Peak TPS is calculated by grouping API logs by second using `$dateToString: { format: "%Y-%m-%dT%H:%M:%S", date: "$created_at" }` and computing the maximum number of requests recorded in any single second.

### P95 Latency (`p95_latency_ms`)
* **Choice**: Latencies are grouped, flattened into a single list in MongoDB using `$reduce` + `$concatArrays`, sorted in ascending order using `$sortArray`, and retrieved via `$arrayElemAt` at index `floor(0.95 * total_requests)`.
* **Rationale**: This is a pure MongoDB aggregation pipeline approach that avoids pulling data arrays into memory and processing percentiles in Python.

## 2. Load Testing Keys Resolution
* **Choice**: `scripts/load_test.py` reads client configuration docs and valid user IDs directly from the MongoDB database on startup using PyMongo, rather than relying on a local JSON file.
* **Rationale**: Querying the database guarantees that the load test is always run using up-to-date client statuses and whitelisted configurations directly matching the current seeded database state.
