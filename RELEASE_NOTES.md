# telegram-notify v0.1.0

First release of the Telegram notification toolkit for Linux servers, using only
the Python standard library.

## Features

- Local CLI for shell scripts, cron jobs, systemd hooks, and monitoring, with an
  optional destination argument and support for multiple configured destinations.
- Optional HTTP gateway with shared-secret authentication, `/notify` and `/health`
  endpoints, and a systemd service running under a dedicated account.
- HTML and MarkdownV2 formatting, notification levels, silent messages, forum
  topics, link preview control, and inline URL buttons.
- Notification levels: `debug`, `info`, `notice`, `warning`, `error`, and `crit`.
  Invalid levels fall back to `info`; HTML `<br>` tags become newlines.
- System-wide installer with install, update, uninstall, and dry-run commands.
  Updates preserve configuration; gateway installation is optional and does not
  automatically start or enable the service.
- Configuration migration tool for existing manual installations.
- `telegram-notify --version` to display the installed version without loading
  configuration or sending a message.

## Requirements and upgrading

- Linux with Python 3.8 or newer at `/usr/bin/python3`; installation requires root.
  The optional gateway also requires systemd, `systemd-analyze`, and `useradd`.
- Shared configuration lives at `/etc/telegram-notify/telegram-notify.ini`.
  All local users can read its bot and gateway tokens and send notifications.
- Existing manual installations must follow the
  [migration procedure](README.md#upgrade-an-existing-manual-installation) before
  using the new installer. Back up configuration and pause notification-producing
  automation during migration.

See the [installation guide](README.md#installation),
[CLI documentation](README_CLI.md), and
[gateway documentation](README_GATEWAY.md) for setup and usage.
