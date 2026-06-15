# telegram-notify

Small Telegram notification toolkit for Linux servers.

It provides two entry points that share the same config and Telegram delivery code:

- `telegram-notify.py`: local CLI for shell scripts, cron jobs, systemd hooks, backup jobs, UPS alerts, and monitoring scripts.
- `telegram-gateway.py`: optional local HTTP-to-Telegram gateway for tools that can only send webhooks.

The CLI has no daemon, no webserver, and no listening port. The gateway is a separate optional service and should only be enabled when HTTP access is needed.

## Features

- Shared Telegram profile configuration
- Multiple Telegram bot destinations
- Telegram HTML formatting
- Telegram MarkdownV2 formatting
- Notification levels
- Silent notifications
- Forum topic/thread support
- Web page preview control
- Inline URL buttons
- Optional local HTTP API
- Basic HTTP authentication via shared secret
- systemd service example for the gateway
- Python standard library only

## Repository layout

```text
telegram-notify/
├── README.md
├── README_CLI.md
├── README_GATEWAY.md
├── telegram_notify_core.py
├── telegram-notify.py
├── telegram-gateway.py
├── telegram-gateway.service.example
└── telegram-notify.ini.example
```

## Which component should I use?

Use the CLI when the sender is local and can execute a command:

```bash
telegram-notify --level error "Backup failed"
```

Use the gateway only when a tool needs HTTP access:

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
    "text": "Backup failed"
  }'
```

## Documentation

- CLI setup and usage: [README_CLI.md](README_CLI.md)
- HTTP gateway setup and usage: [README_GATEWAY.md](README_GATEWAY.md)

## Shared configuration

Both entry points use the same config file:

```bash
/opt/telegram-notify/telegram-notify.ini
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

The `[gateway]` section is only required when running `telegram-gateway.py`.

## Updates

Keep the repository in a stable application directory, for example:

```bash
/opt/telegram-notify
```

Update the code in place:

```bash
cd /opt/telegram-notify
git status --short
git pull --ff-only
```

Your real config file is not tracked by Git:

```bash
/opt/telegram-notify/telegram-notify.ini
```

Do not rerun the initial config copy during updates:

```bash
cp telegram-notify.ini.example telegram-notify.ini
```

That command is only for first-time setup and may overwrite your real config.

Also avoid destructive cleanup commands such as:

```bash
git clean -fdx
```

That can delete ignored files, including `telegram-notify.ini`.

If you use the CLI symlink, no reinstall is usually needed after `git pull`.

If you use the gateway service, restart it after updating:

```bash
systemctl restart telegram-gateway.service
```

## Security notes

The config file contains Telegram bot tokens and, optionally, the gateway API token.

For CLI-only usage, root-only permissions are usually appropriate:

```bash
chown root:root /opt/telegram-notify/telegram-notify.ini
chmod 600 /opt/telegram-notify/telegram-notify.ini
```

For gateway usage with the dedicated `telegram-gateway` user, the service user must be able to read the same config:

```bash
chown root:telegram-gateway /opt/telegram-notify/telegram-notify.ini
chmod 640 /opt/telegram-notify/telegram-notify.ini
```

Keep the gateway bound to `127.0.0.1` unless you deliberately expose it behind proper firewalling and TLS.

## License

MIT
