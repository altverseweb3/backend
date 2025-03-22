## AWS Lambda Test Events

### 1. Test Endpoint

```json
{
  "path": "/test",
  "httpMethod": "GET",
  "body": "{}"
}
```

### 2. Token Balances Test

```json
{
  "path": "/balances",
  "httpMethod": "GET",
  "body": "{\"network\": \"eth-mainnet\", \"userAddress\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\", \"contractAddresses\": \"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,0x6B175474E89094C44Da98b954EedeAC495271d0F\"}"
}
```

### 3. Token Allowance Test

```json
{
  "path": "/allowance",
  "httpMethod": "GET",
  "body": "{\"network\": \"eth-mainnet\", \"userAddress\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\", \"contractAddress\": \"0x6B175474E89094C44Da98b954EedeAC495271d0F\", \"spenderAddress\": \"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\"}"
}
```

### 4. Token Metadata Test

```json
{
  "path": "/metadata",
  "httpMethod": "GET",
  "body": "{\"network\": \"eth-mainnet\", \"contractAddress\": \"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48\"}"
}
```

### 5. Error Case - Missing Parameters

```json
{
  "path": "/balances",
  "httpMethod": "GET",
  "body": "{\"network\": \"eth-mainnet\"}"
}
```

### 6. Error Case - Invalid JSON

```json
{
  "path": "/metadata",
  "httpMethod": "GET",
  "body": "{network: eth-mainnet, contractAddress: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48}"
}
```

### 7. Error Case - Path Not Found

```json
{
  "path": "/invalid-path",
  "httpMethod": "GET",
  "body": "{}"
}
```

### 8. Error Case - Invalid HTTP Method

```json
{
  "path": "/balances",
  "httpMethod": "DELETE",
  "body": "{\"network\": \"eth-mainnet\", \"userAddress\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\"}"
}
```

References:
- Vitalik's address: `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045`
- USDC contract: `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`
- DAI contract: `0x6B175474E89094C44Da98b954EedeAC495271d0F`
- Uniswap Router: `0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D`