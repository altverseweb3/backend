# AWS Lambda Test Events

These test events can be used to test the Lambda function that interfaces with the Alchemy API to retrieve blockchain data.

## 1. Test Endpoint
```json
{
  "path": "/test",
  "httpMethod": "GET",
  "body": "{}"
}
```

## 2. Token Balances Test
```json
{
  "path": "/balances",
  "httpMethod": "POST",
  "body": "{\"network\": \"eth-mainnet\", \"userAddress\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\", \"contractAddresses\": \"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,0x6B175474E89094C44Da98b954EedeAC495271d0F\"}"
}
```

## 3. Token Allowance Test
```json
{
  "path": "/allowance",
  "httpMethod": "POST",
  "body": "{\"network\": \"eth-mainnet\", \"userAddress\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\", \"contractAddress\": \"0x6B175474E89094C44Da98b954EedeAC495271d0F\", \"spenderAddress\": \"0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D\"}"
}
```

## 4. Token Metadata Test
```json
{
  "path": "/metadata",
  "httpMethod": "POST",
  "body": "{\"network\": \"eth-mainnet\", \"contractAddress\": \"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48\"}"
}
```

## 5. Token Prices Test 
```json
{
  "path": "/prices",
  "httpMethod": "POST",
  "body": "{\"addresses\": [{\"network\": \"eth-mainnet\", \"address\": \"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48\"}, {\"network\": \"eth-mainnet\", \"address\": \"0x6B175474E89094C44Da98b954EedeAC495271d0F\"}, {\"network\": \"eth-mainnet\", \"address\": \"0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2\"}, {\"network\": \"solana-mainnet\", \"address\": \"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v\"}]}"
}
```

## 6. Error Case - Missing Parameters for /balances
```json
{
  "path": "/balances",
  "httpMethod": "POST",
  "body": "{\"network\": \"eth-mainnet\"}"
}
```

## 8. Error Case - Invalid JSON for /metadata
```json
{
  "path": "/metadata",
  "httpMethod": "POST",
  "body": "{network: eth-mainnet, contractAddress: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48}"
}
```

## 9. Error Case - Path Not Found
```json
{
  "path": "/invalid-path",
  "httpMethod": "POST",
  "body": "{}"
}
```

## 10. Error Case - Invalid HTTP Method
```json
{
  "path": "/balances",
  "httpMethod": "DELETE",
  "body": "{\"network\": \"eth-mainnet\", \"userAddress\": \"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045\"}"
}
```

## 11. Error Case - Malformed Request in Prices Endpoint
```json
{
  "path": "/prices",
  "httpMethod": "POST",
  "body": "{\"addresses\": [{\"network\": \"eth-mainnet\", \"address\": \"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48\"}, {\"network\": \"avalanche-mainnet\"}]}"
}
```

## 12. SPL Token Balances Test
```json
{
  "path": "/spl-balances",
  "httpMethod": "POST",
  "body": "{\"network\": \"solana-mainnet\", \"userAddress\": \"J27ma1MPBRvmPJxLqBqQGNECMXDm9L6abFa4duKiPosa\"}"
}
```

## 13. SPL Token Balances with programId Filter Test
```json
{
  "path": "/spl-balances",
  "httpMethod": "POST",
  "body": "{\"network\": \"solana-mainnet\", \"userAddress\": \"J27ma1MPBRvmPJxLqBqQGNECMXDm9L6abFa4duKiPosa\", \"programId\": \"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA\"}"
}
```

## 14. SPL Token Balances with mint Filter Test
```json
{
  "path": "/spl-balances",
  "httpMethod": "POST",
  "body": "{\"network\": \"solana-mainnet\", \"userAddress\": \"J27ma1MPBRvmPJxLqBqQGNECMXDm9L6abFa4duKiPosa\", \"mint\": \"2FPyTwcZLUg1MDrwsyoP4D6s1tM7hAkHYRjkNb5w6Pxk\"}"
}
```

## 15. Error Case - Missing Parameters for /spl-balances
```json
{
  "path": "/spl-balances",
  "httpMethod": "POST",
  "body": "{\"network\": \"solana-mainnet\"}"
}
```

## References:
- Vitalik's address: `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045`
- USDC contract: `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`
- DAI contract: `0x6B175474E89094C44Da98b954EedeAC495271d0F`
- WETH contract: `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`
- WETH.e on Avalanche: `0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB`
- Uniswap Router: `0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D`
- Solana sample address: `J27ma1MPBRvmPJxLqBqQGNECMXDm9L6abFa4duKiPosa`
- SPL Token Program ID: `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`