#!/usr/bin/env python3

import hmac
import json
import sys

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram_notify_core import (
    DEFAULT_DESTINATION,
    LEVEL_PREFIXES,
    PARSE_MODES,
    TelegramNotifyError,
    build_reply_markup,
    get_gateway_settings,
    is_destination,
    load_config,
    send_notification,
)


MAX_BODY_BYTES = 65536


class GatewayRequestError(Exception):
    pass


class TelegramGatewayHandler(BaseHTTPRequestHandler):
    server_version = "TelegramNotifyGateway/1.0"

    def do_GET(self):
        if self.path != "/health":
            self.send_json(404, {"status": "error", "error": "not found"})
            return

        self.send_json(200, {"status": "ok"})

    def do_POST(self):
        if self.path != "/notify":
            self.send_json(404, {"status": "error", "error": "not found"})
            return

        token = self.headers.get("X-Notify-Token", "")

        if not hmac.compare_digest(token, self.server.api_token):
            self.send_json(401, {"status": "error", "error": "unauthorized"})
            return

        try:
            payload = self.read_json_body()
            message = parse_notify_payload(payload)

            if not is_destination(self.server.config, message["destination"]):
                raise GatewayRequestError(f"profile not found: {message['destination']}")
        except GatewayRequestError as exc:
            self.send_json(400, {"status": "error", "error": str(exc)})
            return

        try:
            send_notification(self.server.config, **message)
        except TelegramNotifyError as exc:
            self.send_json(502, {"status": "error", "error": str(exc)})
            return

        self.send_json(
            200,
            {
                "status": "ok",
                "profile": message["destination"],
            },
        )

    def read_json_body(self):
        content_length = self.headers.get("Content-Length")

        if not content_length:
            raise GatewayRequestError("missing Content-Length")

        try:
            content_length = int(content_length)
        except ValueError as exc:
            raise GatewayRequestError("invalid Content-Length") from exc

        if content_length < 1:
            raise GatewayRequestError("request body cannot be empty")

        if content_length > MAX_BODY_BYTES:
            raise GatewayRequestError("request body is too large")

        raw_body = self.rfile.read(content_length)

        try:
            decoded_body = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GatewayRequestError("request body must be utf-8 json") from exc

        try:
            payload = json.loads(decoded_body)
        except json.JSONDecodeError as exc:
            raise GatewayRequestError("request body must be valid json") from exc

        if not isinstance(payload, dict):
            raise GatewayRequestError("request body must be a json object")

        return payload

    def send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_notify_payload(payload):
    destination = payload.get("profile", payload.get("destination", DEFAULT_DESTINATION))
    text = payload.get("text", payload.get("message"))
    level = payload.get("level")
    html = get_bool(payload, "html", False)
    markdown = get_bool(payload, "markdown", False)
    silent = get_bool(payload, "silent", False)
    preview = get_bool(payload, "preview", False)
    thread_id = payload.get("thread_id")
    buttons = payload.get("buttons", payload.get("button", []))

    if not isinstance(destination, str) or not destination.strip():
        raise GatewayRequestError("profile must be a non-empty string")

    if not isinstance(text, str) or not text.strip():
        raise GatewayRequestError("text must be a non-empty string")

    if level is not None and level not in LEVEL_PREFIXES:
        levels = ", ".join(LEVEL_PREFIXES)
        raise GatewayRequestError(f"level must be one of: {levels}")

    if html and markdown:
        raise GatewayRequestError("use only one of html or markdown")

    if thread_id is not None:
        if not isinstance(thread_id, int):
            raise GatewayRequestError("thread_id must be an integer")

    if buttons is None:
        buttons = []
    elif isinstance(buttons, (str, dict)):
        buttons = [buttons]
    elif not isinstance(buttons, list):
        raise GatewayRequestError("buttons must be a list, string, or object")

    try:
        build_reply_markup(buttons)
    except TelegramNotifyError as exc:
        raise GatewayRequestError(str(exc)) from exc

    parse_mode = None

    if html:
        parse_mode = PARSE_MODES["html"]

    if markdown:
        parse_mode = PARSE_MODES["markdown"]

    return {
        "destination": destination.strip(),
        "text": text.strip(),
        "level": level,
        "parse_mode": parse_mode,
        "silent": silent,
        "preview": preview,
        "thread_id": thread_id,
        "buttons": buttons,
    }


def get_bool(payload, key, default):
    value = payload.get(key, default)

    if not isinstance(value, bool):
        raise GatewayRequestError(f"{key} must be a boolean")

    return value


def main():
    try:
        config = load_config()
        settings = get_gateway_settings(config)
    except TelegramNotifyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    server = ThreadingHTTPServer(
        (settings["listen_host"], settings["listen_port"]),
        TelegramGatewayHandler,
    )
    server.config = config
    server.api_token = settings["api_token"]

    print(
        f"telegram gateway listening on http://{settings['listen_host']}:{settings['listen_port']}",
        flush=True,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
