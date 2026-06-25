from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st


DEFAULT_DB_PATH = Path(__file__).with_name("perseus_equipment_database.db")
MAX_PREVIEW_ROWS = 5_000
LIGHT_CHART_COLORS = [
    "#2563eb",
    "#16a34a",
    "#f97316",
    "#9333ea",
    "#dc2626",
    "#0891b2",
    "#ca8a04",
    "#db2777",
]
DARK_CHART_COLORS = [
    "#60a5fa",
    "#34d399",
    "#fb923c",
    "#c084fc",
    "#f87171",
    "#22d3ee",
    "#facc15",
    "#f472b6",
]


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def invoice_type_label_sql(column_name: str) -> str:
    return f"""
        CASE LOWER(TRIM(CAST({column_name} AS TEXT)))
            WHEN 'in' THEN 'Invoice'
            WHEN 'wo' THEN 'Work Order'
            WHEN 'rl' THEN 'Rental'
            ELSE COALESCE(NULLIF(TRIM(CAST({column_name} AS TEXT)), ''), '(blank)')
        END
    """


def item_type_label_sql(column_name: str) -> str:
    return f"""
        CASE UPPER(TRIM(CAST({column_name} AS TEXT)))
            WHEN 'PA' THEN 'Parts'
            WHEN 'UN' THEN 'Units'
            WHEN 'SL' THEN 'Labor'
            WHEN 'MC' THEN 'Misc Charge'
            WHEN 'RU' THEN 'Rental Unit'
            WHEN 'TR' THEN 'Trade'
            ELSE COALESCE(NULLIF(TRIM(CAST({column_name} AS TEXT)), ''), '(blank)')
        END
    """


def parse_date_param(value: str | list[str] | None) -> date | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def clamp_date(value: date | None, minimum: date, maximum: date) -> date:
    if value is None:
        return minimum
    return min(max(value, minimum), maximum)


def display_dataframe(
    dataframe: pd.DataFrame,
    column_labels: dict[str, str],
    formats: dict[str, str],
) -> pd.io.formats.style.Styler:
    return dataframe.rename(columns=column_labels).style.format(
        {column_labels.get(column, column): value for column, value in formats.items()}
    )


def apply_theme(dark_mode: bool) -> None:
    px.defaults.template = "plotly_dark" if dark_mode else "plotly"
    px.defaults.color_discrete_sequence = (
        DARK_CHART_COLORS if dark_mode else LIGHT_CHART_COLORS
    )

    if dark_mode:
        st.markdown(
            """
            <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(37, 99, 235, 0.24), transparent 32rem),
                    linear-gradient(135deg, #0e1117 0%, #111827 55%, #171923 100%);
                color: #f5f7fa;
            }

            [data-testid="stHeader"],
            [data-testid="stToolbar"] {
                background: transparent;
            }

            h1, h2, h3 {
                color: #f8fafc;
            }

            [data-testid="stMetric"],
            [data-testid="stExpander"],
            div[data-testid="stDataFrame"] {
                background: rgba(15, 23, 42, 0.96);
                border: 1px solid rgba(96, 165, 250, 0.35);
                border-radius: 0.75rem;
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.24);
            }

            [data-testid="stMetric"] label,
            [data-testid="stMetricLabel"],
            [data-testid="stMetricLabel"] p {
                color: #cbd5e1 !important;
            }

            [data-testid="stMetricValue"],
            [data-testid="stMetricValue"] div {
                color: #f8fafc !important;
                opacity: 1 !important;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.5rem;
                border-bottom-color: #30363d;
            }

            .stTabs [data-baseweb="tab"] {
                color: #c9d1d9;
                background: rgba(96, 165, 250, 0.08);
                border-radius: 999px;
                padding: 0.5rem 1rem;
            }

            .stTabs [aria-selected="true"] {
                color: #ffffff;
                background: linear-gradient(90deg, #2563eb, #7c3aed);
            }

            div[data-testid="stDateInput"] input {
                border-color: #2563eb;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.14), transparent 30rem),
                linear-gradient(135deg, #f8fafc 0%, #eef2ff 55%, #fff7ed 100%);
            color: #0f172a;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"] {
            background: transparent;
        }

        h1 {
            color: #1e3a8a;
        }

        h2, h3 {
            color: #0f172a;
        }

        [data-testid="stMetric"],
        [data-testid="stExpander"],
        div[data-testid="stDataFrame"] {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 0.75rem;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            border-bottom-color: rgba(37, 99, 235, 0.18);
        }

        .stTabs [data-baseweb="tab"] {
            color: #334155;
            background: rgba(37, 99, 235, 0.08);
            border-radius: 999px;
            padding: 0.5rem 1rem;
        }

        .stTabs [aria-selected="true"] {
            color: #ffffff;
            background: linear-gradient(90deg, #2563eb, #7c3aed);
        }

        div[data-testid="stDateInput"] input {
            border-color: #2563eb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def open_database(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


@st.cache_data(show_spinner=False)
def list_tables(db_path: str) -> list[str]:
    with open_database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    return [row[0] for row in rows]


@st.cache_data(show_spinner=False)
def table_columns(db_path: str, table_name: str) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            f"PRAGMA table_info({quote_identifier(table_name)})",
            connection,
        )


@st.cache_data(show_spinner=False)
def table_row_count(db_path: str, table_name: str) -> int:
    with open_database(db_path) as connection:
        row = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
        ).fetchone()
    return int(row[0])


@st.cache_data(show_spinner=False)
def load_table(db_path: str, table_name: str, limit: int) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            f"SELECT * FROM {quote_identifier(table_name)} LIMIT ?",
            connection,
            params=(limit,),
        )


@st.cache_data(show_spinner=False)
def load_invoice_date_range(db_path: str) -> tuple[date | None, date | None]:
    with open_database(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                MIN(DATE(ActivityDate)) AS min_date,
                MAX(DATE(ActivityDate)) AS max_date
            FROM InvoiceHeader
            WHERE IsActive = 1
              AND ActivityDate IS NOT NULL
            """
        ).fetchone()

    if not row["min_date"] or not row["max_date"]:
        return None, None

    return date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"])


@st.cache_data(show_spinner=False)
def load_active_invoice_summary(
    db_path: str,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    invoice_type_label = invoice_type_label_sql("InvoiceType")
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            f"""
            SELECT
                {invoice_type_label} AS invoice_type,
                COUNT(*) AS invoice_count,
                SUM(COALESCE(TotalInvoice, 0)) AS total_invoice
            FROM InvoiceHeader
            WHERE IsActive = 1
              AND (? IS NULL OR DATE(ActivityDate) >= ?)
              AND (? IS NULL OR DATE(ActivityDate) <= ?)
            GROUP BY {invoice_type_label}
            ORDER BY invoice_count DESC
            """,
            connection,
            params=(start_date, start_date, end_date, end_date),
        )


@st.cache_data(show_spinner=False)
def load_active_item_type_summary(
    db_path: str,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    item_type_label = item_type_label_sql("d.ItemType")
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            f"""
            SELECT
                {item_type_label} AS item_type,
                COUNT(*) AS line_count,
                SUM(COALESCE(d.Qty, 0)) AS quantity,
                SUM(COALESCE(d.NetExt, 0)) AS net_ext
            FROM InvoiceDetail d
            JOIN InvoiceHeader h ON h.InvoiceDocId = d.InvoiceDocId
            WHERE h.IsActive = 1
              AND d.IsActive = 1
              AND UPPER(TRIM(CAST(d.ItemType AS TEXT))) NOT IN ('RE', 'QU')
              AND (? IS NULL OR DATE(h.ActivityDate) >= ?)
              AND (? IS NULL OR DATE(h.ActivityDate) <= ?)
            GROUP BY {item_type_label}
            ORDER BY line_count DESC
            """,
            connection,
            params=(start_date, start_date, end_date, end_date),
        )


@st.cache_data(show_spinner=False)
def load_active_item_type_by_invoice_type(
    db_path: str,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    invoice_type_label = invoice_type_label_sql("h.InvoiceType")
    item_type_label = item_type_label_sql("d.ItemType")
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            f"""
            SELECT
                {invoice_type_label} AS invoice_type,
                {item_type_label} AS item_type,
                COUNT(*) AS line_count,
                SUM(COALESCE(d.Qty, 0)) AS quantity,
                SUM(COALESCE(d.NetExt, 0)) AS net_ext
            FROM InvoiceDetail d
            JOIN InvoiceHeader h ON h.InvoiceDocId = d.InvoiceDocId
            WHERE h.IsActive = 1
              AND d.IsActive = 1
              AND UPPER(TRIM(CAST(d.ItemType AS TEXT))) NOT IN ('RE', 'QU')
              AND (? IS NULL OR DATE(h.ActivityDate) >= ?)
              AND (? IS NULL OR DATE(h.ActivityDate) <= ?)
            GROUP BY
                {invoice_type_label},
                {item_type_label}
            ORDER BY invoice_type, line_count DESC
            """,
            connection,
            params=(start_date, start_date, end_date, end_date),
        )


@st.cache_data(show_spinner=False)
def load_unit_sales_by_category(
    db_path: str,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT
                COALESCE(
                    NULLIF(TRIM(uc.DisplayText), ''),
                    NULLIF(TRIM(su.CategoryCode), ''),
                    '(blank)'
                ) AS category,
                COUNT(*) AS line_count,
                SUM(COALESCE(su.Qty, 0)) AS quantity,
                SUM(COALESCE(su.NetExt, d.NetExt, 0)) AS sales_dollars,
                SUM(COALESCE(su.InvoiceCost, 0)) AS invoice_cost
            FROM SaleUnit su
            JOIN InvoiceDetail d ON d.ItemId = su.ItemId
            JOIN InvoiceHeader h ON h.InvoiceDocId = d.InvoiceDocId
            LEFT JOIN UnitBase ub ON ub.UnitId = su.UnitId
            LEFT JOIN UnitCategory uc ON uc.UnitCategoryId = ub.UnitCategoryId
            WHERE h.IsActive = 1
              AND d.IsActive = 1
              AND UPPER(TRIM(CAST(d.ItemType AS TEXT))) = 'UN'
              AND (? IS NULL OR DATE(h.ActivityDate) >= ?)
              AND (? IS NULL OR DATE(h.ActivityDate) <= ?)
            GROUP BY
                COALESCE(
                    NULLIF(TRIM(uc.DisplayText), ''),
                    NULLIF(TRIM(su.CategoryCode), ''),
                    '(blank)'
                )
            ORDER BY sales_dollars DESC
            """,
            connection,
            params=(start_date, start_date, end_date, end_date),
        )


@st.cache_data(show_spinner=False)
def load_rental_usage_by_group(
    db_path: str,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            """
            WITH fallback_group AS (
                SELECT
                    UnitGroupId,
                    MIN(DisplayText) AS DisplayText
                FROM RentalGroup
                WHERE UnitGroupId IS NOT NULL
                GROUP BY UnitGroupId
            )
            SELECT
                COALESCE(
                    NULLIF(TRIM(rg.DisplayText), ''),
                    NULLIF(TRIM(fg.DisplayText), ''),
                    '(blank)'
                ) AS rental_group,
                COUNT(DISTINCT h.InvoiceDocId) AS invoice_count,
                COUNT(DISTINCT ru.UnitId) AS unit_count,
                SUM(COALESCE(ru.DurationQty, 0)) AS duration_quantity,
                SUM(COALESCE(ru.NetExt, d.NetExt, 0)) AS rental_revenue
            FROM RentalUnit ru
            JOIN InvoiceDetail d ON d.ItemId = ru.ItemId
            JOIN InvoiceHeader h ON h.InvoiceDocId = d.InvoiceDocId
            LEFT JOIN UnitBase ub ON ub.UnitId = ru.UnitId
            LEFT JOIN RentalGroup rg ON rg.RentalGroupId = ub.RentalGroupId
            LEFT JOIN fallback_group fg ON fg.UnitGroupId = ru.UnitGroupId
            WHERE h.IsActive = 1
              AND d.IsActive = 1
              AND (? IS NULL OR DATE(h.ActivityDate) >= ?)
              AND (? IS NULL OR DATE(h.ActivityDate) <= ?)
            GROUP BY
                COALESCE(
                    NULLIF(TRIM(rg.DisplayText), ''),
                    NULLIF(TRIM(fg.DisplayText), ''),
                    '(blank)'
                )
            ORDER BY rental_revenue DESC
            """,
            connection,
            params=(start_date, start_date, end_date, end_date),
        )


@st.cache_data(show_spinner=False)
def load_customers_by_class(db_path: str) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT
                COALESCE(NULLIF(TRIM(cct.DisplayText), ''), '(blank)') AS class_name,
                COUNT(DISTINCT cc.CustomerId) AS active_customers
            FROM CustomerClass cc
            JOIN CustomerClassType cct ON cct.ClassTypeId = cc.ClassTypeId
            JOIN Customer c ON c.CustomerId = cc.CustomerId
            WHERE cc.IsActive = 1
              AND c.IsActive = 1
            GROUP BY COALESCE(NULLIF(TRIM(cct.DisplayText), ''), '(blank)')
            ORDER BY active_customers DESC, class_name
            """,
            connection,
        )


@st.cache_data(show_spinner=False)
def load_top_customers_by_sales(
    db_path: str,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT
                c.CustomerNo AS customer_no,
                COALESCE(NULLIF(TRIM(c.CustomerName), ''), h.CustomerName, '(blank)') AS customer_name,
                COUNT(DISTINCT h.InvoiceDocId) AS invoice_count,
                SUM(COALESCE(h.TotalInvoice, 0)) AS sales_dollars
            FROM InvoiceHeader h
            JOIN Customer c ON c.CustomerId = h.CustomerId
            WHERE h.IsActive = 1
              AND c.IsActive = 1
              AND (? IS NULL OR DATE(h.ActivityDate) >= ?)
              AND (? IS NULL OR DATE(h.ActivityDate) <= ?)
            GROUP BY
                c.CustomerId,
                c.CustomerNo,
                COALESCE(NULLIF(TRIM(c.CustomerName), ''), h.CustomerName, '(blank)')
            ORDER BY sales_dollars DESC
            LIMIT 30
            """,
            connection,
            params=(start_date, start_date, end_date, end_date),
        )


@st.cache_data(show_spinner=False)
def load_customer_ar_balances(db_path: str) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT
                prd.BillToCustomerNo AS customer_no,
                COALESCE(NULLIF(TRIM(prd.BillToCustomerName), ''), '(blank)') AS customer_name,
                COUNT(DISTINCT p.InvoiceDocId) AS invoice_count,
                SUM(COALESCE(p.Amount, 0)) AS ar_balance
            FROM Payment p
            JOIN PaymentReceivablesDetail prd ON prd.PaymentId = p.PaymentId
            JOIN Customer c ON c.CustomerId = prd.BillToCustomerId
            WHERE p.IsActive = 1
              AND c.IsActive = 1
              AND p.PmtType IN ('recv', 'recvpmt')
            GROUP BY
                prd.BillToCustomerId,
                prd.BillToCustomerNo,
                COALESCE(NULLIF(TRIM(prd.BillToCustomerName), ''), '(blank)')
            HAVING ABS(SUM(COALESCE(p.Amount, 0))) >= 0.01
            ORDER BY ar_balance DESC
            """,
            connection,
        )


@st.cache_data(show_spinner=False)
def load_ar_aging_summary(db_path: str, as_of_date: date) -> pd.DataFrame:
    with open_database(db_path) as connection:
        row = connection.execute(
            """
            WITH invoice_ar AS (
                SELECT
                    h.InvoiceDocId,
                    h.ActivityDate,
                    MAX(COALESCE(prd.DaysDue, 0)) AS days_due,
                    SUM(COALESCE(p.Amount, 0)) AS balance
                FROM Payment p
                JOIN PaymentReceivablesDetail prd ON prd.PaymentId = p.PaymentId
                JOIN InvoiceHeader h ON h.InvoiceDocId = p.InvoiceDocId
                JOIN Customer c ON c.CustomerId = prd.BillToCustomerId
                WHERE p.IsActive = 1
                  AND h.IsActive = 1
                  AND c.IsActive = 1
                  AND p.PmtType IN ('recv', 'recvpmt')
                GROUP BY h.InvoiceDocId, h.ActivityDate
                HAVING ABS(SUM(COALESCE(p.Amount, 0))) >= 0.01
            ),
            aged_invoice_ar AS (
                SELECT
                    balance,
                    JULIANDAY(?) - JULIANDAY(DATE(ActivityDate, '+' || days_due || ' days')) AS days_past_due
                FROM invoice_ar
            )
            SELECT
                SUM(CASE WHEN days_past_due <= 0 THEN balance ELSE 0 END) AS current_balance,
                SUM(CASE WHEN days_past_due BETWEEN 1 AND 30 THEN balance ELSE 0 END) AS balance_30,
                SUM(CASE WHEN days_past_due BETWEEN 31 AND 60 THEN balance ELSE 0 END) AS balance_60,
                SUM(CASE WHEN days_past_due BETWEEN 61 AND 90 THEN balance ELSE 0 END) AS balance_90,
                SUM(CASE WHEN days_past_due > 90 THEN balance ELSE 0 END) AS balance_90_plus
            FROM aged_invoice_ar
            """,
            (as_of_date,),
        ).fetchone()

    return pd.DataFrame(
        [
            {"bucket": "Current", "ar_balance": row["current_balance"] or 0},
            {"bucket": "1-30 Days", "ar_balance": row["balance_30"] or 0},
            {"bucket": "31-60 Days", "ar_balance": row["balance_60"] or 0},
            {"bucket": "61-90 Days", "ar_balance": row["balance_90"] or 0},
            {"bucket": "90+ Days", "ar_balance": row["balance_90_plus"] or 0},
        ]
    )


@st.cache_data(show_spinner=False)
def load_customers_with_no_sales_since(
    db_path: str,
    cutoff_date: date,
    five_year_cutoff_date: date,
) -> pd.DataFrame:
    with open_database(db_path) as connection:
        return pd.read_sql_query(
            """
            WITH customer_sales AS (
                SELECT
                    h.CustomerId,
                    MAX(DATE(h.ActivityDate)) AS last_sale_date,
                    COUNT(DISTINCT h.InvoiceDocId) AS lifetime_invoice_count,
                    SUM(COALESCE(h.TotalInvoice, 0)) AS lifetime_sales,
                    COUNT(
                        DISTINCT CASE
                            WHEN DATE(h.ActivityDate) >= ? THEN h.InvoiceDocId
                        END
                    ) AS five_year_invoice_count
                FROM InvoiceHeader h
                WHERE h.IsActive = 1
                  AND h.ActivityDate IS NOT NULL
                  AND COALESCE(h.TotalInvoice, 0) > 0
                GROUP BY h.CustomerId
            )
            SELECT
                c.CustomerNo AS customer_no,
                COALESCE(NULLIF(TRIM(c.CustomerName), ''), '(blank)') AS customer_name,
                COALESCE(cs.last_sale_date, 'No Sales') AS last_sale_date,
                COALESCE(cs.lifetime_invoice_count, 0) AS lifetime_invoice_count,
                COALESCE(cs.five_year_invoice_count, 0) AS five_year_invoice_count,
                COALESCE(cs.lifetime_sales, 0) AS lifetime_sales
            FROM Customer c
            LEFT JOIN customer_sales cs ON cs.CustomerId = c.CustomerId
            WHERE c.IsActive = 1
              AND (cs.last_sale_date IS NULL OR cs.last_sale_date < ?)
              AND COALESCE(cs.five_year_invoice_count, 0) > 5
            ORDER BY
                cs.five_year_invoice_count DESC,
                cs.last_sale_date DESC,
                customer_name
            """,
            connection,
            params=(five_year_cutoff_date, cutoff_date),
        )


def detect_datetime_columns(dataframe: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    date_keywords = ("date", "time", "created", "updated", "timestamp")

    for column in dataframe.columns:
        if not any(keyword in column.lower() for keyword in date_keywords):
            continue

        parsed = pd.to_datetime(dataframe[column], errors="coerce")
        if parsed.notna().mean() >= 0.6:
            candidates.append(column)

    return candidates


def numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    return dataframe.select_dtypes(include="number").columns.tolist()


def categorical_columns(dataframe: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in dataframe.columns:
        unique_count = dataframe[column].nunique(dropna=True)
        if 1 < unique_count <= min(50, max(2, len(dataframe) // 2)):
            columns.append(column)
    return columns


def render_schema(db_path: str, tables: Iterable[str]) -> None:
    st.subheader("Database Schema")
    for table_name in tables:
        with st.expander(table_name):
            columns = table_columns(db_path, table_name)
            st.dataframe(
                columns[["name", "type", "notnull", "pk"]],
                use_container_width=True,
                hide_index=True,
            )


def render_active_invoice_dashboard(db_path: str) -> None:
    st.subheader("Invoice Dashboard")

    min_date, max_date = load_invoice_date_range(db_path)
    start_date: date | None = None
    end_date: date | None = None

    if min_date and max_date:
        allowed_max_date = max(date.today(), max_date)
        query_start = parse_date_param(st.query_params.get("invoice_start"))
        query_end = parse_date_param(st.query_params.get("invoice_end"))
        default_start = clamp_date(query_start, min_date, allowed_max_date)
        default_end = clamp_date(query_end, min_date, allowed_max_date)

        if default_start > default_end:
            default_start, default_end = default_end, default_start

        selected_dates = st.date_input(
            "Invoice date range",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=allowed_max_date,
            format="MM/DD/YYYY",
            key="invoice_date_range",
        )

        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            start_date, end_date = selected_dates
            st.query_params["invoice_start"] = start_date.isoformat()
            st.query_params["invoice_end"] = end_date.isoformat()
        else:
            st.info("Select both a start date and an end date to filter invoices.")

    invoice_summary = load_active_invoice_summary(db_path, start_date, end_date)
    item_summary = load_active_item_type_summary(db_path, start_date, end_date)
    unit_sales = load_unit_sales_by_category(db_path, start_date, end_date)
    if invoice_summary.empty or item_summary.empty:
        st.info("No invoice data was found for the selected date range.")
        return

    active_invoice_count = int(invoice_summary["invoice_count"].sum())
    active_invoice_total = float(invoice_summary["total_invoice"].sum())
    active_line_count = int(item_summary["line_count"].sum())
    active_item_type_count = int(item_summary["item_type"].nunique())

    metric_columns = st.columns(4)
    metric_columns[0].metric("Invoices", f"{active_invoice_count:,}")
    metric_columns[1].metric("Invoice total", f"${active_invoice_total:,.0f}")
    metric_columns[2].metric("Item lines", f"{active_line_count:,}")
    metric_columns[3].metric("Item types", f"{active_item_type_count:,}")

    left_column, right_column = st.columns(2)

    with left_column:
        fig = px.bar(
            invoice_summary,
            x="invoice_type",
            y="invoice_count",
            text_auto=True,
            title="Invoices by Invoice Type",
            labels={"invoice_type": "Invoice type", "invoice_count": "Invoices"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with right_column:
        fig = px.pie(
            invoice_summary,
            names="invoice_type",
            values="total_invoice",
            title="Invoice Total by Invoice Type",
        )
        fig.update_traces(
            textinfo="label+value",
            texttemplate="%{label}<br>$%{value:,.0f}",
        )
        st.plotly_chart(fig, use_container_width=True)

    left_column, right_column = st.columns(2)

    with left_column:
        fig = px.bar(
            item_summary,
            x="item_type",
            y="line_count",
            text_auto=True,
            title="Invoice Lines by Item Type",
            labels={"item_type": "Item type", "line_count": "Lines"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with right_column:
        fig = px.bar(
            item_summary.sort_values("net_ext", ascending=False),
            x="item_type",
            y="net_ext",
            text_auto=".2s",
            title="Net Extended Amount by Item Type",
            labels={"item_type": "Item type", "net_ext": "Net extended amount"},
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Unit Sales by Category")
    if unit_sales.empty:
        st.info("No unit sales were found for the selected date range.")
    else:
        unit_sales_total = float(unit_sales["sales_dollars"].sum())
        unit_quantity = float(unit_sales["quantity"].sum())
        unit_cost = float(unit_sales["invoice_cost"].sum())
        unit_margin = unit_sales_total - unit_cost

        metric_columns = st.columns(4)
        metric_columns[0].metric("Unit sales", f"${unit_sales_total:,.2f}")
        metric_columns[1].metric("Units sold", f"{unit_quantity:,.0f}")
        metric_columns[2].metric("Unit cost", f"${unit_cost:,.2f}")
        metric_columns[3].metric("Unit margin", f"${unit_margin:,.2f}")

        left_column, right_column = st.columns(2)

        with left_column:
            fig = px.bar(
                unit_sales,
                x="category",
                y="sales_dollars",
                text_auto=".2s",
                title="Unit Sales Dollars by Category",
                labels={"category": "Category", "sales_dollars": "Sales dollars"},
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        with right_column:
            fig = px.bar(
                unit_sales.sort_values("quantity", ascending=False),
                x="category",
                y="quantity",
                text_auto=True,
                title="Units Sold by Category",
                labels={"category": "Category", "quantity": "Units sold"},
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("Summary Data"):
        st.write("Invoices by type")
        st.dataframe(
            display_dataframe(
                invoice_summary,
                {
                    "invoice_type": "Invoice Type",
                    "invoice_count": "Invoice Count",
                    "total_invoice": "Invoice Total",
                },
                {
                    "invoice_count": "{:,.0f}",
                    "total_invoice": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.write("Unit sales by category")
        st.dataframe(
            display_dataframe(
                unit_sales.drop(columns=["line_count"], errors="ignore"),
                {
                    "category": "Category",
                    "quantity": "Quantity",
                    "sales_dollars": "Sales Dollars",
                    "invoice_cost": "Invoice Cost",
                },
                {
                    "quantity": "{:,.0f}",
                    "sales_dollars": "${:,.2f}",
                    "invoice_cost": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.write("Invoice lines by item type")
        st.dataframe(
            display_dataframe(
                item_summary.drop(columns=["line_count"], errors="ignore"),
                {
                    "item_type": "Item Type",
                    "quantity": "Quantity",
                    "net_ext": "Net Extended",
                },
                {
                    "quantity": "{:,.2f}",
                    "net_ext": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_customers_by_class_dashboard(db_path: str) -> None:
    st.subheader("Customers by Class")

    class_summary = load_customers_by_class(db_path)
    if class_summary.empty:
        st.info("No customer class data was found.")
        return

    active_customers = int(class_summary["active_customers"].sum())
    class_count = int(class_summary["class_name"].nunique())

    metric_columns = st.columns(2)
    metric_columns[0].metric("Customers", f"{active_customers:,}")
    metric_columns[1].metric("Classes", f"{class_count:,}")

    fig = px.bar(
        class_summary,
        x="class_name",
        y="active_customers",
        text_auto=True,
        title="Customers by Class",
        labels={"class_name": "Customer class", "active_customers": "Customers"},
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    fig = px.pie(
        class_summary,
        names="class_name",
        values="active_customers",
        title="Customer Class Mix",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 30 Customers by Sales Dollars")
    customer_start_date: date | None = None
    customer_end_date: date | None = None
    min_date, max_date = load_invoice_date_range(db_path)

    if min_date and max_date:
        allowed_max_date = max(date.today(), max_date)
        query_start = parse_date_param(st.query_params.get("customer_sales_start"))
        query_end = parse_date_param(st.query_params.get("customer_sales_end"))
        default_start = clamp_date(query_start, min_date, allowed_max_date)
        default_end = clamp_date(query_end, min_date, allowed_max_date)

        if default_start > default_end:
            default_start, default_end = default_end, default_start

        selected_dates = st.date_input(
            "Customer sales date range",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=allowed_max_date,
            format="MM/DD/YYYY",
            key="customer_sales_date_range",
        )

        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            customer_start_date, customer_end_date = selected_dates
            st.query_params["customer_sales_start"] = customer_start_date.isoformat()
            st.query_params["customer_sales_end"] = customer_end_date.isoformat()
        else:
            st.info("Select both a start date and an end date to filter customer sales.")

    top_customers = load_top_customers_by_sales(
        db_path,
        customer_start_date,
        customer_end_date,
    )

    if top_customers.empty:
        st.info("No customer sales data was found.")
    else:
        chart_data = top_customers.sort_values("sales_dollars", ascending=True)
        fig = px.bar(
            chart_data,
            x="sales_dollars",
            y="customer_name",
            orientation="h",
            text="sales_dollars",
            title="Top 30 Customers by Sales Dollars",
            labels={"sales_dollars": "Sales dollars", "customer_name": "Customer"},
        )
        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(height=max(600, len(chart_data) * 28))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Customers with No Sales in the Past Year")
    today = date.today()
    no_sales_cutoff = today.replace(year=today.year - 1)
    five_year_cutoff = today.replace(year=today.year - 5)
    no_sales_customers = load_customers_with_no_sales_since(
        db_path,
        no_sales_cutoff,
        five_year_cutoff,
    )

    if no_sales_customers.empty:
        st.info("Every active customer has sales in the past year.")
    else:
        metric_columns = st.columns(2)
        metric_columns[0].metric("Customers", f"{len(no_sales_customers):,}")
        metric_columns[1].metric("Since", no_sales_cutoff.strftime("%m/%d/%Y"))

        st.dataframe(
            display_dataframe(
                no_sales_customers,
                {
                    "customer_no": "Customer No",
                    "customer_name": "Customer Name",
                    "last_sale_date": "Last Sale Date",
                    "lifetime_invoice_count": "Lifetime Invoice Count",
                    "five_year_invoice_count": "Past 5 Year Invoice Count",
                    "lifetime_sales": "Lifetime Sales",
                },
                {
                    "lifetime_invoice_count": "{:,.0f}",
                    "five_year_invoice_count": "{:,.0f}",
                    "lifetime_sales": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Summary Data"):
        st.dataframe(
            display_dataframe(
                class_summary,
                {
                    "class_name": "Customer Class",
                    "active_customers": "Customers",
                },
                {
                    "active_customers": "{:,.0f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.write("Customers with no sales in the past year")
        st.dataframe(
            display_dataframe(
                no_sales_customers,
                {
                    "customer_no": "Customer No",
                    "customer_name": "Customer Name",
                    "last_sale_date": "Last Sale Date",
                    "lifetime_invoice_count": "Lifetime Invoice Count",
                    "five_year_invoice_count": "Past 5 Year Invoice Count",
                    "lifetime_sales": "Lifetime Sales",
                },
                {
                    "lifetime_invoice_count": "{:,.0f}",
                    "five_year_invoice_count": "{:,.0f}",
                    "lifetime_sales": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.write("Top 30 customers by sales dollars")
        st.dataframe(
            display_dataframe(
                top_customers,
                {
                    "customer_no": "Customer No",
                    "customer_name": "Customer Name",
                    "invoice_count": "Invoice Count",
                    "sales_dollars": "Sales Dollars",
                },
                {
                    "invoice_count": "{:,.0f}",
                    "sales_dollars": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
            height=min(1_200, max(450, len(top_customers) * 36)),
        )
def render_ar_dashboard(db_path: str) -> None:
    st.subheader("Customer AR Balances")

    ar_balances = load_customer_ar_balances(db_path)
    ar_aging = load_ar_aging_summary(db_path, date.today())
    if ar_balances.empty:
        st.info("No customer AR balances were found.")
        return

    total_ar_balance = float(ar_balances["ar_balance"].sum())
    customers_with_balance = int(len(ar_balances))
    past_due_customers = int((ar_balances["ar_balance"] > 0).sum())
    credit_balance_customers = int((ar_balances["ar_balance"] < 0).sum())

    metric_columns = st.columns(4)
    metric_columns[0].metric("AR balance", f"${total_ar_balance:,.2f}")
    metric_columns[1].metric("Customers with balance", f"{customers_with_balance:,}")
    metric_columns[2].metric("Positive balances", f"{past_due_customers:,}")
    metric_columns[3].metric("Credit balances", f"{credit_balance_customers:,}")

    st.subheader("AR Aging")
    aging_columns = st.columns(len(ar_aging))
    for index, row in ar_aging.iterrows():
        aging_columns[index].metric(row["bucket"], f"${row['ar_balance']:,.2f}")

    fig = px.bar(
        ar_aging,
        x="bucket",
        y="ar_balance",
        text_auto=".2s",
        title="AR Totals by Aging Bucket",
        labels={"bucket": "Aging bucket", "ar_balance": "AR balance"},
    )
    st.plotly_chart(fig, use_container_width=True)

    chart_data = ar_balances.head(30).sort_values("ar_balance", ascending=True)
    fig = px.bar(
        chart_data,
        x="ar_balance",
        y="customer_name",
        orientation="h",
        text="ar_balance",
        title="Top 30 Customer AR Balances",
        labels={"ar_balance": "AR balance", "customer_name": "Customer"},
    )
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig.update_layout(height=max(600, len(chart_data) * 28))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Summary Data"):
        st.write("AR aging")
        st.dataframe(
            display_dataframe(
                ar_aging,
                {
                    "bucket": "Aging Bucket",
                    "ar_balance": "AR Balance",
                },
                {
                    "ar_balance": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.write("Customer AR balances")
        st.dataframe(
            display_dataframe(
                ar_balances,
                {
                    "customer_no": "Customer No",
                    "customer_name": "Customer Name",
                    "invoice_count": "Invoice Count",
                    "ar_balance": "AR Balance",
                },
                {
                    "invoice_count": "{:,.0f}",
                    "ar_balance": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_rental_dashboard(db_path: str) -> None:
    st.subheader("Rental Usage by Rental Group")

    min_date, max_date = load_invoice_date_range(db_path)
    start_date: date | None = None
    end_date: date | None = None

    if min_date and max_date:
        allowed_max_date = max(date.today(), max_date)
        query_start = parse_date_param(st.query_params.get("rental_start"))
        query_end = parse_date_param(st.query_params.get("rental_end"))
        default_start = clamp_date(query_start, min_date, allowed_max_date)
        default_end = clamp_date(query_end, min_date, allowed_max_date)

        if default_start > default_end:
            default_start, default_end = default_end, default_start

        selected_dates = st.date_input(
            "Rental date range",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=allowed_max_date,
            format="MM/DD/YYYY",
            key="rental_date_range",
        )

        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            start_date, end_date = selected_dates
            st.query_params["rental_start"] = start_date.isoformat()
            st.query_params["rental_end"] = end_date.isoformat()
        else:
            st.info("Select both a start date and an end date to filter rentals.")

    rental_usage = load_rental_usage_by_group(db_path, start_date, end_date)

    if rental_usage.empty:
        st.info("No rental usage was found for the selected date range.")
        return

    rental_revenue = float(rental_usage["rental_revenue"].sum())
    rental_duration = float(rental_usage["duration_quantity"].sum())
    rental_invoice_count = int(rental_usage["invoice_count"].sum())
    rental_unit_count = int(rental_usage["unit_count"].sum())

    metric_columns = st.columns(4)
    metric_columns[0].metric("Rental revenue", f"${rental_revenue:,.2f}")
    metric_columns[1].metric("Duration quantity", f"{rental_duration:,.2f}")
    metric_columns[2].metric("Invoices", f"{rental_invoice_count:,}")
    metric_columns[3].metric("Units", f"{rental_unit_count:,}")

    left_column, right_column = st.columns(2)

    with left_column:
        fig = px.bar(
            rental_usage,
            x="rental_group",
            y="rental_revenue",
            text_auto=".2s",
            title="Rental Revenue by Rental Group",
            labels={"rental_group": "Rental group", "rental_revenue": "Rental revenue"},
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with right_column:
        fig = px.bar(
            rental_usage.sort_values("duration_quantity", ascending=False),
            x="rental_group",
            y="duration_quantity",
            text_auto=".2s",
            title="Rental Duration by Rental Group",
            labels={
                "rental_group": "Rental group",
                "duration_quantity": "Duration quantity",
            },
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Summary Data"):
        st.dataframe(
            display_dataframe(
                rental_usage,
                {
                    "rental_group": "Rental Group",
                    "invoice_count": "Invoice Count",
                    "unit_count": "Unit Count",
                    "duration_quantity": "Duration Quantity",
                    "rental_revenue": "Rental Revenue",
                },
                {
                    "invoice_count": "{:,.0f}",
                    "unit_count": "{:,.0f}",
                    "duration_quantity": "{:,.2f}",
                    "rental_revenue": "${:,.2f}",
                },
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_table_profile(db_path: str, table_name: str) -> pd.DataFrame:
    row_count = table_row_count(db_path, table_name)
    preview_limit = st.slider(
        "Rows to load",
        min_value=100,
        max_value=MAX_PREVIEW_ROWS,
        value=min(1_000, MAX_PREVIEW_ROWS),
        step=100,
    )

    dataframe = load_table(db_path, table_name, preview_limit)

    st.subheader("Overview")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Rows in table", f"{row_count:,}")
    metric_columns[1].metric("Rows loaded", f"{len(dataframe):,}")
    metric_columns[2].metric("Columns", f"{len(dataframe.columns):,}")
    metric_columns[3].metric("Missing cells", f"{int(dataframe.isna().sum().sum()):,}")

    st.subheader("Data Preview")
    st.dataframe(dataframe, use_container_width=True)

    return dataframe


def render_visual_builder(dataframe: pd.DataFrame) -> None:
    st.subheader("Visual Builder")

    if dataframe.empty:
        st.info("No rows were loaded from this table.")
        return

    nums = numeric_columns(dataframe)
    cats = categorical_columns(dataframe)
    dates = detect_datetime_columns(dataframe)

    chart_type = st.selectbox(
        "Chart type",
        ["Bar", "Histogram", "Scatter", "Line over time"],
    )

    if chart_type == "Bar":
        if not cats:
            st.info("No categorical columns were detected for a bar chart.")
            return
        category = st.selectbox("Group by", cats)
        aggregation = st.selectbox("Metric", ["Record count"] + nums)
        if aggregation == "Record count":
            chart_data = dataframe[category].value_counts(dropna=False).reset_index()
            chart_data.columns = [category, "count"]
            fig = px.bar(chart_data, x=category, y="count", title=f"Count by {category}")
        else:
            chart_data = (
                dataframe.groupby(category, dropna=False)[aggregation]
                .sum()
                .reset_index()
                .sort_values(aggregation, ascending=False)
            )
            fig = px.bar(
                chart_data,
                x=category,
                y=aggregation,
                title=f"Sum of {aggregation} by {category}",
            )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Histogram":
        if not nums:
            st.info("No numeric columns were detected for a histogram.")
            return
        value = st.selectbox("Numeric column", nums)
        fig = px.histogram(dataframe, x=value, title=f"Distribution of {value}")
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Scatter":
        if len(nums) < 2:
            st.info("At least two numeric columns are needed for a scatter plot.")
            return
        x_axis = st.selectbox("X axis", nums, index=0)
        y_axis = st.selectbox("Y axis", nums, index=1)
        color = st.selectbox("Color by", ["None"] + cats)
        fig = px.scatter(
            dataframe,
            x=x_axis,
            y=y_axis,
            color=None if color == "None" else color,
            title=f"{y_axis} by {x_axis}",
        )
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Line over time":
        if not dates or not nums:
            st.info("A date/time-like column and a numeric column are needed for a line chart.")
            return
        date_column = st.selectbox("Date column", dates)
        value_column = st.selectbox("Value", nums)
        chart_data = dataframe.copy()
        chart_data[date_column] = pd.to_datetime(chart_data[date_column], errors="coerce")
        chart_data = chart_data.dropna(subset=[date_column])
        fig = px.line(
            chart_data.sort_values(date_column),
            x=date_column,
            y=value_column,
            title=f"{value_column} over {date_column}",
        )
        st.plotly_chart(fig, use_container_width=True)


def render_sql_workspace(db_path: str) -> None:
    st.subheader("SQL Workspace")
    query = st.text_area(
        "Read-only SQL query",
        value="SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name;",
        height=140,
    )

    if st.button("Run Query"):
        normalized = query.strip().lower()
        if not normalized.startswith("select") and not normalized.startswith("with"):
            st.error("Only SELECT/WITH queries are allowed from this tool.")
            return

        try:
            with open_database(db_path) as connection:
                result = pd.read_sql_query(query, connection)
            st.dataframe(result, use_container_width=True)
            st.download_button(
                "Download CSV",
                result.to_csv(index=False).encode("utf-8"),
                file_name="query_results.csv",
                mime="text/csv",
            )
        except Exception as exc:
            st.error(f"Query failed: {exc}")


def main() -> None:
    st.set_page_config(page_title="Perseus Equipment Analytics", layout="wide")
    st.title("Perseus Equipment Analytics")

    dark_mode_default = st.query_params.get("theme") == "dark"
    dark_mode = st.toggle("Dark mode", value=dark_mode_default)
    st.query_params["theme"] = "dark" if dark_mode else "light"
    apply_theme(dark_mode)

    database = DEFAULT_DB_PATH

    if not database.exists():
        st.warning(f"Database not found: {database}")
        st.stop()

    tables = list_tables(str(database))
    if not tables:
        st.warning("No user tables were found in the database.")
        st.stop()

    invoice_tab, customer_tab, ar_tab, rental_tab = st.tabs(
        ["Sales", "Customers", "AR", "Rental"]
    )

    with invoice_tab:
        render_active_invoice_dashboard(str(database))

    with customer_tab:
        render_customers_by_class_dashboard(str(database))

    with ar_tab:
        render_ar_dashboard(str(database))

    with rental_tab:
        render_rental_dashboard(str(database))


if __name__ == "__main__":
    main()
