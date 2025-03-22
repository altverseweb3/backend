import json

def lambda_handler(event, context):
    if event["path"] == "/test":
        if event["httpMethod"] == "GET":
            response_data = {"message": "Hello from altverse /test"}
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "**",
                    "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
                },
                "body": json.dumps(response_data).encode("utf-8"),
            }
    # else:
    #     return {
    #         "statusCode": 404,
    #         "headers": {
    #             "Access-Control-Allow-Origin": "*",
    #             "Access-Control-Allow-Headers": "**",
    #             "Access-Control-Allow-Methods": "ANY,OPTIONS,POST,GET",
    #         },
    #         "body": json.dumps({"message": "Not Found"}).encode("utf-8"),
    #     }
