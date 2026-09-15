"""Per-user desktop integration. No slicer configuration or executable is changed."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .files import atomic_write
from .model import LinkError, canonical, require

APP = "OnshapeSlicerLink"


def config_dir():
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / APP
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "onshape-slicer-link"


def read_config():
    path = config_dir() / "settings.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def save_config(config):
    atomic_write(config_dir() / "settings.json", canonical(config).encode())


def credential_key(origin):
    from .model import digest

    return "device-" + digest(origin.encode())


def secret(origin, value=None):
    import keyring
    from keyring.errors import KeyringError

    try:
        # Only native credential stores. Never fall back to a plaintext plugin.
        supported = ("keyring.backends.Windows", "keyring.backends.SecretService", "keyring.backends.kwallet")
        backend = keyring.get_keyring()
        if not type(backend).__module__.startswith(supported):
            from keyring.backend import get_all_keyring

            candidates = [
                candidate
                for candidate in get_all_keyring()
                if type(candidate).__module__.startswith(supported) and candidate.priority > 0
            ]
            backend = max(candidates, key=lambda candidate: candidate.priority) if candidates else backend
        require(
            type(backend).__module__.startswith(supported),
            "Unlock your desktop password store and retry. On Linux, enable Secret Service or KWallet.",
        )
        if value is not None:
            backend.set_password(APP, credential_key(origin), value)
            return value
        return backend.get_password(APP, credential_key(origin))
    except KeyringError:
        raise LinkError("The desktop password store is unavailable. Unlock it and retry.") from None


def launch(command):
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        kwargs["startupinfo"] = startup
    subprocess.Popen(command, **kwargs)


def pick_slicer(kind="slicer"):
    """A native chooser in its own GUI process; no Tk calls from HTTP threads."""
    folder = config_dir() / "local"
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".picker-", suffix=".json", dir=folder)
    os.close(descriptor)
    path = Path(name)
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command += ["-m", "slicer_link.local"]
    command += ["--pick-slicer", str(path), "--pick-kind", kind]
    try:
        options = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.run(command, check=True, timeout=300, **options)
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, subprocess.SubprocessError):
        raise LinkError("The file picker did not finish. Try again or paste the executable path.") from None
    finally:
        path.unlink(missing_ok=True)


def open_folder(path):
    # The user explicitly chose to open a visible folder.
    if sys.platform == "win32":
        os.startfile(str(Path(path).resolve()))
    else:
        subprocess.Popen(
            ["xdg-open", str(Path(path).resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def slicers():
    found = {}
    if sys.platform == "win32":
        for name, folder, binary in (
            ("OrcaSlicer", "OrcaSlicer", "orca-slicer.exe"),
            ("Bambu Studio", "Bambu Studio", "bambu-studio.exe"),
        ):
            for base in (
                os.environ.get("ProgramFiles", "C:/Program Files"),
                str(Path(os.environ["LOCALAPPDATA"]) / "Programs"),
            ):
                path = Path(base) / folder / binary
                if path.is_file():
                    found[name] = [str(path)]
                    break
    else:
        for name, command in (("OrcaSlicer", "orca-slicer"), ("Bambu Studio", "bambu-studio")):
            if path := shutil.which(command):
                found[name] = [path]
        if shutil.which("flatpak"):
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            installed = result.stdout.splitlines()
            for name, app_id in (
                ("OrcaSlicer", "com.orcaslicer.OrcaSlicer"),
                ("Bambu Studio", "com.bambulab.BambuStudio"),
            ):
                if app_id in installed and name not in found:
                    found[name] = ["flatpak", "run", app_id]
    return found


def helper_command():
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve())]
    executable = Path(sys.executable)
    if sys.platform == "win32" and executable.with_name("pythonw.exe").exists():
        executable = executable.with_name("pythonw.exe")
    return [str(executable), "-m", "slicer_link.helper"]


def local_command():
    command = helper_command()
    if not getattr(sys, "frozen", False):
        command[-1] = "slicer_link.local"
    return command


def register_local_shortcut():
    """Install a per-user Linux application menu entry, with a setup action."""
    if sys.platform == "win32":
        return
    applications = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
    command = local_command()
    content = (
        "[Desktop Entry]\nType=Application\nName=Onshape Slicer Link\n"
        "Comment=Send Onshape parts to your slicer\nTerminal=false\nCategories=Graphics;Engineering;\n"
        "Exec=" + desktop_exec(command).removesuffix(" %u") + "\nActions=Setup;\n\n"
        "[Desktop Action Setup]\nName=Connection setup\n"
        "Exec=" + desktop_exec(command + ["--setup"]).removesuffix(" %u") + "\n"
    )
    atomic_write(applications / "onshape-slicer-link.desktop", content.encode())


def desktop_exec(arguments):
    """Desktop Entry Exec quoting, including its field-code percent escaping."""

    def quoted(value):
        require(not any(c in value for c in "\n\r\0"), "Invalid application path.")
        escaped = value.replace("%", "%%")
        for char in ("\\", '"', "`", "$"):
            escaped = escaped.replace(char, "\\" + char)
        return '"' + escaped + '"'

    return " ".join(quoted(value) for value in arguments) + " %u"


def register_protocol():
    command = helper_command()
    if sys.platform == "win32":
        import winreg

        base = r"Software\Classes\onshape-slicer-link"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Onshape Slicer Link")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, subprocess.list2cmdline(command) + ' "%1"')
    else:
        applications = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
        name = "onshape-slicer-link.desktop"
        content = (
            "[Desktop Entry]\nType=Application\nName=Onshape Slicer Link\n"
            "Comment=Transfer Onshape parts to your slicer\nTerminal=false\nCategories=Graphics;Engineering;\n"
            "MimeType=x-scheme-handler/onshape-slicer-link;\nExec=" + desktop_exec(command) + "\n"
        )
        atomic_write(applications / name, content.encode())
        require(shutil.which("xdg-mime"), "Install your desktop's xdg-utils package, then retry setup.")
        subprocess.run(
            ["xdg-mime", "default", name, "x-scheme-handler/onshape-slicer-link"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        if shutil.which("update-desktop-database"):
            subprocess.run(
                ["update-desktop-database", str(applications)], check=True, capture_output=True, timeout=15
            )
