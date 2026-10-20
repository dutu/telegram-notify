# telegram-notify

Small Telegram notification toolkit for Linux servers:

- `telegram-notify`: local CLI for shell scripts, cron jobs, systemd hooks, backups,
  UPS alerts, and monitoring scripts. It needs no daemon or listening port.
- Optional HTTP gateway for tools that send webhooks.

Both use the same Telegram delivery code and configuration. Features include
multiple destinations, HTML and MarkdownV2, notification levels, silent messages,
forum topics, link previews, and inline URL buttons. Python standard library only.

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration and access](#configuration-and-access)
- [Upgrade an existing manual installation](#upgrade-an-existing-manual-installation)
- [Updating](#updating)
- [Uninstalling](#uninstalling)
- [Development checks](#development-checks)
- [License](#license)

## Requirements

- Linux with Python 3.8 or newer at `/usr/bin/python3`.
- Root access for installation, updates, migration, and configuration.
- The optional gateway also requires systemd, `systemd-analyze`, and `useradd`.
- Outbound HTTPS access to Telegram when sending notifications.

Install Python using your distribution's package manager if necessary. The
installer does not install system packages or download source code.

## Installation

1. Clone into a working directory, for example your home directory:

```bash
git clone https://github.com/dutu/telegram-notify.git "$HOME/telegram-notify"
cd "$HOME/telegram-notify"
```

2. Preview and install the CLI:

```bash
sudo python3 install.py install --dry-run
sudo python3 install.py install
telegram-notify --help
```

   To include the optional gateway, use these commands instead:

```bash
sudo python3 install.py install --with-gateway --dry-run
sudo python3 install.py install --with-gateway
```

   The gateway is installed but is never started or enabled automatically.
   Adding `--with-gateway` later installs it alongside an existing CLI deployment.
   Later installs/updates preserve the gateway selection even without the flag.

3. Edit the shared configuration before sending notifications:

```bash
sudo nano /etc/telegram-notify/telegram-notify.ini
```

   Replace the example bot tokens and chat IDs. The installer creates the file
   only when absent and preserves existing contents during installation/updates.

4. Send a test message as your normal user:

```bash
telegram-notify "Test notification"
```

   Successful delivery exits with status zero and no output. CLI usage and
   formatting examples are in [README_CLI.md](README_CLI.md).

5. If installed and configured, start the optional gateway:

```bash
sudo systemctl start telegram-gateway.service
curl --fail --silent http://127.0.0.1:8484/health
sudo systemctl enable telegram-gateway.service
```

   The health response is `{"status": "ok"}`. Enabling is optional.
   See [README_GATEWAY.md](README_GATEWAY.md) for API usage and operation.

The source checkout is separate from the installation. It can be moved or removed
after installation. Application files are copied into a release directory named
by a source content digest; `current` selects the active release.

| Purpose | Location |
|---|---|
| Installed application | `/opt/telegram-notify/releases/<source-digest>/` |
| Active release link | `/opt/telegram-notify/current` |
| Installer metadata | `/opt/telegram-notify/installation.json` |
| CLI | `/usr/local/bin/telegram-notify` |
| Shared configuration | `/etc/telegram-notify/telegram-notify.ini` |
| Optional systemd unit | `/etc/systemd/system/telegram-gateway.service` |

## Configuration and access

All entry points read only `/etc/telegram-notify/telegram-notify.ini`, regardless
of the calling user's home or current working directory. There is no per-user
mode or fallback to configuration in the source tree.

```ini
[default]
bot_token = 1234567890:AAA_DEFAULT_TOKEN
chat_id = 188488206

[infra]
bot_token = 1234567890:BBB_INFRA_TOKEN
chat_id = 222222222

[gateway]
api_token = CHANGE_ME_TO_A_LONG_RANDOM_SECRET
listen_host = 127.0.0.1
listen_port = 8484
```

The `[gateway]` section is needed only for the optional gateway. Replace its
example secret before starting the service. Keep the listening address at
`127.0.0.1` for local use.

The INI is `root:root`, mode `0644`, in a `0755` directory. All local users can
send notifications **and read the bot and gateway tokens**. Only root can edit
installed code and configuration. No `telegram-notify` group is created. The
gateway continues to run under its dedicated `telegram-gateway` service account.

Restart the gateway after configuration edits. The CLI reads the file on each
invocation.

## Upgrade an existing manual installation

This procedure applies to the old Git checkout installed directly in
`/opt/telegram-notify`, with the INI stored inside it. Pause notification-producing
automation during the migration. Back up your configuration first.

1. Obtain the updated source in a **separate checkout outside `/opt`**, as shown
   in [installation](#installation). Run the remaining scripts from that checkout.
   Do not update the old live clone in place: the new code uses the new INI path.

2. If you use the gateway, note whether it is enabled, then stop it:

```bash
systemctl is-enabled telegram-gateway.service
sudo systemctl stop telegram-gateway.service
```

3. Back up and migrate the INI:

```bash
sudo cp -p /opt/telegram-notify/telegram-notify.ini /root/telegram-notify.ini.pre-migration
sudo python3 migrate-config.py --dry-run
sudo python3 migrate-config.py
```

   The script validates the INI, copies its exact contents into
   `/etc/telegram-notify/telegram-notify.ini`, sets `root:root` and `0644`, verifies
   the contents, then removes the old INI. It never prints credentials and refuses
   to overwrite an existing destination, including on a second run.

   If your old INI is elsewhere, use the same explicit source for both commands:

```bash
sudo python3 migrate-config.py --source /path/to/old/telegram-notify.ini --dry-run
sudo python3 migrate-config.py --source /path/to/old/telegram-notify.ini
```

   If the destination already exists, compare and reconcile the files manually;
   neither file is changed by the script. Moving the INI changes where old code
   looks for credentials, so finish the following steps before resuming senders.

4. Preserve the old checkout and remove its command link. First verify that the
   command is the old symlink, rather than a custom executable:

```bash
readlink /usr/local/bin/telegram-notify
```

   For the documented old installation, this prints
   `/opt/telegram-notify/telegram-notify.py`. Then run:

```bash
sudo mv /opt/telegram-notify /root/telegram-notify-legacy
sudo unlink /usr/local/bin/telegram-notify
```

   Use a fresh backup path if `/root/telegram-notify-legacy` already exists. If no
   command link was installed, skip `readlink` and `unlink`. Preserve a custom
   executable separately before replacing it.

5. If you used the gateway, back up its old unit before installing the new one:

```bash
sudo mv /etc/systemd/system/telegram-gateway.service /etc/systemd/system/telegram-gateway.service.pre-installer
sudo systemctl daemon-reload
```

   Preserve any custom unit settings separately. The installer refuses to replace
   an unmanaged unit or an existing command, protecting local modifications.

6. Run the [installation commands](#installation), adding `--with-gateway` if
   needed. The migrated INI is preserved. Test the CLI and start the gateway
   explicitly before resuming automation. Existing gateway enablement links are
   preserved, so check its enablement and restore your intended setting.

Keep the backup until delivery has been verified. To return to the old setup,
stop the new gateway, uninstall the new deployment, move the old checkout back,
restore the backed-up INI and unit, recreate the old CLI symlink, and reload
systemd before restarting the old gateway.

## Updating

Update the administrator's source checkout, then run the installer from it:

```bash
cd "$HOME/telegram-notify"
git status --short
git pull --ff-only
sudo python3 install.py update --dry-run
sudo python3 install.py update
```

For a gateway installation, stop the service **before either installer command**:

```bash
sudo systemctl stop telegram-gateway.service
```

The installer requires an inactive gateway, stages and validates the application,
then switches `current` to the new release. It retains earlier releases and
preserves the INI contents. Repeating installation/update from identical source
reuses the same release. The INI's ownership and permissions are restored to
`root:root` and `0644` on installation/update.

Test notifications, then restart the gateway explicitly if needed:

```bash
telegram-notify "Notification update verified"
sudo systemctl start telegram-gateway.service
```

Edited installed units or replaced command links cause the installer to stop
before replacing them. Back up customizations and reconcile them with the shipped
unit before retrying. Ordinary activation failures restore the previous command,
release link, unit, and metadata; newly created configuration and service accounts
are preserved. After a power loss or forced termination, inspect `current` and
`installation.json` before retrying.

For recovery using an earlier retained release, run its installer as the source:

```bash
sudo python3 /opt/telegram-notify/releases/<previous-source-digest>/install.py update --dry-run
sudo python3 /opt/telegram-notify/releases/<previous-source-digest>/install.py update
```

Stop the gateway first if installed, and validate delivery before starting it.

## Uninstalling

If the gateway is installed, disable and stop it first:

```bash
sudo systemctl disable --now telegram-gateway.service
```

Preview and remove the managed application:

```bash
sudo python3 /opt/telegram-notify/current/install.py uninstall --dry-run
sudo python3 /opt/telegram-notify/current/install.py uninstall
```

The INI, its directory, the gateway account, and system packages are preserved.
The installer removes its command, release files, metadata, and optional unit;
it refuses to delete modified releases or unrelated files. An empty application
directory and installer lock may remain. There is no automatic configuration purge.

## Development checks

`pyproject.toml` declares the project metadata, initial version `0.1.0`, Python
requirement, and empty runtime dependency list. System deployment uses
`install.py`; the metadata file is included in each installed release.

Run the standard-library test suite from the source checkout:

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
