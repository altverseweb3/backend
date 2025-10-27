## Primary Table Schema

| Data Model | `PK` (Partition Key) | `SK` (Sort Key) |
| :--- | :--- | :--- |
| **`user_stats`** | `USER#{user_address}` | `STATS` |
| **`swap`** | `USER#{user_address}` | `SWAP#{timestamp}#{tx_hash}` |
| **`lending`** | `USER#{user_address}` | `LEND#{timestamp}#{tx_hash}` |
| **`earn`** | `USER#{user_address}` | `EARN#{timestamp}#{tx_hash}` |
| **`periodic_general_stats`** | `STAT#{period_type}#{period_start_date}`| `GENERAL` |
| **`periodic_swap_stats`** | `STAT#{period_type}#{period_start_date}`| `SWAP#{direction}` |
| **`periodic_lending_stats`**| `STAT#{period_type}#{period_start_date}`| `LENDING#{chain}#{market_name}` |
| **`periodic_earn_stats`** | `STAT#{period_type}#{period_start_date}`| `EARN#{chain}#{protocol}` |
| **`leaderboard`** | `LEADERBOARD#{week}` | `USER#{user_address}` |

---

## Global Secondary Indexes (GSIs)

To support efficient, sorted queries for weekly/global leaderboards and offline analytics.

### Weekly Leaderboard GSI

This index allows for fetching a specific week's leaderboard, sorted by `xp` in descending order.

| GSI Name | GSI Partition Key | GSI Sort Key |
| :--- | :--- | :--- |
| `leaderboard-by-xp-gsi` | `LEADERBOARD#{week}` | `xp` (Number) |

---

### Global Leaderboard GSI

This index enables a global, all-time leaderboard by querying across all users. It indexes the `user_stats` items.

| GSI Name | GSI Partition Key | GSI Sort Key |
| :--- | :--- | :--- |
| `global-leaderboard-by-xp-gsi` | `leaderboard_scope` (String) | `total_xp` (Number) |

---

### Transaction Time-Series GSI

This index enables efficient queries for offline analytics jobs (e.g., "fetch all lending transactions from the last 24 hours"). It indexes *only* the `swap`, `lending`, and `earn` items.

| GSI Name | GSI Partition Key | GSI Sort Key |
| :--- | :--- | :--- |
| `transactions-by-time-gsi` | `tx_type` (String) | `timestamp` (Number) |

---

## Data Attributes to Capture

This section outlines the specific attributes intended for capture within each data model.

### Swap
- `user_address`
- `tx_hash`
- `protocol`
- `swap_provider`
- `source_chain`
- `source_token_address`
- `source_token_symbol`
- `amount_in`
- `destination_chain`
- `destination_token_address`
- `destination_token_symbol`
- `amount_out`
- `timestamp`
- `tx_type` 

### Lending
- `user_address`
- `tx_hash`
- `protocol`
- `action`
- `chain`
- `market_name`
- `token_address`
- `token_symbol`
- `amount`
- `timestamp`
- `tx_type`

### Earn
- `user_address`
- `tx_hash`
- `protocol`
- `action`
- `chain`
- `vault_name`
- `vault_address`
- `token_address`
- `token_symbol`
- `amount`
- `timestamp`
- `tx_type`

### User Stats
- `user_address`
- `ip_address`
- `total_swap_count`
- `total_lending_count`
- `total_earn_count`
- `total_xp`
- `first_active_timestamp`
- `last_active_timestamp`

### Periodic General Stats
This item captures both periodic (daily, weekly, monthly) and global (all-time) metrics. The context is determined by the `PK` (`STAT#{period_type}#{period_start_date}`).

- `period_start_date`: (e.g., `2023-10-27`, `2023-W43`, or `ALL`)
- `period_type`: (e.g., `daily`, `weekly`, `monthly`, `all`)
- `swap_count`: The count of swaps. (For `period_type=all`, this is the all-time total).
- `lending_count`: The count of lending actions. (For `period_type=all`, this is the all-time total).
- `earn_count`: The count of earn actions. (For `period_type=all`, this is the all-time total).
- `dapp_entrances`: The count of entrances. (For `period_type=all`, this is the all-time total).
- `active_users`: The count of unique active users for the period. (Not applicable for `period_type=all`).
- `new_users`: The count of new users for the period. (For `period_type=all`, this represents the all-time total unique users).

### Periodic Swap Stats
- `period_start_date`: (e.g., `2023-10-27`, `2023-W43`, or `ALL`)
- `period_type`: (e.g., `daily`, `weekly`, `monthly`, `all`)
- `direction`: A string representing the source and destination chains (e.g., `ETH,ARB` or `BSC,BSC`).
- `count`: The total count of swaps for this direction and period.

### Periodic Lending Stats
- `period_start_date`: (e.g., `2023-10-27`, `2023-W43`, or `ALL`)
- `period_type`: (e.g., `daily`, `weekly`, `monthly`, `all`)
- `chain`
- `market_name`
- `count`: The total count of lending actions for this market and period.

### Periodic Earn Stats
- `period_start_date`: (e.g., `2023-10-27`, `2023-W43`, or `ALL`)
- `period_type`: (e.g., `daily`, `weekly`, `monthly`, `all`)
- `chain`
- `protocol`
- `count`: The total count of earn actions for this protocol and period.

### Leaderboard
- `week`: (e.g., `2023-W43`)
- `user_address`
- `xp`
- `first_xp_timestamp`