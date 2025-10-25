import os
import boto3

# Configure the DynamoDB client
dynamodb = boto3.resource("dynamodb")
rate_limit_table = dynamodb.Table(
    os.environ.get("RATE_LIMIT_TABLE_NAME", "api_rate_limits")
)
metrics_table = dynamodb.Table(os.environ.get("METRICS_TABLE_NAME", "metrics"))

# Rate limit configuration
RATE_LIMIT = 5000  # Number of requests allowed in 5 minutes
BUCKET_DURATION = 300  # 5 minutes in seconds

# Special key for tracking the last database reset (Note: Not used in current code)
RESET_TRACKER_KEY = "daily_reset_tracker"
