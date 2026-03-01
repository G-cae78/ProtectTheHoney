from curl_cffi import requests
import threading

count = 0
lock = threading.Lock()

def send_request():
    global count
    while True:
        r = requests.post("https://hdtvstreams.com/api/auth/login",
                          json={"email":"test@test.com","password":"password123"},
                          impersonate="chrome110")
        with lock:
            count += 1
            print(f"Request {count}: {r.status_code}")
            if r.status_code == 429:
                print(f"Rate limited at request {count}")

threads = [threading.Thread(target=send_request) for _ in range(5)]
for t in threads:
    t.start()