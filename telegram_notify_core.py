import configparser
import json
import re

from pathlib import Path
from urllib import error, parse, request


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "telegram-notify.ini"
DEFAULT_DESTINATION = "default"

LEVEL_PREFIXES = {
    "info": "▫️",
    "warning": "🔸",
    "error": "🔺",
}

PARSE_MODES = {
    "html": "HTML",
    "markdown": "MarkdownV2",
}

BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


class TelegramNotifyError(Exception):
    pass


def load_config(config_file=CONFIG_FILE):
    path = Path(config_file)

    if not path.exists():
        raise TelegramNotifyError(f"config file not found: {path}")

    config = configparser.ConfigParser()
    config.read(path)

    if DEFAULT_DESTINATION not in config:
        raise TelegramNotifyError(f"missing [{DEFAULT_DESTINATION}] destination in config")

    return config


def get_destination(config, name):
    if name not in config:
        raise TelegramNotifyError(f"destination not found: {name}")

    section = config[name]

    bot_token = section.get("bot_token", "").strip()
    chat_id = section.get("chat_id", "").strip()

    if not bot_token or not chat_id:
        raise TelegramNotifyError(f"destination '{name}' is missing bot_token or chat_id")

    return bot_token, chat_id


def is_destination(config, name):
    if name not in config:
        return False

    section = config[name]

    return bool(
        section.get("bot_token", "").strip()
        and section.get("chat_id", "").strip()
    )


def get_gateway_settings(config):
    if "gateway" not in config:
        raise TelegramNotifyError("missing [gateway] section in config")

    section = config["gateway"]

    api_token = section.get("api_token", "").strip()
    listen_host = section.get("listen_host", "127.0.0.1").strip()
    listen_port = section.get("listen_port", "8484").strip()

    if not api_token:
        raise TelegramNotifyError("[gateway] api_token is required")

    if not listen_host:
        raise TelegramNotifyError("[gateway] listen_host cannot be empty")

    try:
        listen_port = int(listen_port)
    except ValueError as exc:
        raise TelegramNotifyError("[gateway] listen_port must be an integer") from exc

    if listen_port < 1 or listen_port > 65535:
        raise TelegramNotifyError("[gateway] listen_port must be between 1 and 65535")

    return {
        "api_token": api_token,
        "listen_host": listen_host,
        "listen_port": listen_port,
    }


def format_message(text, level=None):
    if not level:
        return text

    if level not in LEVEL_PREFIXES:
        levels = ", ".join(LEVEL_PREFIXES)
        raise TelegramNotifyError(f"invalid level '{level}', expected one of: {levels}")

    return f"{LEVEL_PREFIXES[level]} {text}"


def normalize_message_text(text):
    return BR_TAG_RE.sub("\n", str(text)).strip()


def build_reply_markup(buttons):
    if not buttons:
        return None

    inline_keyboard = []

    for button in buttons:
        text, url = parse_button(button)

        inline_keyboard.append(
            [
                {
                    "text": text,
                    "url": url,
                }
            ]
        )

    return {
        "inline_keyboard": inline_keyboard,
    }


def parse_button(button):
    if isinstance(button, str):
        if "=" not in button:
            raise TelegramNotifyError("button must use TEXT=URL format")

        text, url = button.split("=", 1)
    elif isinstance(button, dict):
        text = button.get("text", "")
        url = button.get("url", "")
    else:
        raise TelegramNotifyError("button must be a TEXT=URL string or an object with text and url")

    text = str(text).strip()
    url = str(url).strip()

    if not text or not url:
        raise TelegramNotifyError("button requires non-empty text and url")

    return text, url


def send_notification(
    config,
    destination,
    text,
    *,
    level=None,
    parse_mode=None,
    silent=False,
    preview=False,
    thread_id=None,
    buttons=None,
    timeout=10,
):
    bot_token, chat_id = get_destination(config, destination)

    text = normalize_message_text(text)

    if not text:
        raise TelegramNotifyError("message cannot be empty")

    text = format_message(text, level)

    return send_telegram_message(
        bot_token,
        chat_id,
        text,
        parse_mode=parse_mode,
        silent=silent,
        preview=preview,
        thread_id=thread_id,
        buttons=buttons,
        timeout=timeout,
    )


def send_telegram_message(
    bot_token,
    chat_id,
    text,
    *,
    parse_mode=None,
    silent=False,
    preview=False,
    thread_id=None,
    buttons=None,
    timeout=10,
):
    if parse_mode and parse_mode not in PARSE_MODES.values():
        modes = ", ".join(PARSE_MODES.values())
        raise TelegramNotifyError(f"invalid parse mode '{parse_mode}', expected one of: {modes}")

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "false" if preview else "true",
        "disable_notification": "true" if silent else "false",
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    if thread_id is not None:
        payload["message_thread_id"] = str(thread_id)

    reply_markup = build_reply_markup(buttons)

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    data = parse.urlencode(payload).encode("utf-8")

    try:
        req = request.Request(
            telegram_url,
            data=data,
            method="POST",
        )

        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TelegramNotifyError(f"telegram api http error {exc.code}: {body}") from exc
    except Exception as exc:
        raise TelegramNotifyError(str(exc)) from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TelegramNotifyError(f"telegram api returned invalid json: {body}") from exc

    if not result.get("ok"):
        raise TelegramNotifyError(f"telegram api error: {body}")

    return result
