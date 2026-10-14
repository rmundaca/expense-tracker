#!/usr/bin/env python3
"""
build_package.py - builds the APKG package for Asustor ADM (bumps the version unless told otherwise)
"""
import os
import io
import re
import sys
import json
import tarfile
import zipfile
import argparse
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CONTROL_DIR = ROOT_DIR / "CONTROL"
PACKAGE_DIR = ROOT_DIR / "package"
CONFIG_JSON = CONTROL_DIR / "config.json"
CHANGELOG_TXT = CONTROL_DIR / "changelog.txt"
APP_INIT_PY = PACKAGE_DIR / "app" / "__init__.py"
LICENSE_FILE = ROOT_DIR / "LICENSE"

DIST_DIR = ROOT_DIR / "dist"

def parse_semver(ver_str: str):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", ver_str.strip())
    if not m:
        raise ValueError(f"Invalid semver version: '{ver_str}'")
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)

def bump_version_string(ver_str: str, bump_type: str) -> str:
    major, minor, patch, extra = parse_semver(ver_str)
    if bump_type == "major": return f"{major + 1}.0.0"
    if bump_type == "minor": return f"{major}.{minor + 1}.0"
    if bump_type == "patch": return f"{major}.{minor}.{patch + 1}"
    return ver_str

def get_current_version() -> str:
    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("general", {}).get("version") or data.get("version", "1.0.0")

def update_version(new_version: str, note: str = None):
    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    if "general" in config_data:
        config_data["general"]["version"] = new_version
    config_data["version"] = new_version
    with open(CONFIG_JSON, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if CHANGELOG_TXT.exists():
        entry = f"{new_version} ({date.today().isoformat()})\n- {note or 'Update'}\n\n"
        with open(CHANGELOG_TXT, "r", encoding="utf-8") as f:
            old = f.read().strip()
        if not old.startswith(new_version):
            with open(CHANGELOG_TXT, "w", encoding="utf-8") as f:
                f.write(entry + old + "\n")

    if APP_INIT_PY.exists():
        with open(APP_INIT_PY, "r", encoding="utf-8") as f:
            c = f.read()
        c = re.sub(r'__version__\s*=\s*["\'][^"\']+["\']', f'__version__ = "{new_version}"', c)
        with open(APP_INIT_PY, "w", encoding="utf-8") as f:
            f.write(c)

def create_tar_gz_in_memory(source_dir: Path, exclude_patterns=None, extra_files=None):
    """tar.gz of source_dir, plus extra_files: {name in the archive: path} for files that live elsewhere."""
    if exclude_patterns is None:
        # Runtime data (DB, trained model, logs, credentials key) must never ship: post-upgrade restores with
        # `cp -an`, so a bundled file would silently replace the NAS's own copy.
        exclude_patterns = ["__pycache__", "*.pyc", "*.pyo", ".git*", "venv", "*.db", "*.db-*", "*.db.*",
                            "classifier_model.json", "secret.key", "*.log", "app.log*", "*.tar.gz", "dist", "*.apk",
                            "apkg_validator.py"]

    entries = []
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not any(Path(d).match(p) for p in exclude_patterns)]
        for file in files:
            if not any(Path(file).match(p) for p in exclude_patterns):
                file_path = Path(root) / file
                entries.append((file_path, file_path.relative_to(source_dir).as_posix()))
    entries += [(Path(path), arcname) for arcname, path in (extra_files or {}).items()]

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for file_path, arcname in entries:
            # Read content and normalize line endings for scripts/text
            with open(file_path, "rb") as f:
                content = f.read()

            # Normalize CRLF to LF for shell scripts and source files
            if file_path.suffix.lower() in [".sh", ".py", ".json", ".txt", ".html", ".css", ".js"] or file_path.name == "LICENSE":
                content = content.replace(b"\r\n", b"\n")

            tarinfo = tarfile.TarInfo(name=arcname)
            tarinfo.size = len(content)
            tarinfo.mtime = int(file_path.stat().st_mtime)
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = "root"
            tarinfo.gname = "root"

            if file_path.suffix.lower() in [".sh", ".py"]:
                tarinfo.mode = 0o755
            else:
                tarinfo.mode = 0o644

            tar.addfile(tarinfo, fileobj=io.BytesIO(content))
    buf.seek(0)
    return buf

def build_apkg(new_version: str):
    pkg_name = json.load(open(CONFIG_JSON, "r", encoding="utf-8")).get("general", {}).get("package", "expense-tracker")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    out_apk = DIST_DIR / f"{pkg_name}.apk"
    out_ver = DIST_DIR / f"{pkg_name}_{new_version}_any.apk"

    print("Packing CONTROL...")
    control_bytes = create_tar_gz_in_memory(CONTROL_DIR)
    print("Packing package...")
    # MIT: the license notice travels with every copy of the software
    package_bytes = create_tar_gz_in_memory(PACKAGE_DIR, extra_files={"LICENSE": LICENSE_FILE})

    # The APKG format of ASUSTOR ADM 2.0+ strictly requires:
    # 1. 'apkg-version' containing '2.0\n'
    # 2. 'control.tar.gz'
    # 3. 'data.tar.gz'
    with zipfile.ZipFile(out_apk, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("apkg-version", b"2.0\n")
        z.writestr("control.tar.gz", control_bytes.getvalue())
        z.writestr("data.tar.gz", package_bytes.getvalue())

    import shutil
    shutil.copy2(out_apk, out_ver)
    print("\n[OK] APKG package built in dist/:")
    print(f"  -> dist/{out_apk.name} ({out_apk.stat().st_size / 1024:.1f} KB)")
    print(f"  -> dist/{out_ver.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--version", type=str)
    parser.add_argument("--no-bump", action="store_true")
    parser.add_argument("-m", "--message", type=str)
    args = parser.parse_args()

    cur_ver = get_current_version()
    new_ver = cur_ver if args.no_bump else (args.version or bump_version_string(cur_ver, args.bump))
    update_version(new_ver, args.message)
    build_apkg(new_ver)
