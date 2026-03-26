from curl_cffi import requests
import threading

count = 0 # Global counter for the number of requests sent
lock = threading.Lock() # Lock to synchronize access to the counter across threads


def send_request(): # Function to send a POST request to the target URL and check for rate limiting (HTTP 429 status code).
    global count

    # Send requests in an infinite loop until rate limited
    while True:
        r = requests.post("https://hdtvstreams.com/api/auth/login",
                          json={"email":"test@test.com","password":"password123"},
                          impersonate="chrome110")
        with lock:
            count += 1 # Increment the request counter in a thread-safe manner
            print(f"Request {count}: {r.status_code}") # Print the status code of each request for monitoring
            if r.status_code == 429:
                print(f"Rate limited at request {count}")

threads = [threading.Thread(target=send_request) for _ in range(5)] # Create multiple threads to send requests concurrently, increasing the likelihood of hitting rate limits faster
for t in threads:
    t.start() # Start all threads to begin sending requests simultaneously