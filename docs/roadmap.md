# Future production-readiness roadmap

All items below are proposed, not implemented or validated.

| Priority | Work | Acceptance evidence |
|---|---|---|
| P0 | Authentication, authorization, TLS, secret manager, audit access | Unauthorized access denied; scoped roles and secret rotation tested |
| P0 | Backup/restore, durable checkpoints and disaster recovery | Restore drill and documented RPO/RTO targets |
| P0 | CI security scanning, dependency review and deployment separation | Reproducible builds, least privilege, isolated environments |
| P1 | CDC and update/delete semantics, schema evolution | Replay, correction and incompatible-schema tests |
| P1 | Replicated Kafka, batched consumer writes, distributed Spark | Broker failure and sustained throughput tests |
| P1 | Cloud object storage and managed warehouse/compute | End-to-end reconciliation on larger workloads |
| P1 | SLOs, external notifications, freshness based on event time | Measured latency/freshness and alert routing drills |
| P2 | Larger held-out AI evaluation, semantic ambiguity handling, rate limiting and authorization-aware query plans | Accuracy by question class, injection tests, latency/error distributions |
| P2 | Controlled cold/warm benchmarks and peak RAM instrumentation | Repeated same-query tests, resource measurements, full-stack load profile |

Suggested cloud mapping: managed PostgreSQL and Kafka, object storage with Delta-compatible Spark, managed orchestration and observability, containerized API and dashboard. Select platform only after requirements and cost review. Do not expose the existing unauthenticated localhost API directly to the internet.
