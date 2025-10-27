import json
from ...utils.utils import build_response

from .leaderboard import get_leaderboard, get_user_entry
from .users import get_total_users, get_periodic_user_stats
from .activity import get_total_activity_stats, get_periodic_activity_stats
from .swap import get_total_swap_stats, get_periodic_swap_stats
from .lending import get_total_lending_stats, get_periodic_lending_stats


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
