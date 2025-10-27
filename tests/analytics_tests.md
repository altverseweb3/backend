# AWS Lambda `/analytics` Test Events

These test events are designed to validate the functionality of the `/analytics` endpoint for both `leaderboard` and `user_leaderboard_entry` query types.

-----

### 1\. Fetch Total Users (All-Time)

This event tests the `total_users` query, which hits the `get_total_users` function. It should return a single JSON object with the `total_users` count.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"total_users\"}"
}
```

-----

### 2\. Fetch Daily New & Active Users (DAU)

This event tests the `periodic_user_stats` query for a **daily** period. It hits the `get_periodic_user_stats` function and should return an object containing `new_users` and `active_users` for that specific day.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"daily\", \"period_start_date\": \"2025-10-26\"}"
}
```

and

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"daily\", \"period_start_date\": \"2025-10-27\"}"
}
```

-----

### 3\. Fetch Weekly New & Active Users (WAU)

This event tests the `periodic_user_stats` query for a **weekly** period. It hits the `get_periodic_user_stats` function and should return `new_users` and `active_users` for that specific week.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"weekly\", \"period_start_date\": \"2025-10-20\"}"
}
```

-----

### 4\. Fetch Monthly New & Active Users (MAU)

This event tests the `periodic_user_stats` query for a **monthly** period. It hits the `get_periodic_user_stats` function and should return `new_users` and `active_users` for that specific month.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"monthly\", \"period_start_date\": \"2025-10-01\"}"
}
```

-----

### 5\. Fetch All-Time Activity Stats (KPIs)

This event tests the `total_activity_stats` query, which hits the `get_total_activity_stats` function. It should return a single JSON object with all-time KPI scorecards (e.g., `total_transactions`, `dapp_entrances`, `total_users`).

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"total_activity_stats\"}"
}
```

-----

### 6\. Fetch Periodic Activity Time-series (Daily)

This event tests the `periodic_activity_stats` query for a **daily** time-series. It hits the `get_periodic_activity_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 7 days, containing all metrics needed for the time-series charts (e.g., `total_transactions`, `swap_count`, `active_users`, `transactions_per_active_user`).

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_activity_stats\", \"period_type\": \"daily\", \"limit\": 7}"
}
```

-----

### 7\. Fetch Periodic Activity Time-series (Weekly)

This event tests the `periodic_activity_stats` query for a **weekly** time-series. It hits the `get_periodic_activity_stats` function. It should return an **array** of objects, one for each of the last 8 weeks.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_activity_stats\", \"period_type\": \"weekly\", \"limit\": 8}"
}
```

-----

### 8\. Fetch Periodic Activity Time-series (Monthly)

This event tests the `periodic_activity_stats` query for a **monthly** time-series. It hits the `get_periodic_activity_stats` function. It should return an **array** of objects, one for each of the last 6 months.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_activity_stats\", \"period_type\": \"monthly\", \"limit\": 6}"
}
```

-----

### 9\. Fetch All-Time Swap Stats

This event tests the `total_swap_stats` query, which hits the `get_total_swap_stats` function. It should return an object containing the `total_swap_count`, a `swap_routes` breakdown, and the `cross_chain_count` vs. `same_chain_count`.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"total_swap_stats\"}"
}
```

-----

### 10\. Fetch Periodic Swap Stats (Daily)

This event tests the `periodic_swap_stats` query for a **daily** period. It hits the `get_periodic_swap_stats` function and should return the `swap_routes` breakdown and cross-chain vs. same-chain counts for that specific day.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_swap_stats\", \"period_type\": \"daily\", \"start_date\": \"2025-10-26\"}"
}
```

-----

### 11\. Fetch Periodic Swap Stats (Weekly)

This event tests the `periodic_swap_stats` query for a **weekly** period.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_swap_stats\", \"period_type\": \"weekly\", \"start_date\": \"2025-10-20\"}"
}
```

-----

### 12\. Fetch Periodic Swap Stats (Monthly)

This event tests the `periodic_swap_stats` query for a **monthly** period.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_swap_stats\", \"period_type\": \"monthly\", \"start_date\": \"2025-10-01\"}"
}
```

-----

### 13\. Fetch Global Leaderboard (Limit 50)

This event tests the standard request for the global leaderboard, fetching the top 50 users.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"leaderboard\", \"scope\": \"global\", \"limit\": 50}"
}
```

-----

### 14\. Fetch Weekly Leaderboard (Limit 50)

This event tests the standard request for the weekly leaderboard, fetching the top 50 users for the current week.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"leaderboard\", \"scope\": \"weekly\", \"limit\": 50}"
}
```

-----

### 15\. Fetch Specific User's Leaderboard Entry

This event tests the `user_leaderboard_entry` query. It should return a single JSON object containing the specified user's `global_total_xp` and `weekly_xp`.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"user_leaderboard_entry\", \"user_address\": \"0xf5d8777EA028Ad29515aA81E38e9B85afb7d6303\"}"
}
```