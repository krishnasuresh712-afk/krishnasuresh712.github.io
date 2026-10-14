"""Streamlit front end: KPIs, reorder alerts, weekly trend, and an ask-the-agent box.

Run: streamlit run app.py
"""
import streamlit as st

from src.store_ops import analytics
from src.store_ops.agent import run_agent

st.set_page_config(page_title="Store Ops Agent", layout="wide")


@st.cache_data
def load():
    return analytics.load_data()


orders, products = load()
summary = analytics.revenue_summary(orders)

st.title("Store Ops Agent")
st.caption(f"{summary['period_start']} to {summary['period_end']}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders", f"{summary['orders']:,}")
c2.metric("Revenue", f"${summary['revenue']:,.0f}")
c3.metric("Gross margin", f"{summary['gross_margin_pct']}%")
c4.metric("Avg order value", f"${summary['avg_order_value']:.2f}")

plan = analytics.reorder_plan(orders, products)
alerts = plan[plan["needs_reorder"]]
st.subheader(f"Reorder alerts ({len(alerts)})")
st.dataframe(
    alerts[["sku", "name", "on_hand", "reorder_point", "days_of_cover", "suggested_order_qty"]],
    hide_index=True,
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    st.subheader("Weekly revenue")
    st.line_chart(analytics.weekly_trend(orders), x="week_start", y="revenue")
with right:
    st.subheader("Product performance")
    st.dataframe(analytics.product_performance(orders, products), hide_index=True, use_container_width=True)

st.subheader("Ask the agent")
question = st.chat_input("e.g. Which products should I reorder this week, and how many?")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Running analysis..."):
            result = run_agent(question, orders, products)
        st.write(result.answer)
        with st.expander("Tools used"):
            st.json(result.tool_calls)
