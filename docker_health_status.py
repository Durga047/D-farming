
import subprocess
import sys
import time


def show_logs(container):
    subprocess.run(
        ["docker", "logs", container],
        check=False,
    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python docker_health_status.py CONTAINER_NAME")
        return 2

    container = sys.argv[1]
    deadline = time.monotonic() + 50

    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                container,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print("Could not read Docker health status:")
            print(result.stderr)
            show_logs(container)
            return 1

        status = result.stdout.strip()
        print(f"Docker health status: {status}", flush=True)

        if status == "healthy":
            print("Docker health check passed.")
            return 0

        if status == "unhealthy":
            print("Docker container reported unhealthy status.")
            show_logs(container)
            return 1

        time.sleep(2)

    print("Timed out waiting for Docker to become healthy.")
    show_logs(container)
    return 1


if __name__ == "__main__":
    sys.exit(main())
