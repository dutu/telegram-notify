#!/usr/bin/env python3
"""Install a trusted local source tree; never fetch or update Git repositories."""

import argparse
import contextlib
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass


SOURCE = Path(__file__).resolve().parent
FILES = (
    "telegram-notify.py", "telegram-gateway.py", "telegram_notify_core.py",
    "telegram-notify.ini.example", "telegram-gateway.service.example",
    "install.py", "migrate-config.py", "README.md", "README_CLI.md",
    "README_GATEWAY.md", "pyproject.toml",
)


@dataclass(frozen=True)
class Paths:
    prefix: Path = Path("/opt/telegram-notify")
    config: Path = Path("/etc/telegram-notify/telegram-notify.ini")
    command: Path = Path("/usr/local/bin/telegram-notify")
    unit: Path = Path("/etc/systemd/system/telegram-gateway.service")

    @property
    def manifest(self):
        return self.prefix / "installation.json"

    @property
    def current(self):
        return self.prefix / "current"

    @property
    def command_target(self):
        return self.current / "telegram-notify.py"


def run(*args):
    subprocess.run(args, check=True)


def exists(path):
    return path.exists() or path.is_symlink()


def digest(source):
    result = hashlib.sha256()
    for name in FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing regular source file: {path}")
        result.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return result.hexdigest()[:16]


def unit_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(paths):
    if (paths.prefix / "releases").is_symlink():
        raise ValueError("releases must not be a symlink")
    if paths.manifest.is_symlink():
        raise ValueError("installation.json must not be a symlink")
    if not paths.manifest.exists():
        allowed = {"install.lock"}
        if paths.prefix.exists() and any(p.name not in allowed for p in paths.prefix.iterdir()):
            raise ValueError(
                f"{paths.prefix} is not an installer-managed directory. For an old Git "
                "installation, run migrate-config.py, then move the old checkout to a "
                "backup location outside this directory. See README.md."
            )
        return None
    state = json.loads(paths.manifest.read_text())
    if not isinstance(state, dict):
        raise ValueError("invalid installation manifest")
    releases = state.get("releases")
    if (state.get("schema") != 1 or not isinstance(releases, list) or not releases
            or any(not isinstance(r, str) or not re.fullmatch(r"[0-9a-f]{16}", r) for r in releases)
            or len(set(releases)) != len(releases) or state.get("active") not in releases
            or type(state.get("gateway")) is not bool
            or (state["gateway"] and (not isinstance(state.get("unit_digest"), str)
                                     or not re.fullmatch(r"[0-9a-f]{64}", state["unit_digest"])))):
        raise ValueError("invalid installation manifest")
    if not paths.current.is_symlink() or os.readlink(paths.current) != f"releases/{state['active']}":
        raise ValueError("current link differs from the installation manifest")
    if not paths.command.is_symlink() or os.readlink(paths.command) != str(paths.command_target):
        raise ValueError(f"command has been replaced or removed: {paths.command}")
    if state["gateway"]:
        if paths.unit.is_symlink() or not paths.unit.is_file() or unit_digest(paths.unit) != state["unit_digest"]:
            raise ValueError(f"gateway unit has been modified or removed: {paths.unit}; back it up and restore the installed template before retrying")
    return state


def check_config(paths):
    if paths.config.parent.is_symlink() or paths.config.is_symlink():
        raise ValueError(f"configuration must not be a symlink: {paths.config}")
    if exists(paths.config) and not paths.config.is_file():
        raise ValueError(f"configuration is not a regular file: {paths.config}")


def check_service():
    for command in ("systemctl", "systemd-analyze"):
        if not shutil.which(command):
            raise ValueError(f"gateway installation requires {command}")
    result = subprocess.run(
        ["systemctl", "show", "telegram-gateway.service", "--property=ActiveState", "--value"],
        check=True, capture_output=True, text=True,
    )
    if result.stdout.strip() not in ("inactive", "failed"):
        raise ValueError("stop telegram-gateway.service before installation, update, or removal")


def ensure_gateway_user():
    try:
        account = pwd.getpwnam("telegram-gateway")
    except KeyError:
        run("useradd", "--system", "--user-group", "--no-create-home",
            "--shell", "/usr/sbin/nologin", "telegram-gateway")
    else:
        if account.pw_uid == 0:
            raise ValueError("telegram-gateway must not have UID 0")
        try:
            grp.getgrnam("telegram-gateway")
        except KeyError as exc:
            raise ValueError("existing telegram-gateway account needs a telegram-gateway group") from exc


def atomic_write(path, data, mode=0o644):
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_link(path, target):
    # A private directory avoids replacing any pre-existing temporary link.
    with tempfile.TemporaryDirectory(prefix=f".{path.name}.", dir=path.parent) as directory:
        temporary = Path(directory) / "link"
        temporary.symlink_to(target)
        os.replace(temporary, path)


def snapshot(path):
    if path.is_symlink():
        return ("link", os.readlink(path))
    if path.is_file():
        return ("file", path.read_bytes(), path.stat().st_mode & 0o777)
    if exists(path):
        raise ValueError(f"expected a file or symlink: {path}")
    return ("absent",)


def restore(path, saved):
    if saved[0] == "link":
        atomic_link(path, saved[1])
    elif saved[0] == "file":
        atomic_write(path, saved[1], saved[2])
    else:
        path.unlink(missing_ok=True)


@contextlib.contextmanager
def transaction(paths, gateway):
    targets = [paths.current, paths.command, paths.manifest]
    if gateway:
        targets.append(paths.unit)
    saved = [(path, snapshot(path)) for path in targets]
    try:
        yield
    except BaseException:
        for path, previous in reversed(saved):
            restore(path, previous)
        if gateway:
            run("systemctl", "daemon-reload")
        raise


def validate_source(source, gateway):
    for name in FILES:
        if name.endswith(".py"):
            compile((source / name).read_bytes(), str(source / name), "exec")
    subprocess.run([sys.executable, "-B", str(source / "telegram-notify.py"), "--help"],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "-B", "-c",
                    "import runpy, sys; sys.path.insert(0, sys.argv[1]); "
                    "runpy.run_path(sys.argv[1] + '/telegram-gateway.py')", str(source)], check=True)
    if gateway:
        with tempfile.TemporaryDirectory(prefix="telegram-notify-verify-") as directory:
            unit = Path(directory) / "telegram-gateway.service"
            unit.write_bytes((source / "telegram-gateway.service.example").read_bytes())
            run("systemd-analyze", "verify", str(unit))


@contextlib.contextmanager
def prepared_release(paths, source, gateway, release_id):
    releases = paths.prefix / "releases"
    release = releases / release_id
    created = False
    committed = False
    try:
        releases.mkdir(mode=0o755, exist_ok=True)
        if releases.is_symlink():
            raise ValueError("releases must not be a symlink")
        os.chown(releases, 0, 0)
        releases.chmod(0o755)
        if exists(release):
            if release.is_symlink() or digest(release) != release_id:
                raise ValueError(f"existing release differs from its source digest: {release}")
            validate_source(release, gateway)
        else:
            with tempfile.TemporaryDirectory(prefix=".staging-", dir=paths.prefix) as directory:
                stage = Path(directory) / "release"
                stage.mkdir(mode=0o755)
                stage.chmod(0o755)
                for name in FILES:
                    shutil.copyfile(source / name, stage / name)
                    (stage / name).chmod(0o755 if name.endswith(".py") else 0o644)
                if digest(stage) != release_id:
                    raise ValueError("source changed while staging; retry from a stable checkout")
                validate_source(stage, gateway)
                stage.rename(release)
                created = True
        yield release
        committed = True
    finally:
        # A failed activation normally restores current before this cleanup runs.
        # If restoration failed, preserve any release still referenced by current.
        active = paths.current.is_symlink() and os.readlink(paths.current) == f"releases/{release_id}"
        if created and not committed and not active:
            for name in FILES:
                (release / name).unlink(missing_ok=True)
            release.rmdir()
        if releases.is_dir() and not releases.is_symlink() and not any(releases.iterdir()):
            releases.rmdir()


def deploy(paths, source, mode, with_gateway=False, dry_run=False):
    state = read_manifest(paths)
    if mode == "update" and state is None:
        raise ValueError("update requires an installer-managed installation; use install for the first deployment")
    gateway = with_gateway or bool(state and state["gateway"])
    release_id = digest(source)
    check_config(paths)
    if state is None and exists(paths.command):
        raise ValueError(f"command already exists: {paths.command}; back it up or remove the old symlink before installing")
    if gateway and not (state and state["gateway"]) and exists(paths.unit):
        raise ValueError(f"unmanaged unit exists: {paths.unit}; back it up outside the .service filename before installing")
    if gateway:
        check_service()
    print(f"{'PLAN' if dry_run else 'Deploy'} {mode}: source {source} -> {paths.prefix}/releases/{release_id}")
    print(f"  Config: {paths.config} (root:root, 0644; preserve existing contents)")
    print(f"  Command: {paths.command}; gateway: {'installed, left stopped' if gateway else 'not installed'}")
    if dry_run:
        print("  Stage and validate code; switch current; retain earlier releases. No files changed.")
        return
    if gateway:
        ensure_gateway_user()
    with prepared_release(paths, source, gateway, release_id) as release:
        paths.config.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        os.chown(paths.config.parent, 0, 0)
        paths.config.parent.chmod(0o755)
        if not exists(paths.config):
            # Exclusive creation also protects against overwriting a concurrently created config.
            with paths.config.open("xb") as stream:
                stream.write((release / "telegram-notify.ini.example").read_bytes())
            print(f"Created example config; edit {paths.config} before sending notifications.")
        os.chown(paths.config, 0, 0)
        paths.config.chmod(0o644)
        if not paths.command.parent.exists():
            paths.command.parent.mkdir(mode=0o755, parents=True)
            paths.command.parent.chmod(0o755)
        if gateway:
            check_service()
        new_state = {
            "schema": 1, "active": release_id, "gateway": gateway,
            "releases": list(dict.fromkeys((state["releases"] if state else []) + [release_id])),
            "unit_digest": unit_digest(release / "telegram-gateway.service.example") if gateway else None,
        }
        with transaction(paths, gateway):
            atomic_link(paths.current, f"releases/{release_id}")
            atomic_link(paths.command, str(paths.command_target))
            if gateway:
                atomic_write(paths.unit, (release / "telegram-gateway.service.example").read_bytes())
                run("systemctl", "daemon-reload")
            atomic_write(paths.manifest, (json.dumps(new_state, indent=2) + "\n").encode())
            subprocess.run([sys.executable, "-B", str(paths.command), "--help"],
                           check=True, stdout=subprocess.DEVNULL)
    print("Installation complete. Earlier releases are retained; configuration contents are unchanged.")
    if gateway:
        print("Validate the configuration, then start/enable telegram-gateway.service explicitly.")


def uninstall(paths, dry_run=False):
    state = read_manifest(paths)
    if state is None:
        raise ValueError("no installer-managed installation found")
    if state["gateway"]:
        check_service()
        enabled = subprocess.run(["systemctl", "is-enabled", "telegram-gateway.service"],
                                 capture_output=True, text=True)
        if enabled.stdout.strip() not in ("disabled", "static"):
            raise ValueError("disable telegram-gateway.service before uninstalling")
    releases = [paths.prefix / "releases" / name for name in state["releases"]]
    for release in releases:
        if release.is_symlink() or digest(release) != release.name:
            raise ValueError(f"release was modified; preserve it before uninstalling: {release}")
        if any(p.name not in FILES and p.name != "__pycache__" for p in release.iterdir()):
            raise ValueError(f"unmanaged files in release: {release}; preserve them before uninstalling")
    print(f"{'PLAN' if dry_run else 'Remove'} managed commands, releases, and optional unit; preserve {paths.config}")
    if dry_run:
        return
    with transaction(paths, state["gateway"]):
        paths.command.unlink()
        paths.current.unlink()
        if state["gateway"]:
            paths.unit.unlink()
            run("systemctl", "daemon-reload")
        paths.manifest.unlink()
    # Delete only known installed files. Unknown files are never recursively removed.
    for release in releases:
        for name in FILES:
            (release / name).unlink()
        cache = release / "__pycache__"
        if cache.is_dir() and not cache.is_symlink():
            for item in cache.iterdir():
                if item.is_file() and item.suffix == ".pyc":
                    item.unlink()
            if not any(cache.iterdir()):
                cache.rmdir()
        if not any(release.iterdir()):
            release.rmdir()
    release_root = paths.prefix / "releases"
    if not any(release_root.iterdir()):
        release_root.rmdir()
    print("Uninstalled. Configuration, the gateway account, and system packages are preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install", "update", "uninstall"))
    parser.add_argument("--with-gateway", action="store_true", help="install the optional, stopped systemd gateway")
    parser.add_argument("--dry-run", action="store_true", help="preview changes without writing files")
    args = parser.parse_args()
    if args.mode == "uninstall" and args.with_gateway:
        parser.error("--with-gateway applies only to install/update")
    paths = Paths()
    try:
        if os.geteuid() != 0:
            raise ValueError("run the installer as root (sudo python3 install.py ...)")
        if paths.prefix.is_symlink():
            raise ValueError(f"installation directory must not be a symlink: {paths.prefix}")
        read_manifest(paths)
        if args.dry_run:
            if args.mode == "uninstall":
                uninstall(paths, dry_run=True)
            else:
                deploy(paths, SOURCE, args.mode, args.with_gateway, dry_run=True)
            return
        paths.prefix.mkdir(mode=0o755, parents=True, exist_ok=True)
        os.chown(paths.prefix, 0, 0)
        paths.prefix.chmod(0o755)
        lock_path = paths.prefix / "install.lock"
        if lock_path.is_symlink():
            raise ValueError("install.lock must not be a symlink")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.mode == "uninstall":
                uninstall(paths)
            else:
                deploy(paths, SOURCE, args.mode, args.with_gateway)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
