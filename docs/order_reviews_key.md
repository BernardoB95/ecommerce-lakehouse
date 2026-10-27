# Decision: primary key for `app.order_reviews`

## Context

`review_id` in `olist_order_reviews_dataset.csv` is not unique, so it cannot be the primary key on its own.

## What the data shows

Profiled from the 99,224 rows in `data/olist/olist_order_reviews_dataset.csv`:

| Measure | Value |
|---|---|
| Rows | 99,224 |
| Distinct `review_id` | 98,410 |
| `review_id` values that repeat | 789 (764 appear twice, 25 appear three times) |
| Rows belonging to a repeated `review_id` | 1,603 |
| Duplicate `(review_id, order_id)` pairs | 0 |
| Orders with more than one review | 547 |
| Review `order_id`s missing from `orders` | 0 |

Within every one of the 789 repeated groups, `review_score`, `review_comment_title`, `review_comment_message`, `review_creation_date` and `review_answer_timestamp` are identical. **Only `order_id` differs.**

## Why it happens

These are not duplicate rows or load errors. One review was submitted once and is attached to several different orders. This is consistent with a customer placing multiple orders around the same time and answering a single survey that covers all of them. The source system then repeats the same review for each order. (This explanation is inferred from the pattern, not documented by Olist.)

So `review_id` identifies a *submitted review*, and the table is really one row per review-and-order link.

## Options considered

1. **`PRIMARY KEY (review_id)`**: rejected. It fails on load for the 789 repeated ids.
2. **Deduplicate on `review_id`, keeping one row**: rejected. It silently drops the link to the other orders, so those orders would show no review and review analysis per order would be wrong.
3. **Surrogate key (`BIGSERIAL`)**: rejected. It adds an id with no business meaning and does not stop genuine duplicates from loading.
4. **Composite `PRIMARY KEY (review_id, order_id)`**: chosen.

## Decision

Use a composite primary key on `(review_id, order_id)`.

- The pair is unique in the data (0 duplicates), so every source row loads and none are dropped.
- It matches the grain: one row per review per order.
- It keeps the full review-to-order relationship for joins from `orders`.

```sql
PRIMARY KEY (review_id, order_id)
```

A separate index on `order_id` is also created. The primary key index starts with `review_id`, so it does not help lookups that filter only by `order_id`, which is the common join from `orders`.

## Consequences

- Do not treat `review_id` as unique anywhere downstream. Counting `DISTINCT review_id` gives the number of submitted reviews (98,410), while `COUNT(*)` gives review-order links (99,224).
- Average review score per order and per product should join on `order_id`. Average score across all reviews should decide explicitly whether a repeated review counts once or once per order, because counting per row weights multi-order reviews more heavily.
- In the silver layer, keep `(review_id, order_id)` as the unique key. Create a distinct-review view only if a metric needs one.
- 547 orders have more than one review. If a metric needs one score per order, define the rule (latest `review_answer_timestamp`, for example) when building it.
