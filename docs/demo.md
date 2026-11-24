# Five-minute portfolio demonstration

## Preparation
Use the existing published snapshot. From repository root, activate .venv and run python -m ecommerce.service_manager start app, then status all. Keep Spark stopped while using Ollama. For Grafana evidence, start infra if needed. Do not rerun ingestion just to record the demo. Open dashboard, API docs and repository in separate browser tabs.

| Time | Show | Narration |
|---|---|---|
| 0:00–0:35 | README architecture | This independent project connects synthetic commerce data, batch and streaming pipelines, governed analytics and a local AI interface. |
| 0:35–1:15 | Batch/streaming/lakehouse code | Deterministic IDs support replay; Kafka consumer commits after persistence; Spark separately processes Kafka into Delta layers. |
| 1:15–1:50 | Historical Dagster run or architecture | Seven assets refresh dbt marts, run quality checks and publish a read-only snapshot. The observed run took 98 seconds. |
| 1:50–2:35 | Streamlit Sales | 1500 orders, $86,161.18 gross, $42,549.60 paid. Filter US-East and explain gross includes all statuses, paid is before returns. |
| 2:35–3:00 | Events and quality | 100 distinct events, 17/17 published checks. Clickstream is synthetic and independent of orders. |
| 3:00–4:05 | AI assistant and evidence | Ask total orders, top five customers by paid value, highest gross sales region. Expand query evidence. Ask delete all orders; show rejection. |
| 4:05–4:35 | Benchmarks | 100/100 requests succeeded; KPI mean 15.31 ms. Isolated scale workload generated 50,000 orders and 100,227 lines. |
| 4:35–5:00 | Service manager and roadmap | One terminal controls application services. This is local, not production; future work adds cloud security, distributed tests and CDC. |

If Dagster is not running, use the documented historical result rather than claiming a live run. Do not record credentials or unrelated personal information.

## Screenshot checklist
Capture clean dashboard sales overview, streaming tab, quality tab, AI customer ranking with evidence expanded, Grafana stage dashboard and historical successful Dagster run if available. Save under docs/screenshots with descriptive names; crop personal paths, browser account details and OS capture controls. Add actual images to README only after capture and review. No screenshot assets or video are claimed to exist yet.
