# Speed up a SQLite report query

## MISSION
The baseline query lives in `baseline.json`:

```sql
SELECT o.customer_id,
       COUNT(*)              AS orders,
       SUM(o.amount_cents)   AS total_cents
FROM   orders o
JOIN   customers c ON c.id = o.customer_id
WHERE  c.country = 'US'
  AND  o.created_at >= '2026-01-01'
GROUP BY o.customer_id
HAVING SUM(o.amount_cents) > 100000
ORDER BY total_cents DESC
LIMIT 20;
```

The schema: `customers(id INTEGER PK, country TEXT, signed_up_at TEXT)` and
`orders(id INTEGER PK, customer_id INTEGER, amount_cents INTEGER,
created_at TEXT)`. There are 2 000 customers (≈40% `US`), 25 000 orders
(≈70% in 2026). The baseline runs in ~6 ms with no indexes.

## PARAMETERS
`train.py` accepts `--sql <rewritten SELECT>` and an optional `--indexes`
argument holding one or more `CREATE INDEX IF NOT EXISTS` statements
separated by semicolons. Every hypothesis MUST include a `"sql"` key.

The hypothesis must produce the SAME 20 rows as the baseline, in the same
order. A mismatch scores `speedup = 0`.

## CONSTRAINTS
- No statements other than `SELECT` and `CREATE INDEX` (no `PRAGMA`,
  `ATTACH`, `UPDATE`, `DELETE`, materialised tables, etc.).
- Indexes count toward the cost — pure `CREATE INDEX` without a matching
  rewrite is fine, but adding many useless indexes is wasteful.
- Primary metric is `speedup`, defined as `baseline_us / query_us`. The
  loop passes at 1.1× and fails below 0.9×.

## HYPOTHESES
- Index `orders(created_at, customer_id)` to cut the date filter.
- Index `customers(country)` so the `country = 'US'` predicate is cheap.
- Rewrite the JOIN as an `IN (SELECT id FROM customers WHERE country='US')`.
- Push the `HAVING` into a subquery so the join runs only on hot customers.

## LEARNINGS
(empty — this is the first run)
