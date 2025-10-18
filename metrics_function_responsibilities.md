---

### 📥 `handle_entrance`

This is the simplest event. Its sole responsibility is to track user traffic without being tied to a specific user account.

* **Primary Action**: Increment a counter for general application entrances.
* **Database Operations**:
    1.  Get the current timestamp.
    2.  Calculate the start dates for the current **day**, **week**, and **month**.
    3.  For each period (daily, weekly, monthly), perform an `UpdateItem` operation on the corresponding `periodic_general_stats` item (`PK: STAT#{period_type}#{period_start_date}`, `SK: GENERAL`).
    4.  The update will atomically increment the `dapp_entrances` attribute by 1.

---

### 🔄 `handle_swap`

This handler processes a completed swap transaction. It's responsible for recording the specific event and updating all related aggregate statistics and user-specific data.

* **Primary Action**: Record a user's swap transaction and update all relevant metrics.
* **Database Operations (to be executed in a single transaction)**:
    1.  **Record Individual Swap**: Create a new `swap` item (`PK: USER#{user_address}`, `SK: SWAP#{timestamp}#{tx_hash}`) with all the swap attributes provided in the event.
    2.  **Update User Stats**:
        * Target the `user_stats` item (`PK: USER#{user_address}`, `SK: STATS`).
        * Increment `total_swap_count` by 1.
        * Update `last_active_timestamp` to the current time.
        * *Conditional*: If this is the user's first interaction (i.e., the `user_stats` item doesn't exist yet), also set the `first_active_timestamp`. This "new user" status will be determined before the transaction.
    3.  **Update Periodic General Stats**:
        * For each period (daily, weekly, monthly), update the corresponding `periodic_general_stats` item.
        * Increment `swap_count` by 1.
        * Increment `active_users` by 1.
        * *Conditional*: If the user is new, also increment `new_users` by 1.
    4.  **Update Periodic Swap Stats**:
        * For each period, update the `periodic_swap_stats` item. The `SK` will be `SWAP#{direction}`, where `direction` is `source_chain,destination_chain`.
        * Increment the `count` attribute by 1.
    5.  **Update Leaderboard**:
        * Target the `leaderboard` item for the current week (`PK: LEADERBOARD#{week}`, `SK: USER#{user_address}`).
        * Atomically add **50 points** to the `xp` attribute.
        * Update `xp_timestamp` for user with current timestamp for the current week's entry.

---

### 🏦 `handle_lending`

This handler's logic mirrors the `handle_swap` handler but is tailored for lending activities (deposits, borrows, repays, etc.).

* **Primary Action**: Record a user's lending transaction and update all relevant metrics.
* **Database Operations (to be executed in a single transaction)**:
    1.  **Record Individual Lending Action**: Create a new `lending` item (`PK: USER#{user_address}`, `SK: LEND#{timestamp}#{tx_hash}`) with all lending attributes.
    2.  **Update User Stats**:
        * Target the `user_stats` item.
        * Increment `total_lending_count` by 1.
        * Update `last_active_timestamp`.
        * *Conditional*: Set `first_active_timestamp` if the user is new.
    3.  **Update Periodic General Stats**:
        * For each period, update the general stats item.
        * Increment `lending_count` by 1.
        * Increment `active_users` by 1.
        * *Conditional*: Increment `new_users` by 1 if applicable.
    4.  **Update Periodic Lending Stats**:
        * For each period, update the `periodic_lending_stats` item. The `SK` will be `LENDING#{chain}#{market_name}`.
        * Increment the `count` attribute by 1.
    5.  **Update Leaderboard**:
        * Target the `leaderboard` item for the current week.
        * Atomically add **100 points** to the `xp` attribute.
        * Update `xp_timestamp` for user with current timestamp for the current week's entry.

---

### 🌱 `handle_earn`

This handler follows the same transactional pattern for earn-related activities (e.g., staking, depositing into a vault).

* **Primary Action**: Record a user's "earn" transaction and update all relevant metrics.
* **Database Operations (to be executed in a single transaction)**:
    1.  **Record Individual Earn Action**: Create a new `earn` item (`PK: USER#{user_address}`, `SK: EARN#{timestamp}#{tx_hash}`) with all earn attributes.
    2.  **Update User Stats**:
        * Target the `user_stats` item.
        * Increment `total_earn_count` by 1.
        * Update `last_active_timestamp`.
        * *Conditional*: Set `first_active_timestamp` if the user is new.
    3.  **Update Periodic General Stats**:
        * For each period, update the general stats item.
        * Increment `earn_count` by 1.
        * Increment `active_users` by 1.
        * *Conditional*: Increment `new_users` by 1 if applicable.
    4.  **Update Periodic Earn Stats**:
        * For each period, update the `periodic_earn_stats` item. The `SK` will be `EARN#{chain}#{protocol}`.
        * Increment the `count` attribute by 1.
    5.  **Update Leaderboard**:
        * Target the `leaderboard` item for the current week.
        * Atomically add **100 points** to the `xp` attribute.
        * Update `xp_timestamp` for user with current timestamp.