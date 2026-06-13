#!/usr/bin/env python3

import argparse
import sys

from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram_notify_core import (
    PARSE_MODES,
    TelegramNotifyError,
    load_config,
    send_notification,
)


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send Telegram notifications from local scripts."
    )

    parser.add_argument(
        "destination",
        help="Destination name from telegram-notify.ini, for example: infra"
    )

    parser.add_argument(
        "message",
        nargs="+",
        help="Message text to send"
    )

    parser.add_argument(
        "--level",
        choices=["info", "warning", "error"],
        help="Prepend a status symbol based on severity level"
    )

    parser.add_argument(
        "--html",
        action="store_true",
        help="Use Telegram HTML parse mode"
    )

    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Use Telegram MarkdownV2 parse mode"
    )

    parser.add_argument(
        "--silent",
        action="store_true",
        help="Send notification silently"
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Enable web page preview"
    )

    parser.add_argument(
        "--thread-id",
        type=int,
        help="Telegram forum topic/thread ID"
    )

    parser.add_argument(
        "--button",
        action="append",
        default=[],
        help="Add inline button using TEXT=URL format. Can be used multiple times."
    )

    args = parser.parse_args()

    if args.html and args.markdown:
        fail("use only one of --html or --markdown")

    return args


def main():
    args = parse_args()

    text = " ".join(args.message).strip()

    parse_mode = None

    if args.html:
        parse_mode = PARSE_MODES["html"]

    if args.markdown:
        parse_mode = PARSE_MODES["markdown"]

    try:
        config = load_config()

        send_notification(
            config,
            args.destination,
            text,
            level=args.level,
            parse_mode=parse_mode,
            silent=args.silent,
            preview=args.preview,
            thread_id=args.thread_id,
            buttons=args.button,
        )
    except TelegramNotifyError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
