# Simulate Cyber-Attacks

This folder contains the tools used to generate traffic against the honeypot during testing. The goal was to verify that Cloudflare's rate limiting and WAF rules were actually firing, and to see how the ML pipeline categorised different kinds of attack traffic.

---

## rate_limit tests/

Three scripts that each probe the login endpoint in slightly different ways. All of them target `https://hdtvstreams.com/api/auth/login`.

### rate_limit.py

The simplest one. Fires up to 400 sequential login requests with a tiny delay (1ms) between each, using randomly generated credentials from Faker. Stops early if it gets a 429 back.

Good for a quick sanity check that rate limiting is turned on at all.

```bash
pip install requests faker
python rate_limit.py
```

### curl-cffi.py

Sends login requests using `curl_cffi` with Chrome 110 TLS fingerprint impersonation. The point is to look like a real browser at the TLS layer, which bypasses some basic bot detection that relies on fingerprinting. Spins up 5 threads running in infinite loops.

Useful for testing whether Cloudflare's bot detection can still catch traffic that looks like a legit Chrome browser.

```bash
pip install curl-cffi
python curl-cffi.py
```

Stop it with `Ctrl+C` since it runs forever.

### locust_load.py

The most involved of the three. Uses Locust with a `StepLoadShape` to gradually ramp from 0 up to 500 concurrent users, adding 5 users per step. Each virtual user sends login attempts and homepage requests, and logs whenever it hits a 429 or gets blocked at the edge (403).

This was used to find the rate limit threshold and confirm that Cloudflare was blocking at the right point.

```bash
pip install locust faker requests
locust -f locust_load.py --headless --run-time 5m
```

Or open the Locust web UI by running without `--headless` and navigating to `http://localhost:8089`.

---

## GoldenEye/

A cloned copy of the [GoldenEye](https://github.com/jseidl/GoldenEye) HTTP DoS tool, used to simulate layer-7 denial of service attacks. See its own `README.md` for usage.

This was used to test how the honeypot and Cloudflare handled sustained high-volume traffic, and to check whether that kind of traffic pattern gets flagged by the ML clustering pipeline.

---

## Notes

- All scripts are pointed at the live honeypot domain. Don't run them against anything you don't own or have permission to test.
- The ML pipeline picks up this traffic through nginx logs, so running these during a batch window is a good way to verify the pipeline end-to-end.
