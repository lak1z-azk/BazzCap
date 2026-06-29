import os
import shutil
import sys


_FROZEN_ENV_KEYS = {
    "APPDIR",
    "APPIMAGE",
    "ARGV0",
    "LD_LIBRARY_PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "_PYI_ARCHIVE_FILE",
    "_PYI_APPLICATION_HOME_DIR",
    "_PYI_LINUX_PROCESS_NAME",
    "_PYI_PARENT_PROCESS_LEVEL",
}


def is_flatpak() -> bool:
    return (
        os.path.isfile("/.flatpak-info")
        or "FLATPAK_ID" in os.environ
        or os.environ.get("container") == "flatpak"
        or any(p.startswith("/app/") for p in os.environ.get("PATH", "").split(":"))
    )


def is_frozen_bundle() -> bool:
    return bool(getattr(sys, "frozen", False))


def external_command_env() -> dict[str, str]:
    env = os.environ.copy()
    if is_frozen_bundle():
        for key in _FROZEN_ENV_KEYS:
            env.pop(key, None)
    return env


def _candidate_roots() -> list[str]:
    if not is_frozen_bundle():
        return [os.path.dirname(os.path.abspath(__file__))]

    roots = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        roots.append(meipass)

    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    roots.append(os.path.join(exe_dir, "_internal"))
    roots.append(exe_dir)
    return roots


def packaged_script_path(name: str) -> str:
    candidates = []
    for root in _candidate_roots():
        candidates.append(os.path.join(root, "bazzcap", name))
        candidates.append(os.path.join(root, name))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return candidates[0] if candidates else os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def iter_python_commands(prefer_host: bool = False) -> list[list[str]]:
    commands: list[list[str]] = []

    if prefer_host and shutil.which("flatpak-spawn"):
        commands.append(["flatpak-spawn", "--host", "/usr/bin/python3"])
        commands.append(["flatpak-spawn", "--host", "python3"])
        commands.append(["flatpak-spawn", "--host", "/usr/bin/python"])
        commands.append(["flatpak-spawn", "--host", "python"])

    for python_name in ("/usr/bin/python3", "/usr/bin/python", "python3", "python"):
        if os.path.isabs(python_name):
            if os.path.isfile(python_name) and os.access(python_name, os.X_OK):
                commands.append([python_name])
        elif shutil.which(python_name):
            commands.append([python_name])

    if not is_frozen_bundle() and sys.executable:
        commands.append([sys.executable])

    unique: list[list[str]] = []
    seen = set()
    for command in commands:
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        unique.append(command)
    return unique
