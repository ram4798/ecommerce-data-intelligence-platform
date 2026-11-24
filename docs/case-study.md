# Case study: E-Commerce Data Intelligence Platform

## Problem and scope
A simulated commerce team needs consistent sales reporting, independently collected clickstream metrics, reliable refreshes and a natural-language interface. The project demonstrates these requirements on an Apple M2 with 8 GB RAM, without employer data or paid cloud infrastructure. It is an independent portfolio prototype, not a deployed business system.

## Implementation
1. Deterministic relational generator creates customers, products, inventory, orders, items, payments and returns. Python validates keys and financial totals; PostgreSQL transactions and conflict-ignore inserts protect replay.
2. Kafka single-broker KRaft provides three source partitions and a DLQ. Python consumer validates events, persists valid events, commits offsets after persistence or acknowledged DLQ delivery. Replayed IDs deduplicate in PostgreSQL.
3. Spark JDBC snapshots feed Delta Bronze. Silver reconciles order totals and deduplicates events with watermark plus insert-only MERGE. Gold aggregates daily regional sales and five-minute event windows. Spark reads Kafka independently of the Python consumer.
4. DuckDB exports logical Delta snapshots; dbt builds 14 models with 22 tests, including dimensions, incremental facts and a daily mart. Seven Dagster assets coordinate refresh and publication.
5. Seventeen quality checks guard publication; local Prometheus/Grafana expose stage metrics and five alert rules. Failed quality or publication leaves the old serving file intact; intermediate writes are not rolled back.
6. FastAPI exposes parameterized read-only analytics; Streamlit displays sales, customers, payments, events, quality and AI. Money remains integer cents in API/storage.
7. Qwen 2.5 3B via Ollama interprets questions into typed plans; explicit rules handle narrow frequent intents. Server validates filters, compiles allowlisted SQL and formats results with evidence. Model text is never executable SQL.
8. Process manager starts/stops local services and records identity; macOS framework executable transition was fixed and verified. Spark/LLM are run separately to limit pressure on 8 GB RAM.

## Evidence
| Metric | Observed result | Scope |
|---|---|---|
| Baseline | 1500 orders, 3026 items, 100 customers | Synthetic snapshot |
| Events | 100 unique from 201 deliveries | 100 originals, 100 replays, one invalid |
| Sales | $86,161.18 gross; $42,549.60 paid | Before returns |
| Quality | 17/17 checks | Published snapshot |
| Refresh | 98 seconds | One seven-asset local run |
| API | 100/100 success; KPI mean 15.31 ms | 20 requests per endpoint, two workers |
| AI | LLM 6.84 s; rule 45.68 ms mean | Three trials each, different questions |
| Scale | 50,000 orders; 100,227 generated lines | Relational generation/validation, orders-only temporary DuckDB load |
| Regression | 6 assistant + 6 Phase 9 tests passed | Local suites, not total CI test count |

See [performance](performance.md) for measured latency distribution and caveats.

## Engineering lessons
An LLM invented a region filter for a global ranking and returned the wrong region. Inspectable SQL exposed the issue. Explicit scope/ranking rules and regression fixtures corrected it; later customer ranking and published quality questions received deterministic routes. A separate macOS process issue caused healthy services to appear unmanaged because Python exec changed the executable path. Matching startup time, complete invocation and process group plus recording post-readiness identity resolved the observed issue.

## Trade-offs
Local DuckDB and sequential Spark minimize infrastructure cost but limit concurrent writes and scale. Kafka at-least-once plus idempotent sinks is not global exactly-once. Snapshots favor safe serving over freshness. Rules reduce inference overhead but cover limited wording. No real user conversion analysis, CDC corrections, authentication, HA, external alert delivery or measured production SLA. Optional OpenAI is untested live.

## Outcome
A reproducible end-to-end prototype with documented setup, tests, observed benchmarks and explicit limitations. Next steps are in [roadmap](roadmap.md).
