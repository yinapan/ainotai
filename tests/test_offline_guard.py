import os
import unittest

from src.ai_asset_audit.pipeline.offline_guard import check_offline_status


class OfflineGuardTests(unittest.TestCase):
    def test_offline_status_reports_missing_env(self):
        old_values = {name: os.environ.pop(name, None) for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")}
        try:
            status = check_offline_status()
            self.assertFalse(status.env_ok)
            self.assertEqual(status.missing_env, ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"])
        finally:
            for name, value in old_values.items():
                if value is not None:
                    os.environ[name] = value

    def test_offline_status_ok_when_env_set(self):
        old_values = {}
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
            old_values[name] = os.environ.get(name)
            os.environ[name] = "1"
        try:
            status = check_offline_status()
            self.assertTrue(status.env_ok)
            self.assertEqual(status.missing_env, [])
        finally:
            for name, value in old_values.items():
                if value is not None:
                    os.environ[name] = value
                else:
                    os.environ.pop(name, None)


if __name__ == "__main__":
    unittest.main()
