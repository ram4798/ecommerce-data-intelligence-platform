# Technical interview preparation

## 30 seconds
I built a local e-commerce data intelligence platform as an independent project. It combines PostgreSQL batch ingestion, Kafka events, PySpark and Delta Lake, dbt and Dagster, then serves validated analytics through FastAPI and Streamlit. I added an Ollama assistant that converts natural language into constrained query plans rather than executing model-generated SQL. I verified replay handling, quality gates, snapshot recovery and local performance on an 8 GB Mac.

## Two minutes
The goal was to build an end-to-end analytics system rather than isolated scripts. I started with deterministic synthetic relational data and transactional PostgreSQL ingestion. Kafka carries independent clickstream events; the consumer commits only after persistence and uses event IDs for replay safety. Spark independently reads Kafka and JDBC snapshots, writes Delta Bronze/Silver/Gold, validates totals and deduplicates events. I export logical snapshots to DuckDB, build dbt models and orchestrate seven assets with Dagster. Quality checks prevent a failed refresh from replacing the last-good serving snapshot. FastAPI queries it read-only; Streamlit exposes KPIs and the AI assistant. The assistant uses Qwen 2.5 3B and typed plans, with deterministic rules for common questions. During testing I found a fabricated region filter, inspected SQL evidence and added scope/ranking regression tests. On my Mac, 100 HTTP requests succeeded, KPI latency averaged 15.31 ms, and a separate synthetic scaling benchmark generated and validated 50,000 orders. This is a local prototype, not a production-scale deployment.

## Five minutes
Use the two-minute explanation, then expand: (1) contrast PostgreSQL consumer and independent Spark Kafka reader; describe failure between database commit and offset commit and deduplication; (2) explain Delta checkpoints, ten-minute watermark, insert-only MERGE and late-data limitations; (3) explain dbt grain, distinct order counts, integer cents, snapshot publication and read-only SQL; (4) demonstrate the wrong-region bug and deterministic correction; (5) discuss benchmarks, 8 GB constraints, macOS process ownership fix and future distributed validation. Keep the actual baseline and isolated scale test separate.

## Questions and defensible answers

### Ingestion and streaming
**1. Why deterministic data?** IDs and values are stable for overlapping ranges, so repeatable replay and financial reconciliation tests are possible.

**2. How is batch idempotent?** Primary keys and insert-on-conflict-ignore inside a transaction. Validation precedes writes; audit counts describe submitted records, not new inserts. Updates to existing IDs are not applied.

**3. What if batch fails halfway?** PostgreSQL rolls back business writes; failure audit is separate when DB reachable. A hard interruption may leave a running audit record.

**4. Why Kafka?** Decouple event producer from consumers and retain replayable ordered partitions. Customer ID is the source partition key; ordering is per partition, not global.

**5. What if consumer crashes after database commit?** Offset may not be committed, causing redelivery. Event primary key prevents duplicate valid records. DLQ can duplicate. This is at-least-once, not global exactly-once.

**6. How are bad events handled?** Validate schema/version, IDs, type and timestamps; Python sends invalid messages to DLQ. Spark independently derives quarantine from retained Bronze. The two paths have separate state.

**7. Why two Kafka readers?** Python demonstrates operational persistence and manual commits; Spark demonstrates independent lakehouse processing. They do not share offsets or require each other.

**8. How did you test replay?** 100 original valid events, 100 replay deliveries and one invalid. Observed 100 distinct stored valid events and one rejected message in the fresh test.

### Lakehouse and modeling
**9. Why Bronze/Silver/Gold?** Bronze retains source snapshots and raw payloads; Silver reconciles and validates; Gold provides aggregate metrics. Batch Bronze is overwritten snapshots, not immutable history.

**10. How does Spark dedup work?** Ten-minute event-time watermark and dropDuplicatesWithinWatermark, followed by insert-only Delta MERGE keyed by event ID. Watermark bounds streaming state; late records may be dropped, and replay safety is not an end-to-end exactly-once claim.

**11. Why available-now rather than continuous?** Completes a bounded refresh from available offsets and releases resources, fitting local 8 GB hardware. Trades low latency for scheduled freshness.

**12. How are financial totals reconciled?** Order total equals sum of quantity times unit price. Gross includes all statuses; paid means paid/shipped before returns. Store money in integer cents.

**13. Why DuckDB?** Embedded analytical engine avoids another database service and supports SQL/dbt locally. Export logical Delta snapshots through Spark/Parquet, not arbitrary obsolete Parquet files. Avoid concurrent writers.

**14. What is fact grain?** Sales is order-item grain; count distinct order IDs and customer IDs when needed. Category filters select matching lines; do not multiply order totals by line count.

**15. How does dbt incremental work?** Insert unseen immutable IDs; corrections/deletes are not CDC. A full refresh is needed for corrections under current design.

**16. How does Dagster orchestrate?** Seven assets: batch Delta, streaming Delta, warehouse export, dbt marts, quality, documentation and serving publication. Sequential local execution; selected retry policies. Hourly schedule defined but disabled by default.

### Quality, serving and operations
**17. What happens when quality fails?** Do not publish. Last successful serving snapshot remains readable. The gate does not undo intermediate warehouse changes.

**18. How is publication atomic?** Create candidate file in target directory, copy tables and publication metadata, checkpoint, then os.replace. Failed candidate build leaves old file untouched. Tested failed quality, missing table and successful recovery.

**19. How do you prevent SQL injection?** Fixed table/column/metric/operator allowlists, bound filter parameters and read-only DuckDB connections. API validates date ranges and limits.

**20. What do alerts cover?** Stage failure, quality failure, volume anomaly, stale quality checks and metrics unavailable. Local Prometheus/Grafana only; external notifications not implemented.

**21. How did you manage memory?** Spark local[2], 2 GB driver, four shuffle partitions, Kafka 512 MB heap, two DuckDB threads, one AI request and unload model after use. Separate pipeline and analytics modes. Limits are not measured peak RAM.

**22. Describe a real operational bug.** macOS Python replaced virtualenv argv[0] with Homebrew framework binary. PID/start/group unchanged but exact command identity differed. Recorded post-readiness identity and allowed only a narrowly verified transition. Shutdown and restart then passed.

### AI and performance
**23. Is this RAG?** No vector index, retrieval corpus or embeddings. It is constrained natural-language-to-query-plan analytics with SQL grounding.

**24. Why not execute generated SQL?** Model may generate unsafe or incorrect statements. Pydantic restricts operations/metrics/groups; compiler owns SQL; parameters and read-only snapshot constrain execution.

**25. How did you debug incorrect AI results?** Highest region returned US-Central because model invented a filter. Plan evidence exposed it. Deterministic global-ranking correction and filter validation fixed the tested question; tests protect against recurrence.

**26. How do common rules work?** Exact supported customer ranking/unique count/quality phrases use validated plans before inference. Unmatched wording uses LLM. Regional ranking alignment is after model validation. Coverage limited, no general semantic guarantee.

**27. How do you evaluate accuracy?** Compare known KPIs, inspect plan and SQL, test destructive requests. Twelve business scenarios eventually passed after fixes; four security requests rejected. Not held-out model accuracy or a comprehensive security audit.

**28. What were performance results?** 100 requests across five endpoints, 20 each/two workers, zero errors. KPI mean 15.31 ms, p95 21.49 ms. LLM order count mean 6.84 s, rule customer count 45.68 ms, three each; different questions.

**29. Did the full stack process 50,000 orders?** No. Synthetic generator and validation handled 50,000 orders and 100,227 lines; temporary DuckDB loaded orders only. Full-stack snapshot had 1500 orders.

**30. What would you optimize first?** Spark startup/batch and streaming dominate recorded run; profile before changing partitioning or incremental extraction. Sales endpoint p95 216 ms needs repeated benchmark and query profiling. No claimed improvement without a controlled before/after.

**31. How would you scale to millions?** Proposed: partitioned storage, incremental extraction/CDC, distributed Spark, durable Kafka replication, batched sink, warehouse sizing, workload isolation and load tests. Not implemented.

**32. What would production require?** Authentication/authorization, TLS, secret management, backups, multi-node durability, SLOs, infrastructure as code, deployment monitoring and security review.

## Scenario practice
- Duplicate payment or order-item mismatch: inspect source IDs, compare reconciled totals, reject inconsistent batch, rerun deterministic range.
- Kafka consumer replay: inspect source offsets and event keys; verify dedup and DLQ separately.
- Stale dashboard: distinguish latest pipeline quality from published timestamp; check failed asset and preserve old snapshot.
- Invalid model plan: inspect evidence when available, reproduce with fixture/mock, constrain interpretation without relaxing SQL allowlists.
- Slow pipeline: compare stage histories, inspect Spark execution and data sizes, isolate benchmark conditions, report measured change only.
