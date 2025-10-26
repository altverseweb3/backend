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
| `transactions-by-time-gsi` | `tx_type` (String) | `timestamp` (String) |

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
- `period_start_date`
- `period_type`
- `swap_count`
- `lending_count`
- `earn_count`
- `dapp_entrances`
- `active_users`
- `new_users`

### Periodic Swap Stats
- `period_start_date`
- `period_type`
- `direction`
- `count`

### Periodic Lending Stats
- `period_start_date`
- `period_type`
- `chain`
- `market_name`
- `count`

### Periodic Earn Stats
- `period_start_date`
- `period_type`
- `chain`
- `protocol`
- `count`

### Leaderboard
- `week`
- `user_address`
- `xp`
- `first_xp_timestamp`