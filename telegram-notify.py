#!/usr/bin/env python3

import argparse
import configparser
import json
import sys

from pathlib import Path
from urllib import parse, request


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "telegram-notify.ini"


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def load_config():
    if not CONFIG_FILE.exists():
        fail(f"config file not found: {CONFIG_FILE}")

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if "default" not in config:
        fail("missing [default] destination in config")

    return config


def get_destination(config, name):
    if name not in config:
        fail(f"destination not found: {name}")

    section = config[name]

    bot_token = section.get("bot_token", "").strip()
    chat_id = section.get("chat_id", "").strip()

    if not bot_token or not chat_id:
        fail(f"destination '{name}' is missing bot_token or chat_id")

    return bot_token, chat_id


def build_reply_markup(buttons):
    if not buttons:
        return None

    inline_keyboard = []

    for button in buttons:
        if "=" not in button:
            fail("--button must use TEXT=URL format")

        text, url = button.split("=", 1)

        text = text.strip()
        url = url.strip()

        if not text or not url:
            fail("--button requires non-empty TEXT and URL")

        inline_keyboard.append(
            [
                {
                    "text": text,
                    "url": url
                }
            ]
        )

    return {
        "inline_keyboard": inline_keyboard
    }


def send_message(bot_token, chat_id, text, args):
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "false" if args.preview else "true",
        "disable_notification": "true" if args.silent else "false"
    }

    if args.html:
        payload["parse_mode"] = "HTML"

    if args.markdown:
        payload["parse_mode"] = "MarkdownV2"

    if args.thread_id is not None:
        payload["message_thread_id"] = str(args.thread_id)

    reply_markup = build_reply_markup(args.button)

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    data = parse.urlencode(payload).encode("utf-8")

    try:
        req = request.Request(
            telegram_url,
            data=data,
            method="POST"
        )

        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")

        result = json.loads(body)

        if not result.get("ok"):
            fail(f"telegram api error: {body}")

    except Exception as exc:
        fail(str(exc))


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

    config = load_config()
    bot_token, chat_id = get_destination(config, args.destination)

    text = " ".join(args.message).strip()

    if not text:
        fail("message cannot be empty")

    send_message(bot_token, chat_id, text, args)


if __name__ == "__main__":
    main()