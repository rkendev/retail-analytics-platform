"""
Retail Analytics Platform — Executive Dashboard
================================================

Multi-tab Streamlit dashboard querying the BigQuery star schema (marts layer).
Visualises revenue trends, product performance, customer segments, and pipeline health.

Usage:
    export GCP_PROJECT=nifty-quanta-486115-d6   # or set DBT_PROJECT
    streamlit run app/dashboard.py

Environment variables (all optional — sensible defaults provided):
    GCP_PROJECT / DBT_PROJECT   GCP project ID
    DBT_MARTS_DATASET           BigQuery dataset for marts  (default: marts_dev)
    DBT_STAGING_DATASET         BigQuery dataset for staging (default: staging_dev)
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from google.cloud import bigquery

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
PROJECT_ID = os.getenv("GCP_PROJECT", os.getenv("DBT_PROJECT", "nifty-quanta-486115-d6"))
MARTS = os.getenv("DBT_MARTS_DATASET", "marts_dev")
STAGING = os.getenv("DBT_STAGING_DATASET", "staging_dev")

# Colour palette — consistent across charts
PALETTE = px.colors.qualitative.Set2
BLUE_SCALE = "Blues"
TEAL_SCALE = "Teal"


# ──────────────────────────────────────────────────────────────────────
# BigQuery helpers
# ──────────────────────────────────────────────────────────────────────
@st.cache_resource
def _bq_client() -> bigquery.Client:
    """Singleton BigQuery client (one per Streamlit session)."""
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=300)
def _query(sql: str) -> pd.DataFrame:
    """Execute *sql* and return a DataFrame. Results cached for 5 min."""
    return _bq_client().query(sql).to_dataframe()


def _t(dataset: str, table: str) -> str:
    """Return a fully-qualified BigQuery table reference."""
    return f"`{PROJECT_ID}.{dataset}.{table}`"


# Revenue helper — gracefully handles NULL total_amount_usd
_REV = "COALESCE(f.total_amount_usd, f.unit_price_local * f.quantity)"


def _fmt_usd(value: float) -> str:
    """Format a dollar amount compactly: $1,234 / $12.3K / $1.2M."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 10_000:
        return f"${value / 1_000:,.1f}K"
    return f"${value:,.2f}"


# ──────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Retail Analytics Platform",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Retail Analytics Dashboard")
st.caption(f"Connected to **{PROJECT_ID}** · marts: `{MARTS}` · staging: `{STAGING}`")


# ──────────────────────────────────────────────────────────────────────
# Sidebar — data freshness + controls
# ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔄 Data Freshness")
    try:
        freshness_df = _query(f"""
            SELECT
                MAX(order_date)                     AS latest_order,
                MIN(order_date)                     AS earliest_order,
                COUNT(DISTINCT pipeline_run_id)      AS pipeline_runs,
                COUNT(*)                            AS total_rows
            FROM {_t(MARTS, 'fact_orders')}
        """)
        row = freshness_df.iloc[0]
        st.metric("Latest Order", str(row["latest_order"])[:10])
        st.metric("Earliest Order", str(row["earliest_order"])[:10])
        st.metric("Pipeline Runs", int(row["pipeline_runs"]))
        st.metric("Fact Rows", f"{int(row['total_rows']):,}")
    except Exception as exc:
        st.error(f"Freshness check failed: {exc}")

    st.divider()

    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown(
        "**Retail Analytics Platform**\n\n"
        "End-to-end data pipeline:\n"
        "REST API + CDC + CSV → GCS Bronze → "
        "BigQuery → dbt Star Schema → Streamlit"
    )


# ──────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────
tab_revenue, tab_products, tab_customers, tab_pipeline = st.tabs(
    ["📈 Revenue Overview", "📦 Product Analytics", "👥 Customer Insights", "🔧 Pipeline Health"]
)


# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — Revenue Overview
# ═══════════════════════════════════════════════════════════════════════
with tab_revenue:
    # ── KPI banner ────────────────────────────────────────────────────
    try:
        kpis = _query(f"""
            SELECT
                COUNT(*)                                            AS total_orders,
                COUNT(DISTINCT customer_id)                         AS unique_customers,
                ROUND(SUM({_REV}), 2)                               AS total_revenue,
                ROUND(AVG({_REV}), 2)                               AS avg_order_value,
                COUNT(DISTINCT currency_code)                       AS currencies_used,
                COUNT(DISTINCT store_key)                           AS stores
            FROM {_t(MARTS, 'fact_orders')} f
        """)
        k = kpis.iloc[0]
        row1_c1, row1_c2, row1_c3 = st.columns(3)
        row1_c1.metric("Total Orders", f"{int(k['total_orders']):,}")
        row1_c2.metric("Unique Customers", f"{int(k['unique_customers']):,}")
        row1_c3.metric("Total Revenue", _fmt_usd(k["total_revenue"]))
        row2_c1, row2_c2, row2_c3 = st.columns(3)
        row2_c1.metric("Avg Order Value", f"${k['avg_order_value']:,.2f}")
        row2_c2.metric("Currencies", int(k["currencies_used"]))
        row2_c3.metric("Stores", int(k["stores"]))
    except Exception as exc:
        st.error(f"KPI query failed: {exc}")

    st.divider()

    # ── Revenue over time + by currency ───────────────────────────────
    col_time, col_curr = st.columns(2)

    with col_time:
        st.subheader("Daily Revenue")
        try:
            rev_time = _query(f"""
                SELECT
                    DATE(f.order_date)       AS order_day,
                    ROUND(SUM({_REV}), 2)    AS daily_revenue,
                    COUNT(*)                 AS daily_orders
                FROM {_t(MARTS, 'fact_orders')} f
                GROUP BY 1
                ORDER BY 1
            """)
            if not rev_time.empty:
                fig = px.area(
                    rev_time,
                    x="order_day",
                    y="daily_revenue",
                    labels={"order_day": "Date", "daily_revenue": "Revenue (USD)"},
                    color_discrete_sequence=["#2563eb"],
                )
                fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No revenue data yet.")
        except Exception as exc:
            st.error(f"Revenue trend failed: {exc}")

    with col_curr:
        st.subheader("Revenue by Currency (Top 10)")
        try:
            rev_curr = _query(f"""
                SELECT
                    f.currency_code,
                    ROUND(SUM(f.unit_price_local * f.quantity), 2) AS revenue_local,
                    COUNT(*) AS orders
                FROM {_t(MARTS, 'fact_orders')} f
                GROUP BY 1
                ORDER BY revenue_local DESC
                LIMIT 10
            """)
            if not rev_curr.empty:
                fig = px.bar(
                    rev_curr,
                    x="currency_code",
                    y="revenue_local",
                    color="revenue_local",
                    color_continuous_scale=BLUE_SCALE,
                    labels={"currency_code": "Currency", "revenue_local": "Revenue (Local)"},
                )
                fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No currency data.")
        except Exception as exc:
            st.error(f"Currency revenue failed: {exc}")

    # ── Revenue by store ──────────────────────────────────────────────
    st.subheader("Revenue by Store")
    try:
        rev_store = _query(f"""
            SELECT
                f.store_key,
                ROUND(SUM({_REV}), 2) AS revenue,
                COUNT(*)              AS orders,
                COUNT(DISTINCT f.customer_id) AS customers
            FROM {_t(MARTS, 'fact_orders')} f
            GROUP BY 1
            ORDER BY revenue DESC
        """)
        if not rev_store.empty:
            fig = px.bar(
                rev_store,
                x="store_key",
                y="revenue",
                color="orders",
                color_continuous_scale="Viridis",
                labels={"store_key": "Store", "revenue": "Revenue (USD)", "orders": "Orders"},
                hover_data=["customers"],
            )
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No store data.")
    except Exception as exc:
        st.error(f"Store revenue failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — Product Analytics
# ═══════════════════════════════════════════════════════════════════════
with tab_products:
    col_top, col_cat = st.columns(2)

    with col_top:
        st.subheader("Top 10 Products by Revenue")
        try:
            top_prod = _query(f"""
                SELECT
                    p.product_name,
                    COALESCE(p.category, 'Uncategorized') AS category,
                    ROUND(SUM({_REV}), 2) AS revenue,
                    SUM(f.quantity)         AS units_sold
                FROM {_t(MARTS, 'fact_orders')} f
                JOIN {_t(MARTS, 'dim_products')} p ON f.product_id = p.product_id
                GROUP BY 1, 2
                ORDER BY revenue DESC
                LIMIT 10
            """)
            if not top_prod.empty:
                fig = px.bar(
                    top_prod,
                    x="revenue",
                    y="product_name",
                    orientation="h",
                    color="category",
                    labels={"product_name": "", "revenue": "Revenue (USD)"},
                    color_discrete_sequence=PALETTE,
                    hover_data=["units_sold"],
                )
                fig.update_layout(
                    height=420,
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No product data.")
        except Exception as exc:
            st.error(f"Top products failed: {exc}")

    with col_cat:
        st.subheader("Revenue by Category")
        try:
            cat_rev = _query(f"""
                SELECT
                    COALESCE(p.category, 'Uncategorized') AS category,
                    ROUND(SUM({_REV}), 2)          AS revenue,
                    COUNT(*)                        AS order_count,
                    COUNT(DISTINCT f.customer_id)   AS unique_buyers
                FROM {_t(MARTS, 'fact_orders')} f
                JOIN {_t(MARTS, 'dim_products')} p ON f.product_id = p.product_id
                GROUP BY 1
                ORDER BY revenue DESC
            """)
            if not cat_rev.empty:
                fig = px.pie(
                    cat_rev,
                    values="revenue",
                    names="category",
                    hole=0.4,
                    color_discrete_sequence=PALETTE,
                )
                fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No category data.")
        except Exception as exc:
            st.error(f"Category revenue failed: {exc}")

    # ── Catalog summary table ─────────────────────────────────────────
    st.subheader("Product Catalog Summary")
    try:
        catalog = _query(f"""
            SELECT
                COALESCE(p.category, 'Uncategorized') AS category,
                COUNT(DISTINCT p.product_id)   AS products,
                COUNT(DISTINCT p.brand)        AS brands,
                COUNT(DISTINCT p.subcategory)  AS subcategories
            FROM {_t(MARTS, 'dim_products')} p
            GROUP BY 1
            ORDER BY products DESC
        """)
        if not catalog.empty:
            st.dataframe(catalog, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Catalog query failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — Customer Insights
# ═══════════════════════════════════════════════════════════════════════
with tab_customers:
    col_seg, col_top_cust = st.columns(2)

    with col_seg:
        st.subheader("Customer Segments")
        try:
            segs = _query(f"""
                SELECT
                    COALESCE(c.customer_segment, 'Unknown') AS segment,
                    COUNT(*) AS customer_count
                FROM {_t(MARTS, 'dim_customers')} c
                GROUP BY 1
                ORDER BY customer_count DESC
            """)
            if not segs.empty:
                fig = px.pie(
                    segs,
                    values="customer_count",
                    names="segment",
                    hole=0.4,
                    color_discrete_sequence=PALETTE,
                )
                fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No segment data.")
        except Exception as exc:
            st.error(f"Segment query failed: {exc}")

    with col_top_cust:
        st.subheader("Top 10 Customers by Revenue")
        try:
            top_cust = _query(f"""
                SELECT
                    c.customer_id,
                    COALESCE(c.name, CONCAT('Customer #', CAST(c.customer_id AS STRING)))
                        AS customer_name,
                    ROUND(SUM({_REV}), 2) AS lifetime_revenue,
                    COUNT(*)               AS total_orders
                FROM {_t(MARTS, 'fact_orders')} f
                JOIN {_t(MARTS, 'dim_customers')} c ON f.customer_id = c.customer_id
                GROUP BY 1, 2
                ORDER BY lifetime_revenue DESC
                LIMIT 10
            """)
            if not top_cust.empty:
                fig = px.bar(
                    top_cust,
                    x="lifetime_revenue",
                    y="customer_name",
                    orientation="h",
                    color="total_orders",
                    color_continuous_scale="Oranges",
                    labels={"customer_name": "", "lifetime_revenue": "Revenue (USD)"},
                )
                fig.update_layout(
                    height=380,
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No customer revenue data.")
        except Exception as exc:
            st.error(f"Top customers failed: {exc}")

    # ── Geography ─────────────────────────────────────────────────────
    st.subheader("Customers by Country")
    try:
        geo = _query(f"""
            SELECT
                c.country,
                COUNT(DISTINCT c.customer_id) AS customers,
                ROUND(COALESCE(SUM({_REV}), 0), 2) AS total_revenue
            FROM {_t(MARTS, 'dim_customers')} c
            LEFT JOIN {_t(MARTS, 'fact_orders')} f ON c.customer_id = f.customer_id
            GROUP BY 1
            ORDER BY total_revenue DESC
            LIMIT 15
        """)
        if not geo.empty:
            fig = px.bar(
                geo,
                x="country",
                y="total_revenue",
                color="customers",
                color_continuous_scale=TEAL_SCALE,
                labels={"country": "Country", "total_revenue": "Revenue (USD)"},
                hover_data=["customers"],
            )
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No geographic data.")
    except Exception as exc:
        st.error(f"Geography query failed: {exc}")

    # ── Customer table ────────────────────────────────────────────────
    with st.expander("📋 Full Customer List"):
        try:
            cust_list = _query(f"""
                SELECT
                    c.customer_id,
                    c.name                                      AS customer_name,
                    c.city,
                    c.country,
                    COALESCE(c.customer_segment, 'Unknown')     AS segment,
                    COUNT(f.order_id)                            AS orders,
                    ROUND(COALESCE(SUM({_REV}), 0), 2)          AS revenue
                FROM {_t(MARTS, 'dim_customers')} c
                LEFT JOIN {_t(MARTS, 'fact_orders')} f ON c.customer_id = f.customer_id
                GROUP BY 1, 2, 3, 4, 5
                ORDER BY revenue DESC
            """)
            if not cust_list.empty:
                st.dataframe(cust_list, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Customer list failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — Pipeline Health
# ═══════════════════════════════════════════════════════════════════════
with tab_pipeline:
    # ── Deduplication proof (the interview money-shot) ────────────────
    st.subheader("🔍 Deduplication Proof")
    try:
        dedup = _query(f"""
            SELECT
                (SELECT COUNT(*) FROM {_t(STAGING, 'raw_orders')})   AS raw_rows,
                (SELECT COUNT(*) FROM {_t(STAGING, 'stg_orders')})   AS staged_rows,
                (SELECT COUNT(*) FROM {_t(MARTS, 'fact_orders')})    AS mart_rows,
                (SELECT COUNT(*) FROM (
                    SELECT order_id, COUNT(*) AS c
                    FROM {_t(MARTS, 'fact_orders')}
                    GROUP BY 1
                    HAVING c > 1
                ))                                                   AS duplicate_count
        """)
        d = dedup.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Raw Orders", f"{int(d['raw_rows']):,}")
        c2.metric("After Dedup (Staging)", f"{int(d['staged_rows']):,}")
        c3.metric("Fact Table", f"{int(d['mart_rows']):,}")
        dup_val = int(d["duplicate_count"])
        c4.metric(
            "Duplicates",
            dup_val,
            delta="✓ Zero duplicates" if dup_val == 0 else f"⚠ {dup_val} found",
            delta_color="off" if dup_val == 0 else "inverse",
        )
        if dup_val == 0:
            dedup_removed = int(d["raw_rows"]) - int(d["staged_rows"])
            st.success(
                f"**Idempotency verified:** {int(d['raw_rows']):,} raw → "
                f"{int(d['staged_rows']):,} staged ({dedup_removed} duplicates removed by "
                f"ROW_NUMBER) → {int(d['mart_rows']):,} in fact table via incremental MERGE. "
                f"Zero duplicates in the mart layer."
            )
    except Exception as exc:
        st.error(f"Dedup check failed: {exc}")

    st.divider()

    # ── Layer row counts ──────────────────────────────────────────────
    st.subheader("📊 Data Layer Row Counts")
    try:
        counts = _query(f"""
            SELECT 'raw_orders'         AS layer, 'staging' AS zone, COUNT(*) AS row_count FROM {_t(STAGING, 'raw_orders')}
            UNION ALL SELECT 'stg_orders',         'staging', COUNT(*) FROM {_t(STAGING, 'stg_orders')}
            UNION ALL SELECT 'stg_customers',      'staging', COUNT(*) FROM {_t(STAGING, 'stg_customers')}
            UNION ALL SELECT 'stg_products',       'staging', COUNT(*) FROM {_t(STAGING, 'stg_products')}
            UNION ALL SELECT 'stg_exchange_rates', 'staging', COUNT(*) FROM {_t(STAGING, 'stg_exchange_rates')}
            UNION ALL SELECT 'fact_orders',        'marts',   COUNT(*) FROM {_t(MARTS, 'fact_orders')}
            UNION ALL SELECT 'dim_customers',      'marts',   COUNT(*) FROM {_t(MARTS, 'dim_customers')}
            UNION ALL SELECT 'dim_products',       'marts',   COUNT(*) FROM {_t(MARTS, 'dim_products')}
            UNION ALL SELECT 'dim_date',           'marts',   COUNT(*) FROM {_t(MARTS, 'dim_date')}
            UNION ALL SELECT 'dim_currency',       'marts',   COUNT(*) FROM {_t(MARTS, 'dim_currency')}
        """)

        staging_df = counts[counts["zone"] == "staging"][["layer", "row_count"]]
        marts_df = counts[counts["zone"] == "marts"][["layer", "row_count"]]

        col_s, col_m = st.columns(2)
        with col_s:
            st.markdown("**Staging Layer**")
            st.dataframe(staging_df, use_container_width=True, hide_index=True)
        with col_m:
            st.markdown("**Marts Layer**")
            st.dataframe(marts_df, use_container_width=True, hide_index=True)

        # Visual bar chart of all layers
        fig = px.bar(
            counts,
            x="layer",
            y="row_count",
            color="zone",
            labels={"layer": "Table", "row_count": "Row Count", "zone": "Layer"},
            color_discrete_map={"staging": "#60a5fa", "marts": "#34d399"},
        )
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.error(f"Layer counts failed: {exc}")

    st.divider()

    # ── Pipeline runs ─────────────────────────────────────────────────
    st.subheader("🚀 Pipeline Run History")
    try:
        runs = _query(f"""
            SELECT
                pipeline_run_id,
                COUNT(*)             AS records,
                MIN(order_date)      AS earliest_order,
                MAX(order_date)      AS latest_order
            FROM {_t(MARTS, 'fact_orders')}
            GROUP BY 1
            ORDER BY earliest_order
        """)
        if not runs.empty:
            # Truncate UUIDs for display
            runs["run_short"] = runs["pipeline_run_id"].str[:8] + "…"
            fig = px.bar(
                runs,
                x="run_short",
                y="records",
                color="records",
                color_continuous_scale=BLUE_SCALE,
                labels={"run_short": "Pipeline Run", "records": "Records Loaded"},
                hover_data=["pipeline_run_id", "earliest_order", "latest_order"],
            )
            fig.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No pipeline runs recorded.")
    except Exception as exc:
        st.error(f"Pipeline runs query failed: {exc}")

    # ── Exchange rate coverage ────────────────────────────────────────
    st.subheader("💱 Exchange Rate Coverage")
    try:
        fx = _query(f"""
            SELECT
                COUNT(*)           AS total_currencies,
                MIN(rate_date)     AS earliest_rate,
                MAX(rate_date)     AS latest_rate
            FROM {_t(STAGING, 'stg_exchange_rates')}
        """)
        fx_row = fx.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Currencies Tracked", int(fx_row["total_currencies"]))
        c2.metric(
            "Earliest Rate",
            str(fx_row["earliest_rate"])[:10] if fx_row["earliest_rate"] else "N/A",
        )
        c3.metric(
            "Latest Rate",
            str(fx_row["latest_rate"])[:10] if fx_row["latest_rate"] else "N/A",
        )
    except Exception as exc:
        st.error(f"FX coverage failed: {exc}")


# ──────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Built with **Streamlit** · Data powered by **BigQuery** + **dbt** · "
    "Part of the [Retail Analytics Platform](https://github.com/rkendev/retail-analytics-platform) portfolio project"
)
