import httpx
import logging
import threading
from app.core.config import get_settings

logger = logging.getLogger(__name__)

def _wake_worker_machines_sync() -> None:
    settings = get_settings()
    app_name = settings.fly_worker_app_name
    token = settings.fly_api_token

    if not app_name:
        return

    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # If a token is provided, use the public Machines API; otherwise use internal flaps daemon
        url_base = f"https://api.machines.dev/v1/apps/{app_name}" if token else f"http://_api.internal:4000/v1/apps/{app_name}"

        logger.info("Querying Fly.io machines for worker app %s via %s", app_name, url_base)
        
        # Disable system proxies for internal API endpoint to prevent routing errors
        proxies = {} if not token else None
        
        with httpx.Client(proxies=proxies) as client:
            resp = client.get(f"{url_base}/machines", headers=headers, timeout=5.0)
            resp.raise_for_status()
            machines = resp.json()

            for machine in machines:
                machine_id = machine.get("id")
                state = machine.get("state")
                if state in ("stopped", "stopping"):
                    logger.warning("Starting stopped Fly machine %s for app %s...", machine_id, app_name)
                    start_resp = client.post(f"{url_base}/machines/{machine_id}/start", headers=headers, timeout=5.0)
                    start_resp.raise_for_status()
    except Exception as e:
        logger.error("Failed to automatically wake up Fly worker machines: %s", e, exc_info=True)


def trigger_worker_wakeup() -> None:
    """Asynchronously triggers the wakeup of stopped Fly worker machines in a background thread."""
    settings = get_settings()
    if not settings.fly_worker_app_name:
        return
        
    thread = threading.Thread(target=_wake_worker_machines_sync, name="FlyWorkerWakeup", daemon=True)
    thread.start()
