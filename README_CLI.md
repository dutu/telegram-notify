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

## Installation

Clone the repository:

```bash
cd /opt

git clone https://github.com/YOUR_USERNAME/telegram-notify.git

cd /opt/telegram-notify
```

Copy the example config:

```bash
cp telegram-notify.ini.example telegram-notify.ini
```

Edit the config:

```bash
nano telegram-notify.ini
```

Set config permissions:

```bash
chown root:root /opt/telegram-notify/telegram-notify.ini
chmod 600 /opt/telegram-notify/telegram-notify.ini
```

The executable bit for `telegram-notify.py` is tracked by Git, so you do not need
to run `chmod` again after pulls.

Create a symlink:

```bash
ln -s /opt/telegram-notify/telegram-notify.py /usr/local/bin/telegram-notify
```

Verify:

```bash
telegram-notify --help
```

## Configuration

Create:

```bash
/opt/telegram-notify/telegram-notify.ini
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

Available levels:

- `info` prepends `▫️`
- `warning` prepends `🔸`
- `error` prepends `🔺`

Examples:

```bash
telegram-notify --level info "Backup completed"
```

```bash
telegram-notify infra --level warning "Disk usage is above 80%"
```

```bash
telegram-notify infra --level error "Backup failed"
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
/opt/telegram-notify/telegram-notify.py "Test message"
```

## Security notes

The config file contains Telegram bot tokens.

Recommended CLI-only permissions:

```bash
chmod 600 /opt/telegram-notify/telegram-notify.ini
chown root:root /opt/telegram-notify/telegram-notify.ini
```

Do not commit the real config file to Git.

Only commit:

```text
telegram-notify.ini.example
```

Add this to `.gitignore`:

```text
telegram-notify.ini
```
