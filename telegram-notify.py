#!/usr/bin/env python3

import argparse
import sys

from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram_notify_core import (
    DEFAULT_DESTINATION,
    PARSE_MODES,
    TelegramNotifyError,
    is_destination,
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
        "message",
        nargs="+",
        help="Message text to send, optionally prefixed with a destination name"
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

    if hasattr(parser, "parse_intermixed_args"):
        args = parser.parse_intermixed_args()
    else:
        args = parser.parse_args()

    if args.html and args.markdown:
        fail("use only one of --html or --markdown")

    return args


def resolve_destination_and_message(config, message_parts):
    if len(message_parts) > 1 and is_destination(config, message_parts[0]):
        return message_parts[0], " ".join(message_parts[1:]).strip()

    return DEFAULT_DESTINATION, " ".join(message_parts).strip()


def main():
    args = parse_args()

    parse_mode = None

    if args.html:
        parse_mode = PARSE_MODES["html"]

    if args.markdown:
        parse_mode = PARSE_MODES["markdown"]

    try:
        config = load_config()
        destination, text = resolve_destination_and_message(config, args.message)

        send_notification(
            config,
            destination,
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
