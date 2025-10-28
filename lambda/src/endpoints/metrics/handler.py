import json
from ...utils.utils import build_response, get_client_ip
from .entrance import process_entrance
from .swap import process_swap
from .lending import process_lending
from .earn import process_earn


# Expected event body structure for the /metrics endpoint:
# {
#   "eventType": "entrance' | "swap" | "lending" | "earn",
#   "payload": { ...event specific data... }
# }
# Note: "payload" is not required for "entrance" eventType.
def handle(event):
    """
    Single endpoint to handle various metric events (swap, lend, earn, entrance).
    Routes to the appropriate processor based on the 'eventType' in the request body.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        event_type = body.get("eventType")
        payload = body.get("payload", {})  # Default to empty dict if not present

        if not event_type:
            return build_response(
                400, {"error": "Request body must include 'eventType'"}
            )

        # Extract client IP once for potential use in processors
        ip_address = get_client_ip(event)

        if event_type == "entrance":
            return process_entrance()
        elif event_type == "swap":
            return process_swap(payload, ip_address)
        elif event_type == "lending":
            return process_lending(payload, ip_address)
        elif event_type == "earn":
            return process_earn(payload, ip_address)
        else:
            return build_response(400, {"error": f"Unknown eventType: '{event_type}'"})

    except json.JSONDecodeError:
        return build_response(400, {"error": "Invalid JSON body"})
    except Exception as e:
        print(f"An unexpected error occurred in handle_metrics: {str(e)}")
        return build_response(500, {"error": "An internal server error occurred"})
