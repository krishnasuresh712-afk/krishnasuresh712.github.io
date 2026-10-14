# Order-to-Cash Process Findings

_Generated 2026-10-13 from 800 cases._

## Headline metrics

- Median order-to-cash cycle: **27.0 days** (90th percentile 52.9 days, 742 completed cases, 58 still open)
- Cases following the standard path end to end: **55.4%**
- Orders shipped without approval: **58 (7.2%)**
- Manual credit review: 132 completed cases, median cycle 28.3 days vs 26.8 days without

## Where work waits (internal handoffs)

| source | target | count | median_wait_hours | total_wait_hours | share_of_internal_wait_pct |
|---|---|---|---|---|---|
| Ship | Create Invoice | 800 | 38.5 | 38102.0 | 49.6 |
| Approve Order | Pick | 742 | 11.3 | 10361.0 | 13.5 |
| Pack | Ship | 800 | 7.9 | 7651.0 | 10.0 |
| Credit Check | Manual Credit Review | 145 | 27.8 | 4727.0 | 6.1 |
| Credit Check | Approve Order | 636 | 6.0 | 4564.0 | 5.9 |

## Rework

| activity | cases_with_rework | extra_executions | rework_rate_pct |
|---|---|---|---|
| Credit Check | 174 | 209 | 21.8 |
| Change Price | 35 | 35 | 4.4 |

## Most common process variants

| variant | cases | share_pct | cumulative_pct |
|---|---|---|---|
| Create Order > Credit Check > Approve Order > Pick > Pack > Ship > Create Invoice > Receive Payment | 443 | 55.4 | 55.4 |
| Create Order > Credit Check > Change Price > Credit Check > Approve Order > Pick > Pack > Ship > Create Invoice > Receive Payment | 99 | 12.4 | 67.8 |
| Create Order > Credit Check > Manual Credit Review > Approve Order > Pick > Pack > Ship > Create Invoice > Receive Payment | 95 | 11.9 | 79.7 |
| Create Order > Credit Check > Pick > Pack > Ship > Create Invoice > Receive Payment | 37 | 4.6 | 84.3 |
| Create Order > Credit Check > Approve Order > Pick > Pack > Ship > Create Invoice | 31 | 3.9 | 88.2 |
