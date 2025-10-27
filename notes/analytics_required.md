### Captured Analytics (Real-time)

This list includes metrics that can be pulled **instantly** from aggregated `STAT` items, making them suitable for a fast-loading public dashboard. The 'Description' column details the efficient query pattern.

| Metric Category | Metric Name | Description / Calculation (Based on Schema) | Chart Type | Status |
| :--- | :--- | :--- | :--- | :--- |
| **User & Audience** | **Total Users** | `Get` `STAT#all#ALL` item. <br> Read the **`new_users`** attribute. | KPI Scorecard | ✅ |
| **User & Audience** | New Users (Time-series) | `Get` `STAT#{period}#GENERAL` item. <br> Read the **`new_users`** attribute. | Line/Bar Chart | ✅ |
| **User & Audience** | Active Users (DAU/WAU/MAU) | `Get` `STAT#{period}#GENERAL` item. <br> Read the **`active_users`** attribute. | Line Chart | ✅ |
| **Overall Activity** | **Total Transactions** | `Get` `STAT#all#ALL` item. <br> Calculate **`swap_count + lending_count + earn_count`**. | KPI Scorecard | ✅ |
| **Overall Activity** | Transaction Volume (Time-series) | `Get` `STAT#{period}#GENERAL` item. <br> Calculate **`swap_count + lending_count + earn_count`**. | Line/Bar Chart | ✅ |
| **Overall Activity** | Activity Breakdown (Time-series) | `Get` `STAT#{period}#GENERAL` item. <br> Read **`swap_count`**, **`lending_count`**, and **`earn_count`** attributes. | Stacked Bar Chart | ✅ |
| **Overall Activity** | dApp Entrances (Time-series) | `Get` `STAT#{period}#GENERAL` item. <br> Read the **`dapp_entrances`** attribute. | Line/Bar Chart | ✅ |
| **Overall Activity** | Transactions per Active User | `Get` `STAT#{period}#GENERAL` item. <br> Calculate **`(swap_count + lending_count + earn_count) / active_users`**. | Line Chart / KPI | ✅ |
| **Swap Metrics** | **Total Swap Count** | `Get` `STAT#all#ALL` item. <br> Read the **`swap_count`** attribute. | KPI Scorecard | ✅ |
| **Swap Metrics** | Swap Routes (Chains) Breakdown | `Query` `PK = STAT#{period}` and `SK starts_with "SWAP#"`. <br> Aggregate results from all `periodic_swap_stats` items. | Sankey Diagram / Bar Chart | ✅ |
| **Swap Metrics** | Cross-Chain vs. Same-Chain | `Query` `PK = STAT#{period}` and `SK starts_with "SWAP#"`. <br> Backend logic parses the `SK` (`SWAP#{source}#{dest}`) to sum `count` for `source != dest` vs. `source == dest`. | Donut Chart | ✅ |
| **Lending Metrics** | **Total Lending Count** | `Get` `STAT#all#ALL` item. <br> Read the **`lending_count`** attribute. | KPI Scorecard | ❌ |
| **Lending Metrics** | Lending Market/Chain Breakdown | `Query` `PK = STAT#{period}` and `SK starts_with "LENDING#"`. <br> Backend logic parses the `SK` (`LENDING#{chain}#{market}`) to aggregate `count` by chain or market. | Bar Chart / Donut Chart | ❌ |
| **Earn Metrics** | **Total Earn Count** | `Get` `STAT#all#ALL` item. <br> Read the **`earn_count`** attribute. | KPI Scorecard | ❌ |
| **Earn Metrics** | Earn Protocol/Chain Breakdown | `Query` `PK = STAT#{period}` and `SK starts_with "EARN#"`. <br> Backend logic parses the `SK` (`EARN#{chain}#{protocol}`) to aggregate `count` by chain or protocol. | Bar Chart / Donut Chart | ❌ |
| **Leaderboard** | Weekly Leaderboard | `Query` the **`leaderboard-by-xp-gsi`** with `PK = LEADERBOARD#{current_week}`. | Table | ✅ |
| **Leaderboard** | Global Leaderboard | `Query` the **`global-leaderboard-by-xp-gsi`** with `PK = "GLOBAL"`. | Table | ✅ |

-----

### Expensive / Offline Analytics

This list includes metrics that **cannot** be answered by the real-time `STAT` items. They require full scans, GSI queries, or post-processing (e.g., with AWS Glue, Athena, or a batch Lambda) on the raw transaction data.

| Metric Category | Metric Name | Reason for Offline Calculation | Status |
| :--- | :--- | :--- | :--- |
| **User & Audience** | New User Growth Rate | Depends on "Total Users" (real-time) and periodic `new_users`, but calculation is typically done offline. | ❌ |
| **User & Audience** | Retention Cohorts | Requires finding users by `first_active_timestamp` and then checking their activity in subsequent periods. | ❌ |
| **Swap Metrics** | Swap Pair Breakdown (Tokens) | The `periodic_swap_stats` item is keyed by *chain*, not by `source_token_symbol` or `destination_token_symbol`. This requires querying the raw `swap` items. | ❌ |
| **Lending Metrics** | Lending Action Breakdown | The `periodic_lending_stats` item is keyed by `chain` and `market_name`, not by `action` (deposit, borrow, etc.). This requires querying the raw `lending` items. | ❌ |
| **Lending Metrics** | Lending Assets Breakdown | The `periodic_lending_stats` item does not include `token_symbol`. This requires querying the raw `lending` items. | ❌ |
| **Earn Metrics** | Earn Action Breakdown | The `periodic_earn_stats` item is keyed by `chain` and `protocol`, not by `action` (stake, unstake, etc.). This requires querying the raw `earn` items. | ❌ |
| **Earn Metrics** | Vault Breakdown | The `periodic_earn_stats` item does not include `vault_name`. This requires querying the raw `earn` items. | ❌ |