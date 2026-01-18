import threading
from time import gmtime, strftime, time
from locust import HttpUser, task, between
from faker import Faker
from locust import LoadTestShape
import requests

fake = Faker()
time = time()
# Resolve Locust worker public IP once
PUBLIC_IP = None
ip_lock = threading.Lock()
    
def get_public_ip():
    global PUBLIC_IP
    with ip_lock:
        if PUBLIC_IP is None:
            try:
                PUBLIC_IP = requests.get("https://api.ipify.org").text.strip()
            except Exception:
                PUBLIC_IP = "unknown"
        return PUBLIC_IP
    
class RateLimitUser(HttpUser):
    wait_time = between(0.01, 0.03)  # aggressive but reasonable
    host = "https://hdtvstreams.com"

    def on_start(self):
        self.request_count = 0
        self.rate_limited = False
        self.public_ip = get_public_ip()

    @task
    def login_attempt(self):
        payload = {
            "email": fake.email(),
            "password": fake.password()
        }

        with self.client.post(
            "/api/auth/login",
            json=payload,
            catch_response=True,
            name="/api/auth/login"
        ) as response:

            self.request_count += 1
            if response.status_code == 429:
                self.rate_limited = True
                response.success()
                print(
                    f"Time: {strftime('%Y-%m-%d %H:%M:%S', gmtime())} - "
                    f"[429 HIT] Public IP: {self.public_ip} | "
                    f"Requests before limit: {self.request_count}"
                )
                self.request_count = 0  # reset for next cycle
            elif response.status_code in [401, 403]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

class StepLoadShape(LoadTestShape):
    """
    Gradually increases load to find rate-limit threshold
    """

    step_time = 1       # seconds per step
    step_users = 2        # users added per step
    spawn_rate = 1        # users per second
    max_users = 1

    def tick(self):
        run_time = self.get_run_time()

        current_step = run_time // self.step_time
        users = min((current_step + 1) * self.step_users, self.max_users)

        return (users, self.spawn_rate)