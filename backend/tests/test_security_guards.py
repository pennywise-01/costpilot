import unittest
from pathlib import Path

from app.enterprise.modules.export.service import (
    get_export_storage_dir,
    is_export_file_path_allowed,
)


class ExportPathGuardTests(unittest.TestCase):
    def test_allows_paths_inside_export_storage_dir(self) -> None:
        storage_dir = get_export_storage_dir()
        candidate = storage_dir / "security_guard_test.csv"
        self.assertTrue(is_export_file_path_allowed(str(candidate)))

    def test_rejects_paths_outside_export_storage_dir(self) -> None:
        outside = Path("C:/Windows/System32/drivers/etc/hosts")
        self.assertFalse(is_export_file_path_allowed(str(outside)))

    def test_rejects_empty_path(self) -> None:
        self.assertFalse(is_export_file_path_allowed(None))
        self.assertFalse(is_export_file_path_allowed(""))


if __name__ == "__main__":
    unittest.main()
