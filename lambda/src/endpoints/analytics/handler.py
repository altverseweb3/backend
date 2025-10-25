import json
from ...utils.utils import build_response

from .leaderboard import get_leaderboard, get_user_entry


def handle(event):
    """
    Single endpoint to handle various analytics queries.
    Routes to the appropriate processor based on the 'queryType' in the request body.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        query_type = body.get("queryType")

        if not query_type:
            return build_response(
                400, {"error": "Request body must include 'queryType'"}
            )

        # Route to the imported functions
        if query_type == "leaderboard":
            return get_leaderboard(body)
        elif query_type == "user_leaderboard_entry":
            return get_user_entry(body)

        else:
            return build_response(400, {"error": f"Unknown queryType: '{query_type}'"})

    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})
    except Exception as e:
        print(f"An unexpected error occurred in handle_analytics: {str(e)}")
        return build_response(500, {"error": "An internal server error occurred"})
