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

## Global Secondary Index (GSI)

This index is created on the same table to enable efficient querying of the leaderboard by score.

| GSI Name | GSI Partition Key | GSI Sort Key |
| :--- | :--- | :--- |
| `leaderboard-by-xp-gsi` | `LEADERBOARD#{week}` | `xp` (Number) |

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

### User Stats
- `user_address`
- `ip_address`
- `total_swap_count`
- `total_lending_count`
- `total_earn_count`
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