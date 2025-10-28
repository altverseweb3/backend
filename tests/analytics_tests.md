# AWS Lambda `/analytics` Test Events

These test events are designed to validate the functionality of the `/analytics` endpoint for both `leaderboard` and `user_leaderboard_entry` query types.

All protected test events **must** include a `headers` object with a valid API key to pass. Public tests do not require this header.

**Example `headers` block to add:**

```json
  "headers": {
    "x-api-key": "API_KEY_GOES_HERE"
  },
```

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

### 2\. Fetch Periodic User Stats Time-series (Daily)

This event tests the `periodic_user_stats` query for a **daily** time-series. It hits the `get_periodic_user_stats` function and should return an **array** of objects, one for each of the last 7 days, containing `new_users` and `active_users`.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"daily\", \"limit\": 7}"
}
```

-----

### 3\. Fetch Periodic User Stats Time-series (Weekly)

This event tests the `periodic_user_stats` query for a **weekly** time-series. It hits the `get_periodic_user_stats` function and should return an **array** of objects for the last 8 weeks.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"weekly\", \"limit\": 8}"
}
```

-----

### 4\. Fetch Periodic User Stats Time-series (Monthly)

This event tests the `periodic_user_stats` query for a **monthly** time-series. It hits the `get_periodic_user_stats` function and should return an **array** of objects for the last 6 months.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_user_stats\", \"period_type\": \"monthly\", \"limit\": 6}"
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

### 10\. Fetch Periodic Swap Stats Time-series (Daily)

This event tests the `periodic_swap_stats` query for a **daily** time-series. It should return an **array** of objects, one for each of the last 7 days.


```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_swap_stats\", \"period_type\": \"daily\", \"limit\": 7}"
}
```

-----

### 11\. Fetch Periodic Swap Stats Time-series (Weekly)

This event tests the `periodic_swap_stats` query for a **weekly** time-series. It should return an **array** of objects, one for each of the last 8 weeks.


```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_swap_stats\", \"period_type\": \"weekly\", \"limit\": 8}"
}
```

-----

### 12\. Fetch Periodic Swap Stats Time-series (Monthly)

This event tests the `periodic_swap_stats` query for a **monthly** time-series. It should return an **array** of objects, one for each of the last 6 months.


```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_swap_stats\", \"period_type\": \"monthly\", \"limit\": 6}"
}
```

-----

### 13\. Fetch All-Time Lending Stats (KPIs)

This event tests the `total_lending_stats` query, which hits the `get_total_lending_stats` function. It should return an object containing the `total_lending_count` (for the KPI card) and an all-time `breakdown` array (for the donut chart).

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"total_lending_stats\"}"
}
```

-----

### 14\. Fetch Periodic Lending Stats (Daily)

This event tests the `periodic_lending_stats` query for a **daily** time-series. It hits the `get_periodic_lending_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 7 days, containing the `period_start`, `total_lending_count`, and `breakdown` for each day.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_lending_stats\", \"period_type\": \"daily\", \"limit\": 7}"
}
```

-----

### 15\. Fetch Periodic Lending Stats (Weekly)

This event tests the `periodic_lending_stats` query for a **weekly** time-series. It hits the `get_periodic_lending_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 8 weeks.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_lending_stats\", \"period_type\": \"weekly\", \"limit\": 8}"
}
```

-----

### 16\. Fetch Periodic Lending Stats (Monthly)

This event tests the `periodic_lending_stats` query for a **monthly** time-series. It hits the `get_periodic_lending_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 6 months.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_lending_stats\", \"period_type\": \"monthly\", \"limit\": 6}"
}
```

-----

### 17\. Fetch All-Time Earn Stats (KPIs)

This event tests the `total_earn_stats` query, which hits the `get_total_earn_stats` function. Based on your `earn.py` code, this should return an object containing the `total_earn_count`. 

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"total_earn_stats\"}"
}
```

-----

### 18\. Fetch Periodic Earn Stats (Daily)

This event tests the `periodic_earn_stats` query for a **daily** time-series. It hits the `get_periodic_earn_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 7 days, containing the `period_start`, `total_earn_count`, and breakdowns (`by_chain`, `by_protocol`, etc.) for each day.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_earn_stats\", \"period_type\": \"daily\", \"limit\": 7}"
}
```

-----

### 19\. Fetch Periodic Earn Stats (Weekly)

This event tests the `periodic_earn_stats` query for a **weekly** time-series. It hits the `get_periodic_earn_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 8 weeks.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_earn_stats\", \"period_type\": \"weekly\", \"limit\": 8}"
}
```

-----

### 20\. Fetch Periodic Earn Stats (Monthly)

This event tests the `periodic_earn_stats` query for a **monthly** time-series. It hits the `get_periodic_earn_stats` function with a `limit`. It should return an **array** of objects, one for each of the last 6 months.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"periodic_earn_stats\", \"period_type\": \"monthly\", \"limit\": 6}"
}
```

-----

### 21\. Fetch Global Leaderboard (Limit 50)

This event tests the standard request for the global leaderboard, fetching the top 50 users.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"leaderboard\", \"scope\": \"global\", \"limit\": 50}"
}
```

-----

### 22\. Fetch Weekly Leaderboard (Limit 50)

This event tests the standard request for the weekly leaderboard, fetching the top 50 users for the current week.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"leaderboard\", \"scope\": \"weekly\", \"limit\": 50}"
}
```

-----

### 23\. Fetch Specific User's Leaderboard Entry

This event tests the `user_leaderboard_entry` query. It should return a single JSON object containing the specified user's `global_total_xp` and `weekly_xp`.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"user_leaderboard_entry\", \"user_address\": \"0xf5d8777EA028Ad29515aA81E38e9B85afb7d6303\"}"
}
```