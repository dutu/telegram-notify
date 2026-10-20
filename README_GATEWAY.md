# telegram-notify HTTP gateway

Optional HTTP-to-Telegram gateway for tools that can send webhooks but cannot execute the local CLI.

The gateway uses the same `telegram-notify.ini` file and the same shared delivery code as `telegram-notify.py`.

## Features

- Local HTTP API
- Multiple Telegram bot profiles
- Profile-based routing
- Shared config with the CLI
- Notification levels
- Telegram HTML formatting
- Telegram MarkdownV2 formatting
- Silent notifications
- Forum topic/thread support
- Web page preview control
- Inline URL buttons
- Basic authentication via shared secret
- Dedicated system user
- systemd integration
- Python standard library only

## Installation

Follow the [installation guide](README.md#installation), using
`--with-gateway`. The installer creates the dedicated `telegram-gateway` account
and installs the systemd unit, leaving the service stopped. This account's
standard service group is used only by systemd; local CLI users need no group
membership.

For existing manual installations, first follow the
[migration procedure](README.md#upgrade-an-existing-manual-installation).
For later updates, follow [updating](README.md#updating).

## Configuration

Edit the shared configuration:

```bash
sudo nano /etc/telegram-notify/telegram-notify.ini
```

The `[gateway]` section defines the shared API secret and listening address:

```ini
[gateway]
api_token = CHANGE_ME_TO_A_LONG_RANDOM_SECRET
listen_host = 127.0.0.1
listen_port = 8484

[default]
bot_token = 1234567890:AAA_DEFAULT_TOKEN
chat_id = 188488206
```

Replace the example credentials. Use a long random gateway secret, for example
one generated with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

The file is owned by `root:root` with mode `0644`; the gateway and all local CLI
users can read it. Every local user can also read the bot and API tokens.
The gateway reads configuration at startup; restart it after configuration edits.

## Start and enable

Start only when HTTP access is needed:

```bash
sudo systemctl start telegram-gateway.service
systemctl status telegram-gateway.service
curl --fail --silent http://127.0.0.1:8484/health
```

Enable it to start after reboot:

```bash
sudo systemctl enable telegram-gateway.service
```

Stop and disable it when no longer needed:

```bash
sudo systemctl disable --now telegram-gateway.service
```

## API

Health check:

```bash
curl -s http://127.0.0.1:8484/health
```

Send notification:

```bash
curl \
  -s \
  -X POST \
  http://127.0.0.1:8484/notify \
  -H "Content-Type: application/json" \
  -H "X-Notify-Token: CHANGE_ME_TO_A_LONG_RANDOM_SECRET" \
  -d '{
    "profile": "infra",
    "text": "UPS switched to battery"
  }'
```

Expected response:

```json
{
  "status": "ok",
  "profile": "infra"
}
```

## Request fields

Required fields:

- `text`: message text to send

`<br>`, `<br/>`, and `<br />` in message text are normalized to newline
characters before sending.

Optional fields:

- `profile`: destination from `telegram-notify.ini`; defaults to `default`
- `destination`: alias for `profile`
- `level`: one of `debug`, `info`, `warning`, `error`, or `crit`; invalid levels fall back to `info`
- `html`: boolean; enables Telegram HTML parse mode
- `markdown`: boolean; enables Telegram MarkdownV2 parse mode
- `silent`: boolean; sends notification silently
- `preview`: boolean; enables web page preview
- `thread_id`: integer Telegram forum topic/thread ID
- `buttons`: list of inline buttons

Buttons can use either string format:

```json
{
  "buttons": [
    "Open Kuma=https://kuma.example.com"
  ]
}
```

Or object format:

```json
{
  "buttons": [
    {
      "text": "Open Kuma",
      "url": "https://kuma.example.com"
    }
  ]
}
```

## Combined example

```bash
curl \
  -s \
  -X POST \
  http://127.0.0.1:8484/notify \
  -H "Content-Type: application/json" \
  -H "X-Notify-Token: CHANGE_ME_TO_A_LONG_RANDOM_SECRET" \
  -d '{
    "profile": "infra",
    "level": "error",
    "html": true,
    "silent": true,
    "thread_id": 123,
    "buttons": [
      {
        "text": "Open Kuma",
        "url": "https://kuma.example.com"
      }
    ],
    "text": "<b>Kuma alert</b>: home-mt is down"
  }'
```

## Logs

Follow logs:

```bash
journalctl -u telegram-gateway.service -f
```

Restart:

```bash
sudo systemctl restart telegram-gateway.service
```

## Security notes

Keep `listen_host = 127.0.0.1` unless you deliberately need network access.

If exposing the gateway beyond localhost:

- Use a long random `api_token`
- Restrict access with a firewall
- Prefer a reverse proxy with TLS
- Avoid exposing it directly to the public internet
