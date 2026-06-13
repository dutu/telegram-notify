# telegram-notify

Small local Telegram notification helper for Linux servers.

It sends Telegram messages from shell scripts, cron jobs, systemd services, backup jobs, UPS alerts, monitoring scripts, and other local automation.

No daemon, no webserver, no listening port.

## Features

- Simple local CLI
- Multiple destinations
- Telegram HTML formatting
- Telegram MarkdownV2 formatting
- Silent notifications
- Forum topic/thread support
- Web page preview control
- Inline URL buttons
- Single Python file
- No external Python dependencies

## Repository layout

```text
telegram-notify/
├── README.md
├── telegram-notify.py
└── telegram-notify.ini.example
```

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

Set permissions:

```bash
chown root:root /opt/telegram-notify/telegram-notify.py
chmod 755 /opt/telegram-notify/telegram-notify.py

chown root:root /opt/telegram-notify/telegram-notify.ini
chmod 600 /opt/telegram-notify/telegram-notify.ini
```

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

## Basic usage

```bash
telegram-notify infra "Backup completed"
```

```bash
telegram-notify personal "Server rebooted"
```

```bash
telegram-notify default "Test message"
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

## Silent notifications

```bash
telegram-notify infra --silent "Backup completed"
```

## Enable link previews

By default, link previews are disabled.

Enable them with:

```bash
telegram-notify infra --preview "https://example.com"
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
  telegram-notify infra --html "<b>nginx is down</b> on $(hostname)"
fi
```

## Example systemd service hook

```ini
[Service]
ExecStartPost=/usr/local/bin/telegram-notify infra "Service started"
ExecStopPost=/usr/local/bin/telegram-notify infra "Service stopped"
```

## Logs and debugging

This tool does not keep its own log file.

When used from systemd, errors appear in the journal of the calling service.

Manual test:

```bash
telegram-notify infra "Test from $(hostname)"
```

If it fails, run:

```bash
/opt/telegram-notify/telegram-notify.py infra "Test message"
```

## Security notes

The config file contains Telegram bot tokens.

Recommended permissions:

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

## License

MIT