from collections import deque
import requests
from faker import Faker
import time

fake = Faker()
url = "https://hdtvstreams.com/api/auth/login"

exceeded = False

def rate_limit_test(login_url, max_attempts, delay):
    """
    Sends repeated fake login requests to test rate limiting.

    Stops when rate limiting is detected or max_attempts is reached.
    """

    for attempt in range(1, max_attempts + 1):
        data = {
            "email": fake.email(),
            "password": fake.password()
        }

        response = requests.post(login_url, data=data)

        print(f"Attempt {attempt}: Status {response.status_code}")

        # Common rate-limit signal
        if response.status_code == 429:
            print("Rate limiting detected, after ", attempt, "attempts.")
            exceeded = True
            break

        time.sleep(delay)

def main():
    print("Running rate limit attack simulation...")
    rate_limit_test(url, 100, 0.1)
    print("Rate limit exceeded:", exceeded)

if __name__ == "__main__":
    main()
