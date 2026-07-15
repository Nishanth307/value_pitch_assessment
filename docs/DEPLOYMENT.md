# Production Deployment Guide (AWS ECS/EKS)

This document provides a written walkthrough of deploying VeriGate to production in AWS (ECS or EKS), configuring secure ingress, and transitioning single-process features to enterprise-ready solutions.

---

## 1. Production Architecture Overview

In a typical production environment, VeriGate is deployed across multiple containers/replicas for high availability:

```
[ Clients ] ---> [ HTTPS (Port 443) ]
                       |
                       v
        [ AWS Application Load Balancer (ALB) ]
                       | (HTTP - Port 80)
                       v
   [ EKS Pods / ECS Fargate Tasks (Replicas) ]
        |                   |
        v                   v
[ AWS Secrets Manager ]   [ AWS ElastiCache (Redis) ]
```

---

## 2. Secure Configuration & Secrets Management

In production, secret environment variables (like `MONGO_URI` and `ADMIN_API_KEY`) must **NEVER** be committed in ConfigMaps or code.

* **Secrets Manager**: Store the MongoDB URI and API keys in **AWS Secrets Manager** or **AWS Systems Manager Parameter Store** (SecureString).
* **Injection**:
  * **ECS**: Reference the Secret ARNs directly inside the ECS Task Definition (`secrets` array) to map them to container environment variables at runtime.
  * **EKS**: Use the **External Secrets Operator** or **AWS Secrets Store CSI Driver** to mount secrets from Secrets Manager directly into the pod environment.

---

## 3. Ingress, TLS, & IP Whitelisting (ALB)

To enforce IP Whitelisting safely:
1. **TLS Termination**: Terminate TLS/SSL on the **Application Load Balancer (ALB)** using an ACM (AWS Certificate Manager) certificate.
2. **Real Client IP Verification**:
   * The ALB automatically appends the real client connection IP to the `X-Forwarded-For` header before forwarding the request to the Flask container targets.
   * **Security Rule**: The security group on the ECS/EKS nodes must **only** accept incoming traffic from the ALB.
   * **Trust Mapping**: Because the containers only accept traffic from the ALB, we can safely trust the `X-Forwarded-For` header value since it was set by our own trusted load balancer, mitigating header spoofing.

---

## 4. Scaling & Distributed Coordination (Redis)

As we scale VeriGate past a single container replica (e.g. using HPAs or ECS scaling policies), our single-process in-memory limits must be transitioned to a shared cache:

### A. Distributed TPS Limiter
* **Issue**: The current deque-based rate limiter is isolated in each container's memory. Replicas have no awareness of requests hit on other nodes.
* **Transition**: Use **AWS ElastiCache for Redis**. Implement rate limiting using:
  * **Redis Sorted Sets (ZSET)**: Store timestamps of requests for each client. Trim sets by removing elements older than 1 second, and check card/length of set.
  * **Redis Token Bucket**: Use Redis commands or Lua scripts to atomically increment and decrement client bucket tokens.

### B. Distributed Circuit Breaker
* **Issue**: Timed-out or failed vendor connections recorded on one instance will not trip the circuit breaker on other replicas, allowing requests to continue hitting failing vendors.
* **Transition**: Move the circuit breaker state to Redis:
  * Store Vendor A failure counters and timestamps in a central Redis key with an expiration window.
  * Replicas query Redis before calling Vendor A. If the failure counter exceeds the threshold, the circuit state key is set to "open" globally in Redis with a 30-second TTL, routing all instances to Vendor B immediately.
