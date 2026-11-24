# Phase 6 monitoring

Run from repository root with existing Phase 5 dependencies. Stop Dagster before manual refreshes. The quality gate reads DuckDB without changing business data. It checks required columns (not exact types), nulls, counts, event uniqueness, raw-to-fact completeness, sales reconciliation and freshness of the last successful warehouse export (not event-time freshness). Volume changes over 50% against the last clean baseline are warnings; the first run establishes the baseline. Rules are in config/quality.json. Failed checks block the downstream documentation asset, but do not roll back already built marts. Stage metrics represent latest attempt, not cumulative counters; JSONL preserves attempt history. Metrics persist on disk and are served as Prometheus text exposition by nginx.

    python -m ecommerce.warehouse
    python -m ecommerce.quality
    mkdir -p data/observability/metrics
    docker compose -f compose.yaml -f compose.kafka.yaml -f compose.monitoring.yaml up -d metrics prometheus grafana

Prometheus: http://localhost:9090/alerts. Grafana: http://localhost:3001 (admin / local_demo_change_me on first startup; change password). Dashboard: E-Commerce Pipeline Health. Run Dagster refresh_analytics to populate stage metrics. Missing stage files alert until first run. No external notification receiver; alerts are visible in Prometheus and Grafana only. Local ports bind loopback. Set GRAFANA_ADMIN_PASSWORD before first startup if desired.

Controlled failure (does not modify business data):
    python -m ecommerce.quality --simulate-failure
Expected nonzero exit. Allow at least two scrape/evaluation intervals and inspect alerts. Then recover:
    python -m ecommerce.quality
If snapshot is stale, rerun warehouse export first. The failure report is overwritten on recovery; JSONL retains both attempts. No concurrent refreshes. Stop monitoring without deleting volumes:
    docker compose -f compose.yaml -f compose.kafka.yaml -f compose.monitoring.yaml stop metrics prometheus grafana
