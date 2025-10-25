# AWS Lambda `/metrics` Test Events

These test events are designed to validate the functionality of the `/metrics` endpoint for all supported event types (`entrance`, `swap`, `lending`, `earn`) and to check its error handling capabilities.

### 1\. DApp Entrance Event

This event tests the simplest case: tracking a general visit to the application. It should increment the `dapp_entrances` counter in the `periodic_general_stats` items.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"eventType\": \"entrance\"}"
}
```

-----

### 2\. Swap Transaction Event

This tests the full transactional update for a swap. It records the individual swap and updates user stats, periodic general stats, periodic swap stats, and the leaderboard.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"eventType\": \"swap\", \"payload\": {\"user_address\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\", \"tx_hash\": \"0x123abc456def7890123abc456def7890123abc456def7890123abc456def7890\", \"protocol\": \"uniswap_v3\", \"swap_provider\": \"altverse_aggregator\", \"source_chain\": \"ethereum\", \"source_token_address\": \"0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2\", \"source_token_symbol\": \"WETH\", \"amount_in\": \"1000000000000000000\", \"destination_chain\": \"polygon\", \"destination_token_address\": \"0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270\", \"destination_token_symbol\": \"WMATIC\", \"amount_out\": \"1500000000000000000000\", \"timestamp\": 1760972488}}"
}
```

-----

### 3\. Lending Transaction Event

This tests the transactional update for a lending action (e.g., a deposit). It updates all relevant stats and adds 100 XP to the user's leaderboard score.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"eventType\": \"lending\", \"payload\": {\"user_address\": \"0x742d35Cc6634C0532925a3b844Bc454e4438f44e\", \"tx_hash\": \"0x456def7890123abc456def7890123abc456def7890123abc456def7890123abc\", \"protocol\": \"aave_v3\", \"action\": \"deposit\", \"chain\": \"arbitrum\", \"market_name\": \"USDC.e\", \"token_address\": \"0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8\", \"token_symbol\": \"USDC.e\", \"amount\": \"500000000\", \"timestamp\": 1729171600}}"
}
```

-----

### 4\. Earn Transaction Event

This tests the transactional update for an "earn" action, such as staking in a vault. It updates all relevant stats and also adds 100 XP to the user's leaderboard score.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"eventType\": \"earn\", \"payload\": {\"user_address\": \"0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1\", \"tx_hash\": \"0x7890123abc456def7890123abc456def7890123abc456def7890123abc456def\", \"protocol\": \"yearn_finance\", \"action\": \"stake\", \"chain\": \"ethereum\", \"vault_name\": \"yvWETH\", \"vault_address\": \"0xa258C4606Ca8206D8aA700cE2143D748Ab3b728F\", \"token_address\": \"0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2\", \"token_symbol\": \"WETH\", \"amount\": \"500000000000000000\", \"timestamp\": 1729171720}}"
}
```

-----

## Error Handling Tests

These events can be used to verify that the function correctly handles invalid or incomplete requests.

### 5\. Error Handling: Missing `eventType`

This request is missing the required `eventType` field in the body. The function should return a `400 Bad Request` error.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"payload\": {\"user_address\": \"0x123...\"}}"
}
```

-----

### 6\. Error Handling: Unknown `eventType`

This request uses an `eventType` that is not supported. The function should return a `400 Bad Request` error.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"eventType\": \"unknown_action\", \"payload\": {}}"
}
```

-----

### 7\. Error Handling: Incomplete Payload (Swap)

This `swap` event is missing the required `user_address` field in its payload. The function should return a `400 Bad Request` error with a message indicating the missing fields.

```json
{
  "path": "/metrics",
  "httpMethod": "POST",
  "body": "{\"eventType\": \"swap\", \"payload\": {\"tx_hash\": \"0x123abc456def7890123abc456def7890123abc456def7890123abc456def7890\", \"timestamp\": 1729171516, \"source_chain\": \"ethereum\", \"destination_chain\": \"polygon\"}}"
}
```