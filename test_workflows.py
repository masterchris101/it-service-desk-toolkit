"""Exercise the public CLI in a disposable SQLite lab. Run python3 -m unittest -v."""
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

CLI = Path(__file__).with_name("it_helpdesk_toolkit.py").resolve()


class ServiceDeskWorkflows(unittest.TestCase):
    def setUp(self):
        lab = tempfile.TemporaryDirectory()
        self.addCleanup(lab.cleanup)
        self.folder = Path(lab.name)

    def run_cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(CLI), *args], cwd=self.folder,
            capture_output=True, text=True, check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def test_unknown_cloud_pc_actions(self):
        for action in ("restart", "reprovision", "deprovision"):
            with self.subTest(action=action):
                result = self.run_cli("w365", action, "999", success=False)
                self.assertIn("CPC-999", result.stderr)
                self.assertIn("not found", result.stderr.lower())
                self.assertEqual(result.stdout, "")

    def test_provision_and_restart(self):
        self.run_cli("w365", "provision", "--user", "learner")
        self.run_cli("w365", "restart", "1")
        listing = self.run_cli("w365", "list").stdout
        self.assertIn("learner", listing)
        self.assertIn("Running", listing)

    def test_critical_ticket_deadline_and_closure(self):
        self.run_cli("ticket", "new", "Classroom offline", "--impact", "1", "--urgency", "1")
        self.assertIn("Classroom offline", self.run_cli("ticket", "list").stdout)
        self.run_cli("ticket", "close", "1", "--note", "Instructor confirmed")
        self.assertIn("No open tickets", self.run_cli("ticket", "list").stdout)
        with sqlite3.connect(self.folder / "helpdesk.db") as db:
            priority, opened, due, notes = db.execute(
                "SELECT priority, opened, sla_due, notes FROM tickets WHERE id=1"
            ).fetchone()
        self.assertEqual(priority, 1)
        self.assertEqual(datetime.fromisoformat(due) - datetime.fromisoformat(opened), timedelta(hours=4))
        self.assertIn("Instructor confirmed", notes)

    def test_compliance_findings_become_tickets(self):
        self.run_cli("seed")
        self.run_cli("devices", "compliance", "--auto-ticket")
        with sqlite3.connect(self.folder / "helpdesk.db") as db:
            rows = db.execute(
                "SELECT short_desc FROM tickets WHERE category='Endpoint Management'"
            ).fetchall()
        self.assertCountEqual(
            [row[0].split()[1] for row in rows], ["WIN-LT-002", "WIN-DT-003", "MAC-LT-005"]
        )
