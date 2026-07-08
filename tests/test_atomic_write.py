from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from worksisyphus import atomic_write_bytes, atomic_write_text


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_write_failure_preserves_previous_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "resume.tex"
            output.write_bytes(b"previous output\n")

            with patch("worksisyphus.artifacts.os.replace", side_effect=RuntimeError("replace failed")):
                with self.assertRaises(RuntimeError):
                    atomic_write_bytes(output, b"new partial output\n")

            self.assertEqual(output.read_bytes(), b"previous output\n")
            self.assertEqual(list(output.parent.glob(f".{output.name}.*.tmp")), [])

    def test_atomic_write_text_replaces_output_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "resume.tex"

            atomic_write_text(output, "complete output\n")

            self.assertEqual(output.read_text(encoding="utf-8"), "complete output\n")


if __name__ == "__main__":
    unittest.main()
