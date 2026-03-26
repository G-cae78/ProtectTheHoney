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
ip_lock = threading.Lock() # Lock to synchronize access to PUBLIC_IP across threads
    
def get_public_ip(): # Function to retrieve the public IP address of the machine running the Locust tests, with caching to avoid redundant API calls.
    global PUBLIC_IP
    with ip_lock:
        if PUBLIC_IP is None:
            try:
                PUBLIC_IP = requests.get("https://api.ipify.org").text.strip()
            except Exception:
                PUBLIC_IP = "unknown"
        return PUBLIC_IP
    
class RateLimitUser(HttpUser): # Locust user class that simulates login attempts to test rate limiting on the target API.
    wait_time = between(0.01, 0.05)  # aggressive but reasonable
    host = "https://hdtvstreams.com"

    def on_start(self):
        self.request_count = 0
        self.rate_limited = False
        self.public_ip = get_public_ip()

    @task
    def login_attempt(self): # Task that sends POST requests to the login endpoint, checking for rate limiting (HTTP 429) and edge blocking (HTTP 403), while counting requests and printing status codes for monitoring.

        # Generate random credentials for each login attempt to avoid triggering simple credential-based blocks, while focusing on testing rate limits and edge blocks based on request volume and patterns rather than specific user accounts.
        payload = {
            "email": fake.email(),
            "password": fake.password()
        }

        # Send the POST request to the login endpoint and handle responses to detect rate limiting and edge blocking, while printing relevant information for monitoring and debugging.
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
                self.request_count = 0

            elif response.status_code == 403:
                response.success()  # EXPECTED: blocked at Cloudflare edge
                print("\n--- EDGE BLOCK ---")
                print(f"Status: {response.status_code}")
                print("Headers:")
                for k, v in response.headers.items():
                    print(f"  {k}: {v}")
                print("\nBody (first 500 chars):")
                print(response.text[:500])
                print("------------------\n")

            elif response.status_code == 401:
                response.success()  # invalid credentials = expected

            else:
                response.failure(f"Unexpected status: {response.status_code}")


    @task
    def load_assets(self): # Additional task to load the homepage, which may trigger different rate limits or edge blocks based on overall traffic patterns, while monitoring responses for success or failure.
        with self.client.get(
            "/",
            catch_response=True,
            name="/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to load homepage: {response.status_code}")

class StepLoadShape(LoadTestShape): # Custom load shape that gradually increases the number of users over time to find the rate-limit threshold, with configurable parameters for step duration, user increments, spawn rate, and maximum users.
    """
    Gradually increases load to find rate-limit threshold
    """

    step_time = 1       # seconds per step
    step_users = 5      # users added per step
    spawn_rate = 10       # users per second
    max_users = 500

    def tick(self):
        run_time = self.get_run_time() # Get the total run time of the test in seconds

        current_step = run_time // self.step_time # Calculate the current step based on elapsed time and step duration
        users = min((current_step + 1) * self.step_users, self.max_users) # Calculate the total number of users to simulate based on the current step, ensuring it does not exceed the maximum user limit

        return (users, self.spawn_rate) # Return the current user count and spawn rate for Locust to adjust the load accordingly