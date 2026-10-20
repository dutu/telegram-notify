# telegram-notify CLI

Local Telegram notification CLI for Linux servers.

It sends Telegram messages from shell scripts, cron jobs, systemd services, backup jobs, UPS alerts, monitoring scripts, and other local automation.

No daemon, no webserver, no listening port.

## Features

- Simple local CLI
- Multiple destinations
- Telegram HTML formatting
- Telegram MarkdownV2 formatting
- Notification levels
- Silent notifications
- Forum topic/thread support
- Web page preview control
- Inline URL buttons
- Python standard library only

## Installation and updates

Follow the [installation guide](README.md#installation) for the system-wide CLI.
Clone the source into your home directory or another working directory outside
`/opt`; the installer copies application files into `/opt/telegram-notify`.

For an existing manual installation, first follow the
[migration procedure](README.md#upgrade-an-existing-manual-installation).
For later updates, follow [updating](README.md#updating).

Verify the installed command:

```bash
telegram-notify --help
```

Installation and configuration require root. Any local user can run the CLI;
there is no per-user configuration or notification group.

## Configuration

Edit the shared configuration created by the installer:

```bash
sudo nano /etc/telegram-notify/telegram-notify.ini
```

Example:

```ini
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

Each section is a destination.

A destination defines:

- `bot_token`
- `chat_id`

If you also use the gateway, the same file may include a `[gateway]` section. The CLI ignores it.

## Basic usage

Send to the `[default]` destination:

```bash
telegram-notify "Backup completed"
```

Use a specific destination by putting the destination name before the message:

```bash
telegram-notify infra "Backup completed"
```

```bash
telegram-notify personal "Server rebooted"
```

```bash
telegram-notify "Test message"
```

Destination detection is config-based. If the first argument matches a configured destination and there is more message text after it, it is treated as the destination. Otherwise, the whole message is sent to `[default]`.

## Notification levels

Use `--level` to prepend a status symbol to the message.
Invalid levels fall back to `info` so the notification is still sent.

Available levels:

- `debug` prepends `🔍`
- `info` prepends `▫️`
- `warning` prepends `🔸`
- `error` prepends `🔺`
- `crit` prepends `🛑`

Examples:

```bash
telegram-notify --level info "Backup completed"
```

```bash
telegram-notify --level debug "Debug details"
```

```bash
telegram-notify infra --level warning "Disk usage is above 80%"
```

```bash
telegram-notify infra --level error "Backup failed"
```

```bash
telegram-notify infra --level crit "Database is unreachable"
```

## HTML messages

```bash
telegram-notify infra --html "<b>Backup failed</b> on NAS"
```

Telegram supports a limited HTML subset, including:

```html
<b>bold</b>
<i>italic</i>
<code>inline code</code>
<pre>preformatted</pre>
<a href="https://example.com">link</a>
```

`<br>`, `<br/>`, and `<br />` in message text are normalized to newline
characters before sending.

## MarkdownV2 messages

```bash
telegram-notify infra --markdown "*Backup completed* on NAS"
```

MarkdownV2 requires Telegram-specific escaping for reserved characters.

## Silent notifications

```bash
telegram-notify --silent "Backup completed"
```

## Enable link previews

By default, link previews are disabled.

Enable them with:

```bash
telegram-notify --preview "https://example.com"
```

## Forum topic/thread

For Telegram forum groups, send to a specific topic:

```bash
telegram-notify infra --thread-id 123 "UPS switched to battery"
```

## Inline button

```bash
telegram-notify infra \
  --button "Open Kuma=https://kuma.example.com" \
  "Kuma alert"
```

Multiple buttons:

```bash
telegram-notify infra \
  --button "Open Kuma=https://kuma.example.com" \
  --button "Open Proxmox=https://proxmox.example.com" \
  "Infrastructure alert"
```

## Combined example

```bash
telegram-notify infra \
  --level error \
  --html \
  --silent \
  --thread-id 123 \
  --button "Open Kuma=https://kuma.example.com" \
  "<b>Kuma alert</b>: home-mt is down"
```

## Example from a shell script

```bash
#!/bin/bash

set -e

if ! systemctl is-active --quiet nginx; then
  telegram-notify infra --level error --html "<b>nginx is down</b> on $(hostname)"
fi
```

## Example systemd service hook

```ini
[Service]
ExecStartPost=/usr/local/bin/telegram-notify infra --level info "Service started"
ExecStopPost=/usr/local/bin/telegram-notify infra --level warning "Service stopped"
```

## Logs and debugging

This tool does not keep its own log file.

When used from systemd, errors appear in the journal of the calling service.

Manual test:

```bash
telegram-notify "Test from $(hostname)"
```

If it fails, run:

```bash
/opt/telegram-notify/current/telegram-notify.py "Test message"
```

## Security notes

The shared configuration is owned by `root:root`, with mode `0644`, in a `0755`
directory. All local users can send notifications and read the bot tokens. Only
root can edit the configuration or installed code.

Keep real configuration out of the source checkout and Git. Commit only
`telegram-notify.ini.example`.
