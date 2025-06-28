curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "swapperAddress": "0x123abc789def0123456789abcdef0123456789"
  }' \
  $API_GATEWAY_URL/swap-metrics

curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "swapperAddress": "0x123abc789def0123456789abcdef0123456789",
    "txHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef123456",
    "swapType": "vanilla"
  }' \
  $API_GATEWAY_URL/swap-metrics

curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "swapperAddress": "0x123abc789def0123456789abcdef0123456789",
    "txHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef123456",
    "swapType": "earn/etherFi",
    "path": "ETH/USDC",
    "amount": "1000000000000000000",
    "tokenIn": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "tokenOut": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "network": "eth-mainnet"
  }' \
  $API_GATEWAY_URL/swap-metrics