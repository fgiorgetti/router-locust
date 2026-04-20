import random
import urllib3
import requests
from locust import HttpUser, task, between, events
from requests.adapters import HTTPAdapter

# Disable SSL warnings if hitting self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Target hosts — each request picks one (or assign per-user in on_start)
# ---------------------------------------------------------------------------
TARGET_HOSTS = [
    "http://127.0.0.1:8181",
    "http://127.0.0.1:8282",
    "http://127.0.0.1:8383",
]


class NoKeepAliveAdapter(HTTPAdapter):
    """HTTP adapter that forces a new TCP connection for every request."""

    def send(self, request, **kwargs):
        request.headers["Connection"] = "close"
        return super().send(request, **kwargs)


class FreshConnectionSession(requests.Session):
    """Session whose pool is discarded after every request."""

    def __init__(self):
        super().__init__()
        # Mount our no-keep-alive adapter for http
        adapter = NoKeepAliveAdapter(
            pool_connections=1,
            pool_maxsize=1,
        )
        self.mount("http://", adapter)

    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        # Close the underlying connection immediately so it isn't pooled
        response.close()
        return response


class MultiHostUser(HttpUser):
    """
    A simulated user that:
    - Uses a fresh TCP connection for every request
    - Sends requests to randomly selected hosts from TARGET_HOSTS
    """

    # Locust requires a host, but we override it per-request below.
    # Set to the first host as a fallback / for the Locust web UI label.
    host = TARGET_HOSTS[0]

    wait_time = between(0.5, 2.0)  # seconds between tasks

    def on_start(self):
        # Replace the Locust-managed session with our fresh-connection session
        self.client.session = FreshConnectionSession()

    def _random_host(self) -> str:
        return random.choice(TARGET_HOSTS)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task(3)
    def get_health(self):
        host = self._random_host()
        url = f"{host}/health"
        with self.client.get(
            url,
            name="/health",          # groups results by name in the UI
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status {resp.status_code} from {host}")

    @task(5)
    def get_resource(self):
        host = self._random_host()
        resource_id = random.randint(1, 1000)
        url = f"{host}/api/resource/{resource_id}"
        with self.client.get(
            url,
            name="/api/resource/[id]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 404:
                resp.success()   # 404 is an expected/valid response here
            else:
                resp.failure(f"Bad status {resp.status_code}")

    @task(2)
    def post_event(self):
        host = self._random_host()
        url = f"{host}/api/events"
        payload = {"type": "load_test", "value": random.random()}
        with self.client.post(
            url,
            json=payload,
            name="/api/events",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 201, 202):
                resp.failure(f"POST failed: {resp.status_code}")
