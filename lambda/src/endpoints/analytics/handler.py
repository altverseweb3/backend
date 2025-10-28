import json
from ...utils.utils import build_response
from ...config import ANALYTICS_API_KEY  # This is imported correctly

from .leaderboard import get_leaderboard, get_user_entry
from .users import get_total_users, get_periodic_user_stats
from .activity import get_total_activity_stats, get_periodic_activity_stats
from .swap import get_total_swap_stats, get_periodic_swap_stats
from .lending import get_total_lending_stats, get_periodic_lending_stats
from .earn import get_total_earn_stats, get_periodic_earn_stats

PUBLIC_QUERY_TYPES = {"leaderboard", "user_leaderboard_entry"}


def check_api_key(event):
    """
    Checks for a valid API key in the 'x-api-key' header.
    Returns None if the key is valid.

    Returns a 403 response object if the key is missing or invalid.
    """
    if not ANALYTICS_API_KEY:
        # This is a server-side configuration error
        print("Error: ANALYTICS_API_KEY environment variable is not set in Lambda.")
        return build_response(500, {"error": "Internal server configuration error"})

    # API Gateway often lowercases headers
    headers = event.get("headers", {})
    received_key = headers.get("x-api-key") or headers.get("X-Api-Key")

    if received_key == ANALYTICS_API_KEY:
        # Key is valid, allow request to proceed
        return None

    # Key is missing or invalid
    print("Invalid or missing API key.")
    return build_response(403, {"error": "Forbidden"})


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

        # Check the key for all query types EXCEPT the public ones.
        if query_type not in PUBLIC_QUERY_TYPES:
            api_key_response = check_api_key(event)
            if api_key_response:
                # If the key check fails, return the 403/500 response immediately.
                return api_key_response

        # --- Users Routes ---
        if query_type == "total_users":
            return get_total_users(body)
        elif query_type == "periodic_user_stats":
            return get_periodic_user_stats(body)

        # --- Activity Routes ---
        elif query_type == "total_activity_stats":
            return get_total_activity_stats(body)
        elif query_type == "periodic_activity_stats":
            return get_periodic_activity_stats(body)

        # --- Swap Routes ---
        elif query_type == "total_swap_stats":
            return get_total_swap_stats(body)
        elif query_type == "periodic_swap_stats":
            return get_periodic_swap_stats(body)

        # --- Lending Routes ---
        elif query_type == "total_lending_stats":
            return get_total_lending_stats(body)
        elif query_type == "periodic_lending_stats":
            return get_periodic_lending_stats(body)

        # --- Earn Routes ---
        elif query_type == "total_earn_stats":
            return get_total_earn_stats(body)
        elif query_type == "periodic_earn_stats":
            return get_periodic_earn_stats(body)

        # --- Leaderboard Routes ---
        elif query_type == "leaderboard":
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
