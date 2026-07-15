# VeriGate Gateway

VeriGate is a secure, high-performance Python/Flask and MongoDB API gateway designed to orchestrate background identity verification pipelines. It handles client authentication, IP whitelisting, TPS rate limiting, PII masking/hashing, vendor timeout orchestration, fallback retry routing, and circuit breaking.

---

## Quick Start Setup (Local Run in < 10 mins)

Follow these steps to set up and run the service locally:

### 1. Prerequisites
- Python 3.11+
- MongoDB running locally on port `27017` (or pointed at MongoDB Atlas)
- Alternatively, if you have Docker installed, spin up MongoDB with:
  ```bash
  docker run -d --name local-mongo -p 27017:27017 mongo:latest
  ```

### 2. Install Dependencies
```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Variables
Create a `.env` file at the project root:
```bash
cp .env.example .env
```
*(By default, variables are set to work with your local Docker mongo instance).*

### 4. Seed the Database
Populate the MongoDB instance with mock clients, sub-users, and API keys:
```bash
PYTHONPATH=. venv/bin/python3 scripts/seed.py
```
*(Keep note of the generated API keys printed to stdout).*

### 5. Start the Application
Start the Flask application:
```bash
flask run
```
The gateway is now running at `http://127.0.0.1:5000/`.

---

## Running Verification & Testing

### Running Tests
Run the unit test suite containing 23 tests:
```bash
PYTHONPATH=. venv/bin/pytest -v
```

### Running the Load Test
Execute the concurrent traffic load generator:
```bash
PYTHONPATH=. venv/bin/python3 scripts/load_test.py
```

Refer to [curl_examples.md](file:///home/nishanth/projects/assessments/value_pitch_assessment/curl_examples.md) for individual curl commands testing successes and specific errors.

---

## Running with Docker Compose

If you prefer to run the application using Docker, MongoDB and the Flask application can be spun up in isolated containers:

1. **Start the Containers**:
   ```bash
   docker compose up -d --build
   ```
2. **Retrieve client API keys from container logs**:
   Since the container seeds itself automatically upon starting, you can view the generated API keys by running:
   ```bash
   docker logs verigate-app
   ```
3. **Execute requests**:
   Once the containers are up, the server will be reachable at `http://127.0.0.1:5000/`. You can copy the API keys from the logs to use in your headers.

---

## Database Index Design

We establish the following indexes on the `api_logs` collection to optimize search speeds:

1. **Compound Index (`client_id`, `created_at`)**: 
   * *Justification*: Required because all MIS reporting filters requests within a time range (`created_at`) and can optionally filter by client (`client_id`). This compound index prevents full table scans.
2. **Single Index (`error_code`)**: 
   * *Justification*: Crucial for grouping operations on error status classifications (e.g. `/mis/errors` or `/mis/fallback`) to fetch matching error statuses instantly.

---

## Critical Security & Production Caveats

### 1. In-Memory TPS Limiter (Single-Process Limitation)
The current rate-limiter is implemented as an in-memory sliding window using `collections.deque` and threading locks.
* **Production Caveat**: This implementation only works for a single Python process. If deployed behind multiple Gunicorn workers or scaled across multiple Kubernetes pods/nodes, each worker will maintain its own isolated memory state, allowing clients to bypass the configured limit.
* **Production Solution**: A shared distributed store like **Redis** must be used. We should implement rate-limiting using Redis sorted sets (ZSET) or token buckets to centrally track timestamps across all workers.

### 2. X-Forwarded-For Trust Model (IP Spoofing Risk)
The IP whitelisting middleware reads the `X-Forwarded-For` header to determine client IP addresses.
* **Production Caveat**: Clients can easily spoof this header by sending arbitrary IPs, which bypasses IP whitelisting controls.
* **Production Solution**: The gateway must **NEVER** trust client-supplied `X-Forwarded-For` headers directly. It must only trust this header if the gateway is running behind a secure, trusted reverse proxy (e.g., an AWS Application Load Balancer or Nginx) configured to overwrite/sanitize the header or append the true remote connection IP at a fixed index in the list.
