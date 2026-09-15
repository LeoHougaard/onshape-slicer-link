"""Development runtime for stock slicers in a dedicated WSL/container desktop.

No Docker Desktop, host display mount, host credentials or privileged container.
Only the isolated runtime's port and persistent /config volume are exposed.
"""

import argparse
import base64
import json
import secrets
import subprocess
import time
from pathlib import Path

import httpx

from slicer_link import platforms
from slicer_link.files import folder_lock

DISTRO = "OnshapeSlicerProbe"
PORTS = {"orca": 18871, "bambu": 18872}
IMAGES = {
    "orca": "lscr.io/linuxserver/orcaslicer@sha256:da376d4048875d7c328fd7c7e79a1ef67678f5418101e56621e47443bfb9a68c",
    "bambu": "lscr.io/linuxserver/bambustudio@sha256:7f31ec3fecb07338eb391674f4a4436fed4c5ceab238e5bbc31c330cbf4196ff",
}
ROOT = Path(__file__).resolve().parents[1]


def password():
    name = "embedded-runtime-development-v1"
    with folder_lock(platforms.config_dir() / "embedded" / "credential"):
        value = platforms.secret(name)
        if not value:
            value = secrets.token_urlsafe(32)
            platforms.secret(name, value)
    return value


def authorization():
    return "Basic " + base64.b64encode(f"slicer-link:{password()}".encode()).decode()


def docker(*args, data=None, timeout=60):
    result = subprocess.run(
        ["wsl", "-d", DISTRO, "--", "docker", *args],
        input=data,
        capture_output=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.stdout


def ensure_engine():
    """Resume only the application's existing WSL distribution after a reboot."""
    try:
        docker("info", "--format", "{{.ServerVersion}}", timeout=10)
        return
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    # No host daemon, startup configuration or other WSL distribution is changed.
    result = subprocess.run(
        [
            "wsl",
            "-d",
            DISTRO,
            "--",
            "sh",
            "-c",
            (
                "command -v dockerd >/dev/null && "
                "nohup dockerd --host=unix:///var/run/docker.sock "
                ">/var/log/osl-dockerd.log 2>&1 </dev/null &"
            ),
        ],
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("The dedicated WSL runtime is not installed or could not start.")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            docker("info", "--format", "{{.ServerVersion}}", timeout=5)
            return
        except (RuntimeError, subprocess.TimeoutExpired):
            time.sleep(0.5)
    raise RuntimeError(
        "Docker did not start in the dedicated WSL runtime. Check /var/log/osl-dockerd.log there."
    )


def start(kind):
    ensure_engine()
    name = f"osl-{kind}-development"
    names = docker("container", "ls", "-a", "--format", "{{.Names}}").decode().splitlines()
    if name in names:
        docker("start", name)
        return
    environment = {
        "PUID": "1000",
        "PGID": "1000",
        "TZ": "America/Vancouver",
        "CUSTOM_USER": "slicer-link",
        "PASSWORD": password(),
        "SUBFOLDER": f"/desktop/{kind}/",
        "PELORUS": "true",
        "SELKIES_AUDIO_ENABLED": "false|locked",
        "SELKIES_MICROPHONE_ENABLED": "false|locked",
        "SELKIES_GAMEPAD_ENABLED": "false|locked",
        "SELKIES_MANUAL_WIDTH": "1280",
        "SELKIES_CLIPBOARD_ENABLED": "false|locked",
        "SELKIES_ENABLE_SHARING": "false|locked",
        "SELKIES_MANUAL_HEIGHT": "800",
        "SELKIES_FRAMERATE": "20",
        "SELKIES_UI_SHOW_SIDEBAR": "false",
        "NO_GAMEPAD": "1",
    }
    docker(
        "run",
        "-d",
        "--name",
        name,
        "--shm-size=1g",
        "--memory=8g",
        "--cpus=4",
        "--publish",
        f"127.0.0.1:{PORTS[kind]}:3000",
        "--volume",
        f"osl-{kind}-development:/config",
        "--env-file",
        "/dev/stdin",
        IMAGES[kind],
        data="".join(f"{key}={value}\n" for key, value in environment.items()).encode(),
        timeout=120,
    )


def request(kind, path, body=None):
    url = f"http://127.0.0.1:{PORTS[kind]}/desktop/{kind}/pelorus{path}"
    with httpx.Client(headers={"Authorization": authorization()}, timeout=30, trust_env=False) as client:
        response = client.get(url) if body is None else client.post(url, json=body)
        response.raise_for_status()
        return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "state", "windows", "screenshot", "control", "explore"])
    parser.add_argument("kind", choices=PORTS)
    parser.add_argument("--json", help="Desktop input as JSON, or PID for explore")
    options = parser.parse_args()
    if options.action == "start":
        start(options.kind)
        print(f"Started dedicated {options.kind} desktop.")
    elif options.action == "screenshot":
        result = request(options.kind, "/api/desktop/screenshot")
        image = result.get("screenshot") or result.get("image") or result.get("data")
        if not image:
            print({key: str(value)[:100] for key, value in result.items()})
            return
        path = ROOT / "artifacts" / "embedded" / f"{options.kind}-desktop.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(image.split(",")[-1]))
        print(path)
    elif options.action == "control":
        result = request(options.kind, "/api/desktop/control", json.loads(options.json))
        print(
            json.dumps(
                {key: value for key, value in result.items() if key not in {"screenshot", "image", "data"}}
            )
        )
    elif options.action == "explore":
        result = request(options.kind, f"/api/desktop/explore/{int(options.json)}")
        print(json.dumps({key: value for key, value in result.items() if key != "screenshot"}))
    else:
        print(json.dumps(request(options.kind, f"/api/{options.action}")))


if __name__ == "__main__":
    main()
