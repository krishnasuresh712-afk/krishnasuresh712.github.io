"""SQL analysis layer. Each function returns plain rows so the dashboard, a notebook or an API can reuse it."""
from __future__ import annotations

import sqlite3

RECALLS_BY_CLASS = """
SELECT classification, COUNT(*) AS recalls,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM recalls WHERE report_date >= :since), 1) AS pct
FROM recalls
WHERE report_date >= :since
GROUP BY classification
ORDER BY classification
"""

MONTHLY_TREND = """
SELECT strftime('%Y-%m', report_date) AS month,
       COUNT(*) AS recalls,
       SUM(classification = 'Class I') AS class_i
FROM recalls
WHERE report_date >= :since
GROUP BY month
ORDER BY month
"""

TOP_FIRMS = """
SELECT recalling_firm,
       COUNT(*) AS recalls,
       SUM(classification = 'Class I') AS class_i,
       MAX(report_date) AS most_recent
FROM recalls
WHERE report_date >= :since
GROUP BY recalling_firm
ORDER BY recalls DESC, class_i DESC
LIMIT :limit
"""

REASON_MIX = """
SELECT reason_category,
       COUNT(*) AS recalls,
       SUM(classification = 'Class I') AS class_i,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM recalls WHERE report_date >= :since), 1) AS pct
FROM recalls
WHERE report_date >= :since
GROUP BY reason_category
ORDER BY recalls DESC
"""

OPEN_CLASS_I = """
SELECT recall_number, report_date, recalling_firm, reason_category,
       substr(product_description, 1, 120) AS product
FROM recalls
WHERE classification = 'Class I' AND status = 'Ongoing' AND report_date >= :since
ORDER BY report_date DESC
"""


def _run(conn: sqlite3.Connection, sql: str, **params) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def recalls_by_class(conn, since="1900-01-01"):
    return _run(conn, RECALLS_BY_CLASS, since=since)


def monthly_trend(conn, since="1900-01-01"):
    return _run(conn, MONTHLY_TREND, since=since)


def top_firms(conn, since="1900-01-01", limit=10):
    return _run(conn, TOP_FIRMS, since=since, limit=limit)


def reason_mix(conn, since="1900-01-01"):
    return _run(conn, REASON_MIX, since=since)


def open_class_i(conn, since="1900-01-01"):
    return _run(conn, OPEN_CLASS_I, since=since)
