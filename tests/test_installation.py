import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import install
from telegram_notify_core import CONFIG_FILE, TelegramNotifyError, load_config


spec = importlib.util.spec_from_file_location("migrate_config", install.SOURCE / "migrate-config.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

CONFIG = b"# Keep comments and formatting\n[default]\nbot_token = secret-token\nchat_id = 123\n"


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = install.Paths(
            prefix=self.root / "opt/telegram-notify",
            config=self.root / "etc/telegram-notify/telegram-notify.ini",
            command=self.root / "bin/telegram-notify",
            unit=self.root / "systemd/telegram-gateway.service",
        )
        self.paths.prefix.mkdir(parents=True)
        self.paths.unit.parent.mkdir()
        self.chown = mock.patch("os.chown").start()
        self.addCleanup(mock.patch.stopall)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def deploy(self, source=install.SOURCE, **kwargs):
        return install.deploy(self.paths, source, kwargs.pop("mode", "install"), **kwargs)

    def state(self):
        return json.loads(self.paths.manifest.read_text())

    def changed_source(self):
        source = self.root / "source"
        source.mkdir()
        for name in install.FILES:
            shutil.copyfile(install.SOURCE / name, source / name)
        with (source / "telegram_notify_core.py").open("a") as stream:
            stream.write("\n# Different release for update test.\n")
        return source


class InstallerTests(Workspace):
    def test_installed_command_reports_version_without_configuration(self):
        self.deploy()
        self.paths.config.unlink()
        result = subprocess.run(
            [sys.executable, "-B", str(self.paths.command), "--version"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout, "telegram-notify 0.1.0\n")
        self.assertEqual(result.stderr, "")

    def test_install_cli_stages_only_application_files_and_sets_permissions(self):
        with mock.patch.object(install, "check_service") as service:
            self.deploy()
        service.assert_not_called()
        self.assertTrue(self.paths.current.is_symlink())
        self.assertEqual(self.paths.command.resolve(), self.paths.current.resolve() / "telegram-notify.py")
        self.assertEqual(self.paths.config.stat().st_mode & 0o777, 0o644)
        self.assertEqual((self.paths.current / "telegram-notify.py").stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.paths.current / ".git").exists())
        self.assertFalse((self.paths.current / "telegram-notify.ini").exists())
        self.assertFalse(self.paths.unit.exists())
        self.assertFalse(self.state()["gateway"])

    def test_existing_config_contents_preserved_and_permissions_normalized(self):
        self.paths.config.parent.mkdir(parents=True)
        self.paths.config.write_bytes(CONFIG)
        self.paths.config.chmod(0o600)
        self.deploy()
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)
        self.assertEqual(self.paths.config.stat().st_mode & 0o777, 0o644)
        self.chown.assert_called_with(self.paths.config, 0, 0)

    def test_restrictive_umask_still_allows_nonroot_command_and_config_access(self):
        previous = os.umask(0o077)
        try:
            self.deploy()
        finally:
            os.umask(previous)
        for path in (self.paths.current.resolve(), self.paths.prefix / "releases",
                     self.paths.config.parent, self.paths.command.parent):
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.paths.config.stat().st_mode & 0o777, 0o644)

    def test_dry_run_writes_nothing(self):
        before = list(self.root.rglob("*"))
        self.deploy(dry_run=True)
        self.assertEqual(list(self.root.rglob("*")), before)

    def test_update_requires_managed_installation(self):
        with self.assertRaisesRegex(ValueError, "requires an installer-managed"):
            self.deploy(mode="update")

    def test_refuse_legacy_checkout_without_touching_config(self):
        legacy = self.paths.prefix / "telegram-notify.ini"
        legacy.write_bytes(CONFIG)
        with self.assertRaisesRegex(ValueError, "migrate-config.py"):
            self.deploy()
        self.assertEqual(legacy.read_bytes(), CONFIG)
        self.assertFalse(self.paths.config.exists())

    def test_refuse_unmanaged_command(self):
        self.paths.command.parent.mkdir()
        self.paths.command.write_text("custom command")
        with self.assertRaisesRegex(ValueError, "command already exists"):
            self.deploy()
        self.assertEqual(self.paths.command.read_text(), "custom command")

    def test_update_retains_old_release_and_config(self):
        self.deploy()
        old = self.paths.current.resolve()
        self.paths.config.write_bytes(CONFIG)
        self.deploy(self.changed_source(), mode="update")
        self.assertNotEqual(self.paths.current.resolve(), old)
        self.assertTrue(old.exists())
        self.assertEqual(len(self.state()["releases"]), 2)
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)

    def test_reinstall_same_source_does_not_create_duplicate_releases(self):
        self.deploy()
        state = self.state()
        self.deploy(mode="update")
        self.assertEqual(self.state(), state)

    def test_failed_validation_leaves_active_release_unchanged(self):
        self.deploy()
        state = self.state()
        with mock.patch.object(install, "validate_source", side_effect=ValueError("invalid code")):
            with self.assertRaisesRegex(ValueError, "invalid code"):
                self.deploy(self.changed_source(), mode="update")
        self.assertEqual(install.read_manifest(self.paths), state)
        self.assertFalse(list(self.paths.prefix.glob(".staging-*")))

    def test_failed_first_install_can_be_retried(self):
        with mock.patch.object(install, "validate_source", side_effect=ValueError("invalid code")):
            with self.assertRaisesRegex(ValueError, "invalid code"):
                self.deploy()
        self.assertIsNone(install.read_manifest(self.paths))
        self.deploy()
        self.assertTrue(self.paths.command.exists())

    def test_gateway_opt_in_and_selection_preserved_during_updates(self):
        with mock.patch.object(install, "check_service"), \
                mock.patch.object(install, "ensure_gateway_user") as account, \
                mock.patch.object(install, "run") as run:
            self.deploy(with_gateway=True)
            self.assertTrue(self.paths.unit.exists())
            account.assert_called_once()
            self.deploy(self.changed_source(), mode="update")
        self.assertTrue(self.state()["gateway"])
        for call in run.call_args_list:
            self.assertNotIn("start", call.args)
            self.assertNotIn("enable", call.args)

    def test_failed_gateway_activation_restores_unit_links_and_manifest(self):
        with mock.patch.object(install, "check_service"), \
                mock.patch.object(install, "ensure_gateway_user"), mock.patch.object(install, "run"):
            self.deploy(with_gateway=True)
        old_state = self.state()
        old_unit = self.paths.unit.read_bytes()

        def fail_once(*args):
            if args == ("systemctl", "daemon-reload") and not getattr(fail_once, "failed", False):
                fail_once.failed = True
                raise subprocess.CalledProcessError(1, args)

        with mock.patch.object(install, "check_service"), \
                mock.patch.object(install, "ensure_gateway_user"), \
                mock.patch.object(install, "run", side_effect=fail_once):
            with self.assertRaises(subprocess.CalledProcessError):
                self.deploy(self.changed_source(), mode="update")
        self.assertEqual(install.read_manifest(self.paths), old_state)
        self.assertEqual(self.paths.unit.read_bytes(), old_unit)
        self.assertEqual(len(list((self.paths.prefix / "releases").iterdir())), 1)

    def test_refuse_running_gateway(self):
        with mock.patch.object(install.shutil, "which", return_value="/usr/bin/command"), \
                mock.patch.object(install.subprocess, "run", return_value=mock.Mock(stdout="active\n")):
            with self.assertRaisesRegex(ValueError, "stop telegram-gateway"):
                install.check_service()

    def test_refuse_edited_unit(self):
        with mock.patch.object(install, "check_service"), \
                mock.patch.object(install, "ensure_gateway_user"), mock.patch.object(install, "run"):
            self.deploy(with_gateway=True)
        self.paths.unit.write_text("custom unit")
        with self.assertRaisesRegex(ValueError, "modified or removed"):
            self.deploy(mode="update")

    def test_refuse_config_symlink(self):
        self.paths.config.parent.mkdir(parents=True)
        self.paths.config.symlink_to(self.root / "other-config")
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            self.deploy()

    def test_corrupt_manifest_does_not_change_files(self):
        self.deploy()
        self.paths.manifest.write_text("[]")
        with self.assertRaisesRegex(ValueError, "invalid installation manifest"):
            self.deploy()

    def test_uninstall_preserves_config_and_allows_reinstall(self):
        self.deploy()
        self.paths.config.write_bytes(CONFIG)
        install.uninstall(self.paths)
        self.assertFalse(self.paths.command.exists())
        self.assertFalse(self.paths.current.exists())
        self.assertFalse(self.paths.manifest.exists())
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)
        self.deploy()
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)

    def test_uninstall_dry_run_preserves_deployment(self):
        self.deploy()
        state = self.state()
        install.uninstall(self.paths, dry_run=True)
        self.assertEqual(install.read_manifest(self.paths), state)

    def test_uninstall_refuses_unmanaged_files(self):
        self.deploy()
        custom = self.paths.current / "local-file"
        custom.write_text("keep me")
        with self.assertRaisesRegex(ValueError, "unmanaged files"):
            install.uninstall(self.paths)
        self.assertEqual(custom.read_text(), "keep me")
        self.assertTrue(self.paths.manifest.exists())


class ConfigMigration(Workspace):
    def setUp(self):
        super().setUp()
        self.legacy = self.root / "old.ini"
        self.legacy.write_bytes(CONFIG)

    def test_move_preserves_exact_contents_and_changes_permissions(self):
        self.legacy.chmod(0o600)
        migration.migrate(self.legacy, self.paths.config)
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)
        self.assertEqual(self.paths.config.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.chown.call_args.args[1:], (0, 0))

    def test_migration_dry_run_writes_nothing(self):
        migration.migrate(self.legacy, self.paths.config, dry_run=True)
        self.assertEqual(self.legacy.read_bytes(), CONFIG)
        self.assertFalse(self.paths.config.parent.exists())

    def test_existing_destination_is_never_overwritten_even_if_identical(self):
        self.paths.config.parent.mkdir(parents=True)
        self.paths.config.write_bytes(CONFIG)
        with self.assertRaisesRegex(ValueError, "destination already exists"):
            migration.migrate(self.legacy, self.paths.config)
        self.assertEqual(self.legacy.read_bytes(), CONFIG)
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)

    def test_invalid_ini_is_not_moved(self):
        self.legacy.write_text("[broken")
        with self.assertRaises(TelegramNotifyError):
            migration.migrate(self.legacy, self.paths.config)
        self.assertTrue(self.legacy.exists())
        self.assertFalse(self.paths.config.exists())

    def test_missing_default_destination_is_not_moved(self):
        self.legacy.write_text("[other]\nchat_id = 42\n")
        with self.assertRaisesRegex(TelegramNotifyError, "missing"):
            migration.migrate(self.legacy, self.paths.config)
        self.assertTrue(self.legacy.exists())

    def test_unlink_failure_keeps_original_and_removes_new_copy(self):
        unlink = Path.unlink

        def fail_source(path, *args, **kwargs):
            if path == self.legacy:
                raise PermissionError("source cannot be removed")
            return unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fail_source):
            with self.assertRaises(PermissionError):
                migration.migrate(self.legacy, self.paths.config)
        self.assertEqual(self.legacy.read_bytes(), CONFIG)
        self.assertFalse(self.paths.config.exists())

    def test_destination_created_concurrently_is_preserved(self):
        def publish_conflict(source, destination):
            destination.write_text("concurrent config")
            raise FileExistsError("destination now exists")

        with mock.patch.object(migration.os, "link", side_effect=publish_conflict):
            with self.assertRaises(FileExistsError):
                migration.migrate(self.legacy, self.paths.config)
        self.assertEqual(self.legacy.read_bytes(), CONFIG)
        self.assertEqual(self.paths.config.read_text(), "concurrent config")

    def test_missing_source_is_reported(self):
        self.legacy.unlink()
        with self.assertRaisesRegex(ValueError, "source config not found"):
            migration.migrate(self.legacy, self.paths.config)

    def test_changed_source_is_preserved(self):
        link = os.link

        def change_source(source, destination):
            link(source, destination)
            self.legacy.write_bytes(CONFIG + b"# Edited during migration\n")

        with mock.patch.object(migration.os, "link", side_effect=change_source):
            with self.assertRaisesRegex(ValueError, "changed during migration"):
                migration.migrate(self.legacy, self.paths.config)
        self.assertEqual(self.legacy.read_bytes(), CONFIG + b"# Edited during migration\n")
        self.assertFalse(self.paths.config.exists())

    def test_invalid_ini_error_does_not_expose_credentials(self):
        self.legacy.write_text("[default]\nsecret-token-on-invalid-line\n")
        with self.assertRaises(TelegramNotifyError) as raised:
            migration.migrate(self.legacy, self.paths.config)
        self.assertNotIn("secret-token", str(raised.exception))

    def test_interruption_after_source_removal_keeps_new_config(self):
        unlink = Path.unlink

        def interrupt_after_unlink(path, *args, **kwargs):
            result = unlink(path, *args, **kwargs)
            if path == self.legacy:
                raise KeyboardInterrupt()
            return result

        with mock.patch.object(Path, "unlink", interrupt_after_unlink):
            with self.assertRaises(KeyboardInterrupt):
                migration.migrate(self.legacy, self.paths.config)
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.paths.config.read_bytes(), CONFIG)


class ConfigurationPath(unittest.TestCase):
    def test_config_is_system_wide(self):
        self.assertEqual(CONFIG_FILE, Path("/etc/telegram-notify/telegram-notify.ini"))

    def test_unreadable_config_is_reported_cleanly(self):
        with mock.patch.object(Path, "open", side_effect=PermissionError("access denied")):
            with self.assertRaisesRegex(TelegramNotifyError, "cannot read config file"):
                load_config()


if __name__ == "__main__":
    unittest.main()
