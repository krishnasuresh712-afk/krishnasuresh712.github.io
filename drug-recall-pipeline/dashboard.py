"""Streamlit dashboard over the recalls database.

Run: streamlit run dashboard.py   (after running the ingest)
"""
from datetime import date

import pandas as pd
import streamlit as st

from src.recall_pipeline import queries
from src.recall_pipeline.ingest import DEFAULT_DB, connect

st.set_page_config(page_title="Drug Recall Monitor", layout="wide")
st.title("FDA Drug Recall Monitor")
st.caption("Source: openFDA drug enforcement reports")

conn = connect(DEFAULT_DB)
since = st.sidebar.date_input("Reported since", date(date.today().year - 1, 1, 1)).isoformat()

by_class = pd.DataFrame(queries.recalls_by_class(conn, since))
if by_class.empty:
    st.warning("No data yet. Run `python -m src.recall_pipeline.ingest` first.")
    st.stop()

total = int(by_class["recalls"].sum())
class_i = int(by_class.loc[by_class["classification"] == "Class I", "recalls"].sum())
open_i = pd.DataFrame(queries.open_class_i(conn, since))

c1, c2, c3 = st.columns(3)
c1.metric("Recalls", f"{total:,}")
c2.metric("Class I (most serious)", f"{class_i:,}", f"{100 * class_i / total:.1f}% of total", delta_color="off")
c3.metric("Class I still ongoing", f"{len(open_i):,}")

left, right = st.columns(2)
with left:
    st.subheader("Monthly recalls")
    st.bar_chart(pd.DataFrame(queries.monthly_trend(conn, since)), x="month", y=["recalls", "class_i"])
with right:
    st.subheader("Why products are recalled")
    st.dataframe(pd.DataFrame(queries.reason_mix(conn, since)), hide_index=True, use_container_width=True)

st.subheader("Firms with the most recalls")
st.dataframe(pd.DataFrame(queries.top_firms(conn, since)), hide_index=True, use_container_width=True)

st.subheader("Ongoing Class I recalls")
st.dataframe(open_i, hide_index=True, use_container_width=True)
