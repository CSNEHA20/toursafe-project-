# TourSafe Environment Matrix & Parity Specification

This document defines the configuration, isolation boundaries, and infrastructure characteristics for all deployment tiers.

| Parameter / Dimension | Development (`dev`) | Test / QA (`test`) | Staging (`staging`) | Production (`prod`) |
| :--- | :--- | :--- | :--- | :--- |
| **Domain Base** | `localhost` | `test.toursafe.internal` | `staging-api.toursafe.internal` | `api.toursafe.internal` |
| **TLS / SSL** | Optional (Plain HTTP) | Self-signed / Internal CA | Let's Encrypt / ACM | ACM TLSv1.3 with HSTS |
| **API Replicas** | 1 (Reload enabled) | 1 | 2 (Stateless) | 3 - 15 (Autoscaling HPA) |
| **Database Tier** | Standalone MongoDB (Docker) | Ephemeral / Mock Motor | 3-node Replica Set (M30) | 3-node Multi-AZ Replica Set (M50+) with KMS Encryption |
| **Redis Tier** | Standalone Redis (Docker) | Mock / In-Memory State | Redis Sentinel Pair | Redis Cluster with TLS & Auth |
| **Telemetry Retention** | 1 day | 1 day | 7 days | 30 days (Configurable / Governed) |
| **KYC Storage** | Local Scratch Directory | Mock Storage | Isolated S3 Bucket | Encrypted S3 KMS Vault with 2-Year Retention Policy |
| **Synthetic Guard** | Active by default | Active | Active | Active on synthetic tests; Inactive for real tourists |
| **CORS Origins** | `http://localhost:8081`, `127.0.0.1` | `http://test-runner` | `https://staging-app.toursafe.internal` | Strict Whitelist (`https://app.toursafe.internal`) |
| **Debug Mode** | `true` | `false` | `false` | `false` (Strictly Enforced) |
| **Admin Bootstrap** | Auto Seed Developer Admin | Auto Seed Test Fixtures | Controlled CLI Tool (`scripts/bootstrap_admin.py`) | Controlled Vault/KMS CLI Bootstrap (`scripts/bootstrap_admin.py`) |
| **PII Data** | Synthetic Mock Only | Synthetic Fixtures Only | Anonymized / Synthetic | Real Protected Tourist Data under DPDP Act 2023 |

---

## Environment Promotion Lifecycle

1. **Development (`dev`)**: Developer workstations and local feature branch testing with Docker Compose.
2. **Pull Request Validation (`test`)**: Automated GitHub Actions CI executes all 45+ regression suites, lint, type checks, and SAST scans.
3. **Staging (`staging`)**: Mirrors production container topology, runs database forward migrations, and executes the synthetic smoke test suite.
4. **Production (`prod`)**: Deployed following manual engineering sign-off, executes database pre-flight snapshot, rolling update with zero downtime, and post-deployment smoke validation.
