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

## Dependencies

```bash
python3 --version

apt update
apt install -y python3
```

## Create service user

```bash
useradd \
  --system \
  --no-create-home \
  --shell /usr/sbin/nologin \
  telegram-gateway
```

Verify:

```bash
id telegram-gateway
```

## Install application

Clone the repository if it is not already installed:

```bash
cd /opt

git clone https://github.com/YOUR_USERNAME/telegram-notify.git

cd /opt/telegram-notify
```

The executable bit for `telegram-gateway.py` is tracked by Git, so you do not
need to run `chmod` again after pulls.

## Updates

Use one stable clone directory, for example:

```bash
/opt/telegram-notify
```

Update the installed code in place:

```bash
cd /opt/telegram-notify
git status --short
git pull --ff-only
```

Do not copy the example config again during updates:

```bash
cp /opt/telegram-notify/telegram-notify.ini.example /opt/telegram-notify/telegram-notify.ini
```

That command is only for first-time setup and may overwrite your real config.

Your real config file is ignored by Git and should remain here:

```bash
/opt/telegram-notify/telegram-notify.ini
```

Avoid destructive cleanup commands such as:

```bash
git clean -fdx
```

That can delete ignored files, including `telegram-notify.ini`.

Restart the gateway after updating code:

```bash
systemctl restart telegram-gateway.service
```

If the service example changed, review the difference before replacing the
installed service:

```bash
diff -u /etc/systemd/system/telegram-gateway.service /opt/telegram-notify/telegram-gateway.service.example
```

## Configure

Create the shared config file:

```bash
cp /opt/telegram-notify/telegram-notify.ini.example /opt/telegram-notify/telegram-notify.ini
nano /opt/telegram-notify/telegram-notify.ini
```

Example:

```ini
[gateway]
api_token = CHANGE_ME_TO_A_LONG_RANDOM_SECRET
listen_host = 127.0.0.1
listen_port = 8484

[default]
bot_token = 1234567890:AAA_DEFAULT_TOKEN
chat_id = 188488206

[infra]
bot_token = 1234567890:BBB_INFRA_TOKEN
chat_id = 222222222

[personal]
bot_token = 1234567890:CCC_PERSONAL_TOKEN
chat_id = 333333333
```

Lock down permissions so the gateway user can read the config:

```bash
chown root:telegram-gateway /opt/telegram-notify/telegram-notify.ini
chmod 640 /opt/telegram-notify/telegram-notify.ini
```

## systemd service

Install the service file:

```bash
cp /opt/telegram-notify/telegram-gateway.service.example /etc/systemd/system/telegram-gateway.service
systemctl daemon-reload
```

Start only when HTTP access is needed:

```bash
systemctl start telegram-gateway.service
```

Stop when no longer needed:

```bash
systemctl stop telegram-gateway.service
```

Check status and logs:

```bash
systemctl status telegram-gateway.service
journalctl -u telegram-gateway.service -n 50 --no-pager
```

Enable it only if it should start after reboot:

```bash
systemctl enable --now telegram-gateway.service
```

Disable it again:

```bash
systemctl disable --now telegram-gateway.service
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
systemctl restart telegram-gateway.service
```

## Security notes

Keep `listen_host = 127.0.0.1` unless you deliberately need network access.

If exposing the gateway beyond localhost:

- Use a long random `api_token`
- Restrict access with a firewall
- Prefer a reverse proxy with TLS
- Avoid exposing it directly to the public internet
