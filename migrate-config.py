#!/usr/bin/env python3
"""Move an existing INI to /etc/telegram-notify without overwriting files."""

import argparse
import os
from pathlib import Path
import sys
import tempfile

from telegram_notify_core import CONFIG_FILE, TelegramNotifyError, load_config


LEGACY_CONFIG = Path("/opt/telegram-notify/telegram-notify.ini")


def migrate(source, destination=CONFIG_FILE, dry_run=False):
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("source, destination, and destination directory must not be symlinks")
    if source.absolute() == destination.absolute():
        raise ValueError("source and destination must be different paths")
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}; no files changed")
    if not source.is_file():
        raise ValueError(f"source config not found: {source}")
    # Validate structure without sending a notification or printing any credentials.
    load_config(source)
    data = source.read_bytes()
    print(f"{'PLAN' if dry_run else 'Move'} {source} -> {destination} (root:root, 0644)")
    if dry_run:
        print("The old file is removed only after the new copy has been verified. No files changed.")
        return
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    os.chown(destination.parent, 0, 0)
    destination.parent.chmod(0o755)
    fd, name = tempfile.mkstemp(prefix=".migrate-", dir=destination.parent)
    temporary = Path(name)
    published = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        load_config(temporary)
        os.chown(temporary, 0, 0)
        temporary.chmod(0o644)
        # A hard link publishes a complete file and fails if the destination exists.
        os.link(temporary, destination)
        published = True
        if destination.read_bytes() != data or source.read_bytes() != data:
            raise ValueError("configuration changed during migration; original file preserved")
        source.unlink()
    except BaseException:
        # Preserve the published copy if unlink succeeded before an interruption.
        if published and source.is_file():
            destination.unlink()
        raise
    finally:
        temporary.unlink(missing_ok=True)
    print("Configuration moved. Both entry points now use the file under /etc/telegram-notify.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=LEGACY_CONFIG,
                        help=f"existing INI (default: {LEGACY_CONFIG})")
    parser.add_argument("--dry-run", action="store_true", help="validate and preview without changing files")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError("run migration as root (sudo python3 migrate-config.py ...)")
        migrate(args.source, dry_run=args.dry_run)
    except (OSError, ValueError, TelegramNotifyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
