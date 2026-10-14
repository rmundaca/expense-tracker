"""The APKG must never ship runtime data (the NAS upgrade would replace its own files with them)."""
import io
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_package import create_tar_gz_in_memory  # noqa: E402


def test_package_excludes_runtime_data():
    root = Path(tempfile.mkdtemp())
    (root / "app").mkdir()
    (root / "app" / "main.py").write_bytes(b"print('hi')\r\n")
    (root / "data").mkdir()
    (root / "data" / "users").mkdir()
    for name in ("expense_tracker.db", "expense_tracker.db-wal", "expense_tracker.db.pre-multiuser-20260925120000",
                 "app.db", "users/1.db", "users/1.db-wal", "classifier_model.json", "secret.key", "app.log"):
        (root / "data" / name).write_text("x")
    (root / "app" / "__pycache__").mkdir()
    (root / "app" / "__pycache__" / "main.cpython-311.pyc").write_text("x")

    with tarfile.open(fileobj=io.BytesIO(create_tar_gz_in_memory(root).getvalue())) as tar:
        names = tar.getnames()
        assert names == ["app/main.py"]
        assert tar.extractfile("app/main.py").read() == b"print('hi')\n"  # CRLF normalized for the NAS


def test_package_carries_the_license():
    root = Path(tempfile.mkdtemp())
    (root / "app").mkdir()
    (root / "app" / "main.py").write_text("x")
    license_file = Path(tempfile.mkdtemp()) / "LICENSE"
    license_file.write_bytes(b"MIT License\r\n")

    archive = create_tar_gz_in_memory(root, extra_files={"LICENSE": license_file})
    with tarfile.open(fileobj=io.BytesIO(archive.getvalue())) as tar:
        assert sorted(tar.getnames()) == ["LICENSE", "app/main.py"]
        assert tar.extractfile("LICENSE").read() == b"MIT License\n"
