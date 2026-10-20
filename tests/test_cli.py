import contextlib
import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("telegram_notify_cli", SOURCE / "telegram-notify.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class VersionTests(unittest.TestCase):
    def test_version_exits_successfully_without_loading_config_or_sending(self):
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["telegram-notify", "--version"]), \
                mock.patch.object(cli, "load_config") as load_config, \
                mock.patch.object(cli, "send_notification") as send_notification, \
                contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                cli.main()
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue(), f"telegram-notify {cli.VERSION}\n")
        load_config.assert_not_called()
        send_notification.assert_not_called()

    def test_version_matches_project_metadata(self):
        self.assertRegex(
            (SOURCE / "pyproject.toml").read_text(),
            rf'(?m)^version = "{re.escape(cli.VERSION)}"$',
        )
