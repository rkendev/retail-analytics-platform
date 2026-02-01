# Architecture Decision Records

## ADR-001: Medallion Architecture (Bronze → Silver → Gold)

**Context:** Need a clear data organization strategy that supports auditing, reprocessing, and incremental builds.

**Decision:** Three-layer medallion architecture:
- **Bronze (GCS):** Raw, immutable Parquet. Never modified. Hive-partitioned by date.
- **Silver (BigQuery staging):** Cleaned, typed, deduplicated. Materialized as views.
- **Gold (BigQuery marts):** Star schema dimensional model. Optimized for analytics.

**Consequences:** Slightly more storage cost for keeping bronze, but enables full reprocessing from raw data if transformation logic changes.

---

## ADR-002: Pydantic V2 for Ingestion Validation

**Context:** Records from three different sources need validation before entering bronze.

**Decision:** Use Pydantic V2 models as data contracts. Each source has a dedicated model.

**Alternatives considered:**
- Great Expectations — better for statistical profiling, but heavy for per-record validation
- Pandera — good for DataFrame validation, but we validate dict-by-dict at ingestion
- Manual validation — error-prone, no schema documentation

**Consequences:** Fast, type-safe validation. Contracts serve as living documentation. Trade-off: doesn't do statistical checks (handled by dbt tests downstream).

---

## ADR-003: Quarantine Pattern

**Context:** What happens when a record fails validation?

**Decision:** Invalid records route to a separate quarantine bucket with error details, while valid records proceed normally. A weekly review process generates a quarantine report.

**Alternative:** Fail-fast (reject the entire batch if any record is bad). Rejected because one corrupted record shouldn't block thousands of valid records.

---

## ADR-004: BigQuery over Snowflake

**Context:** GCP-focused portfolio needs a cloud data warehouse.

**Decision:** BigQuery.

**Rationale:**
- Serverless (no cluster provisioning)
- Native MERGE for upserts
- Generous free tier ($300 credits + 1TB/month queries)
- GCS integration is zero-copy

**Trade-offs:** Snowflake has better multi-cloud portability, more granular concurrency control, and Time Travel is more configurable.

---

## ADR-005: Incremental Fact Table with MERGE

**Context:** `fact_orders` grows daily. Full refresh is wasteful.

**Decision:** dbt incremental materialization with `unique_key='order_id'` and a `WHERE order_date > max(existing)` filter.

**Consequences:** Each daily run only processes new data. BigQuery's MERGE handles upserts for late-arriving CDC updates. Full refresh available via `dbt run --full-refresh`.

---

## ADR-006: Quality Gates as Circuit Breakers

**Context:** How to prevent bad staging data from corrupting the gold layer.

**Decision:** SQL assertion checks run between staging refresh and mart build. Critical failures halt the pipeline.

**Implementation:** Airflow task dependency chain:
```
dbt_staging → quality_gates → dbt_marts
```
If `quality_gates` fails, `dbt_marts` never executes.

---

## ADR-007: Local-First Development

**Context:** GCP services cost money. Developers need a fast feedback loop.

**Decision:** All extractors and loaders support a `local_mode` flag. Bronze data writes to `data/bronze/` as local Parquet. Tests run without any GCP credentials.

**Consequences:** `make run-local` works on any machine. GCP deployment is a config switch, not a code change.
