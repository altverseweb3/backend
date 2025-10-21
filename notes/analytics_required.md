## Captured Analytics

| Metric Category | Metric Name | Description / Calculation (Based on your Schema) | Suggested Chart Type |
| :--- | :--- | :--- | :--- |
| **User & Audience** | Total Users | `COUNT` of all `user_stats` items. | **KPI Scorecard** (Big Number) |
| **User &Audience** | New Users (Time-series) | `COUNT` of `user_stats` items, grouped by `first_active_timestamp` (Daily, Weekly, Monthly). | **Line Chart** or **Bar Chart** |
| **User & Audience** | Active Users (DAU/WAU/MAU) | `COUNT` of unique users with any event (`swap`, `lending`, `earn`, `entrance`) in the period. | **Line Chart** |
| **User & Audience** | User Segmentation | Breakdown of users by `total_swap_count > 0` vs. `total_lending_count > 0` vs. `total_earn_count > 0`. | **Venn Diagram** or **Donut Chart** |
| **Overall Activity** | Total Transactions | `SUM` of all `swap`, `lending`, and `earn` items. | **KPI Scorecard** (Big Number) |
| **Overall Activity** | Transaction Volume (Time-series) | `COUNT` of all transactions (`swap`, `lending`, `earn`) per day/week/month. | **Line Chart** or **Bar Chart** |
| **Overall Activity** | Activity Breakdown | Stacked bar chart (one bar per day/week) showing `swap_count`, `lending_count`, and `earn_count`. | **Stacked Bar Chart** |
| **Overall Activity** | dApp Entrances (Time-series) | `COUNT` of `entrance` events, grouped by day, week, and month. | **Line Chart** or **Bar Chart** |
| **Overall Activity** | Transactions per Active User | `Total Transactions` in period / `Active Users` in period. | **Line Chart** or **KPI Scorecard** |
| **Swap Metrics** | Total Swap Count | `COUNT` of all `swap` items. | **KPI Scorecard** (Big Number) |
| **Swap Metrics** | Swap Pair Breakdown | `COUNT` for each `source_token_symbol` -> `destination_token_symbol` combination. | **Bar Chart** or **Donut Chart** (Top 5 + "Other") |
| **Swap Metrics** | Swap Routes (Chains) Breakdown | `COUNT` for each `source_chain` -> `destination_chain` combination. | **Bar Chart** or **Sankey Diagram** |
| **Swap Metrics** | Cross-Chain vs. Same-Chain | `%` of swaps where `source_chain != destination_chain`. | **Donut Chart** or **100% Stacked Bar** |
| **Lending Metrics** | Lending Action Breakdown | `COUNT` of lending actions, grouped by `action` (`deposit`, `withdraw`, `borrow`, `repay`). | **Donut Chart** or **Bar Chart** |
| **Lending Metrics** | Lending Market Breakdown | `COUNT` of transactions for each `market_name`. | **Bar Chart** or **Donut Chart** (Top 5 + "Other") |
| **Lending Metrics** | Popular Lending Chains | `COUNT` grouped by `chain`. | **Donut Chart** or **Bar Chart** |
| **Lending Metrics** | Lending Assets Breakdown | `COUNT` of transactions for each `token_symbol`. | **Bar Chart** or **Donut Chart** (Top 5 + "Other") |
| **Growth & Retention** | New User Growth Rate | `(New Users this Period / Total Users last Period) * 100%`. | **Line Chart** or **KPI Scorecard** |
| **Growth & Retention** | Retention Cohorts | `%` of new users from "Week 1" who returned in "Week 2", "Week 3", etc. | **Heatmap Table** (Cohort Table) |
| | | | |
| **Leaderboard Displays** | Weekly Leaderboard | A view of the `leaderboard-by-xp-gsi` for the current `week`, sorted by `xp` (DESC). | **Table** |
| **Leaderboard Displays** | Global Leaderboard | A view of the `global-leaderboard-by-xp-gsi`, sorted by `total_xp` (DESC). | **Table** |
| | | | |
| **Low Priority** | Earn Action Breakdown | `COUNT` of earn actions, grouped by `action` (`stake`, `unstake`, `claim`). | **Donut Chart** or **Bar Chart** |
| **Low Priority** | Popular Earn Protocols | `COUNT` grouped by `protocol`. | **Donut Chart** or **Bar Chart** |
| **Low Priority** | Popular Earn Chains | `COUNT` grouped by `chain`. | **Donut Chart** or **Bar Chart** |
| **Low Priority** | Vault Breakdown | `COUNT` of transactions for each `vault_name`. | **Bar Chart** or **Donut Chart** (Top 5 + "Other") |