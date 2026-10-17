import json
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:5056/health"
TIMEOUT_SECONDS = 30
RETRY_INTERVAL_SECONDS = 2

deadline = time.monotonic() + TIMEOUT_SECONDS
last_error = None

while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(URL, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))

            if response.status != 200:
                raise RuntimeError(
                    f"Unexpected HTTP status: {response.status}"
                )

            if data.get("status") != "ok":
                raise RuntimeError(f"Unexpected health response: {data}")

            if data.get("database") != "connected":
                raise RuntimeError(f"Database check failed: {data}")

            print(f"Container health check passed: {data}")
            break

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        RuntimeError,
    ) as error:
        last_error = error
        time.sleep(RETRY_INTERVAL_SECONDS)
else:
    raise SystemExit(f"Container health check failed: {last_error}")
