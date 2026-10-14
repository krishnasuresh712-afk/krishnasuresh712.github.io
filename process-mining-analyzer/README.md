# Process Mining Analyzer

Reconstructs how a business process *actually* runs from system event logs, then pinpoints where work waits, where it gets redone, and where the standard path is skipped. It is the analysis a process improvement or operations consulting engagement starts with, written in plain Python and Pandas so every number can be traced.

An optional Claude step turns the computed metrics into a COO-ready executive summary, constrained to use only numbers the analysis produced.

## Questions it answers

| Question | Function |
|---|---|
| How many distinct ways does the process really run? | `variants` |
| How long does order-to-cash take, median and 90th percentile? | `cycle_time_summary` |
| Which handoffs accumulate the most waiting time? | `transitions`, `bottlenecks` |
| Which steps are done more than once per case? | `rework` |
| How often is the standard path followed, and are approvals skipped? | `conformance` |
| Does an extra step (e.g. manual credit review) slow cases down? | `duration_impact` |

## Sample findings (synthetic order-to-cash log, 800 cases)

From [`reports/findings.md`](reports/findings.md):

- The **Ship → Create Invoice** handoff holds about half of all internal waiting time (median ~38 hours), pointing to batched invoicing
- About **22% of cases repeat the credit check**, driven by price changes after the initial check
- About **7% of orders ship without approval**, a controls gap
- Only about **55% of cases follow the standard path** end to end

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_event_log.py           # or drop in a real export (see below)
pytest
python -m src.process_mining.report             # metrics-only report
cp .env.example .env                            # add ANTHROPIC_API_KEY, then:
python -m src.process_mining.report --summarize # adds the executive summary
```

Outputs go to `reports/findings.md` (readable report) and `reports/findings.json` (raw metrics).

## Using a real event log

Any system that timestamps steps can produce one (ERP, CRM, ticketing, Celonis or SAP exports). Provide a CSV with:

`case_id, activity, timestamp` (plus optional `resource`)

Update `REFERENCE_PATH` in `analysis.py` to the process's intended path.

## Design notes

- **Customer payment time is excluded from bottlenecks**: waiting on a customer is not an internal delay a workflow change can fix. Cycle time still includes it.
- **Open cases are excluded from cycle-time statistics** so incomplete cases don't make the process look faster than it is.
- **The LLM never computes.** It receives the metrics JSON and is told not to introduce any other number.

## Next steps

- Process map visualization (directly-follows graph with wait times on the edges)
- Resource-level workload and handoff analysis
- Before/after comparison to measure a pilot's impact
