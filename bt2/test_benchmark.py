"""Kiểm tra lỗi hồi quy psql nhận URI qua PGDATABASE."""

import unittest
from unittest.mock import patch

from benchmark import run_psql


class PsqlConnectionTest(unittest.TestCase):
    @patch("subprocess.run")
    def test_uri_is_passed_as_conninfo_and_password_stays_in_environment(self, run):
        run_psql(
            "postgresql://tester:example-password@localhost:5432/bt2_lab",
            "SELECT 1;\n", "psql",
        )
        args, kwargs = run.call_args
        command = args[0]
        connection = command[command.index("-d") + 1]
        self.assertIn("dbname=bt2_lab", connection)
        self.assertNotIn("password", connection)
        self.assertEqual(kwargs["env"]["PGPASSWORD"], "example-password")
        self.assertTrue(kwargs["check"])


if __name__ == "__main__":
    unittest.main()
