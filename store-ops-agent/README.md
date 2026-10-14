# Store Ops Agent

An AI operations analyst for a small e-commerce business. It answers questions like *"What should I reorder this week?"* or *"Which products drive my margin?"* using Claude tool calling over deterministic Python analytics, and shows the results in a Streamlit dashboard.

**Design principle:** the model never does math. Every number comes from a tested Pandas function; Claude decides which function to call and explains the result. That keeps answers auditable, which matters when an operator acts on them.

## What it does

| Capability | How |
|---|---|
| Revenue, COGS, gross margin, AOV | `analytics.revenue_summary` |
| Product-level performance and revenue share | `analytics.product_performance` |
| Weekly revenue trend with week-over-week change | `analytics.weekly_trend` |
| Reorder points, days of cover, suggested order quantities | `analytics.reorder_plan` |
| Natural-language Q&A over all of the above | `agent.run_agent` (Claude tool use loop) |

### Reorder logic

```
avg daily demand   = units sold in lookback window / lookback days
reorder point      = avg daily demand x (supplier lead time + safety stock days)
needs reorder      = on hand <= reorder point
suggested quantity = avg daily demand x (lead time + safety stock + cover days) - on hand
```

## Architecture

```
orders.csv, products.csv
        |
  analytics.py  (pure, tested Pandas functions)
        |
  agent.py  -- Claude picks a tool --> dispatch() --> JSON result --> Claude explains
        |
  app.py  (Streamlit: KPIs, reorder alerts, trends, chat)
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add your ANTHROPIC_API_KEY
python scripts/generate_sample_data.py   # or drop in your own CSVs (see below)
pytest
streamlit run app.py
```

Or with Docker:

```bash
docker build -t store-ops-agent .
docker run -p 8501:8501 --env-file .env store-ops-agent
```

## Using real store data

Replace the files in `data/` with an export from your store (same columns):

- `orders.csv`: `order_id, order_date, sku, quantity, unit_price, unit_cost`
- `products.csv`: `sku, name, on_hand, lead_time_days, safety_stock_days`

The sample data is synthetic and anonymized; it is only there so the project runs out of the box.

## Tests

`tests/test_store_ops.py` checks the analytics math against hand-computed values and runs the agent loop against a fake Claude client, so the tool-calling flow is tested without an API key.

## Next steps

- Deploy to Streamlit Community Cloud and record a 60-second demo
- Add a "why" trace in the UI showing which tool produced each number
- Email or Slack a weekly reorder digest
