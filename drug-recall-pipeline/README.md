# Drug Recall Pipeline

An end-to-end data pipeline that pulls FDA drug recall reports from the public **openFDA REST API**, loads them into a SQL database, and serves a monitoring dashboard: the kind of integration a pharma quality, supply chain, or procurement team would actually use to watch supplier risk.

## What it does

- **Extract:** pages through the openFDA drug enforcement endpoint (handles pagination, rate limiting, and the API's "no results" 404)
- **Transform:** normalizes dates and fields and classifies each free-text recall reason into a category (sterility, impurities, contamination, potency, labeling, cGMP)
- **Load:** idempotent upsert into SQLite, so re-runs update recall status instead of duplicating rows; every run is logged in an `ingest_runs` audit table
- **Analyze:** SQL queries for recalls by class, monthly trend, firms with the most recalls, reason mix, and ongoing Class I (most serious) recalls
- **Serve:** a Streamlit dashboard, with Docker Compose to run the ingest and dashboard together

## Architecture

```
openFDA API --> ingest.py (extract, normalize, categorize) --> SQLite (recalls, ingest_runs)
                                                                    |
                                                    queries.py (SQL analysis layer)
                                                                    |
                                                         dashboard.py (Streamlit)
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
python -m src.recall_pipeline.ingest --since 2024-01-01     # first load
python -m src.recall_pipeline.ingest --incremental          # later runs: only new reports
streamlit run dashboard.py
```

With Docker:

```bash
docker compose up --build      # runs the ingest, then serves the dashboard on :8501
```

No API key is needed; openFDA allows unauthenticated requests at a lower rate limit. For heavier use, request a free key and append `&api_key=...` to the request URL.

## Tests

`tests/test_pipeline.py` covers reason categorization, date normalization, idempotent loading with status updates, every SQL query, and pagination (with a fake HTTP session, so tests run offline).

## Questions this answers

- How many Class I recalls are still open right now?
- Which manufacturers recall most often, and for what reasons?
- Are sterility or impurity recalls trending up?

## Next steps

- Schedule the incremental load daily (cron or GitHub Actions)
- Alert by email or Slack when a watched supplier gets a Class I recall
- Swap SQLite for Postgres for multi-user access
