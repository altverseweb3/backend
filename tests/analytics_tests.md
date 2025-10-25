# AWS Lambda `/analytics` Test Events

These test events are designed to validate the functionality of the `/analytics` endpoint for both `leaderboard` and `user_leaderboard_entry` query types.

### 1\. Fetch Global Leaderboard (Limit 50)

This event tests the standard request for the global leaderboard, fetching the top 50 users.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"leaderboard\", \"scope\": \"global\", \"limit\": 50}"
}
```

-----

### 2\. Fetch Weekly Leaderboard (Limit 50)

This event tests the standard request for the weekly leaderboard, fetching the top 50 users for the current week.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"leaderboard\", \"scope\": \"weekly\", \"limit\": 50}"
}
```

-----

### 3\. Fetch Specific User's Leaderboard Entry

This event tests the `user_leaderboard_entry` query. It should return a single JSON object containing the specified user's `global_total_xp` and `weekly_xp`.

```json
{
  "path": "/analytics",
  "httpMethod": "POST",
  "body": "{\"queryType\": \"user_leaderboard_entry\", \"user_address\": \"0xf5d8777EA028Ad29515aA81E38e9B85afb7d6303\"}"
}
```