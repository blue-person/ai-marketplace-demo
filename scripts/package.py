#!/usr/bin/env python3
"""Builds the project delivery ZIP and its SHA-256 fingerprint.

Usage (from the project root):
    python scripts/package.py --group group03

Creates deliveries/<group>-<date>.zip with the source code and leaves out what
must not be delivered: .env, installed dependencies, build output and the git
repository. Prints the SHA-256 fingerprint to register on the platform together
with the ZIP. Uses only the Python 3 standard library.
"""

import argparse
import fnmatch
import hashlib
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories that are never included (at any level).
EXCLUDED_DIRECTORIES = {
	".git",
	"node_modules",
	"dist",
	"__pycache__",
	".venv",
	"venv",
	".idea",
	".vscode",
	"deliveries",
	".sandbox",
	".pytest_cache",
	".mypy_cache",
	"__MACOSX",
}
# Files that are never included.
EXCLUDED_FILES = [
	".env",
	".env.*",
	"*.pyc",
	"*.o",
	".DS_Store",
	"Thumbs.db",
	"*.zip",
	"*.log",
	"worker/robot",
	# Course material and personal notes that are not part of the source code.
	"*.pdf",
	"TA.txt",
	"CLAUDE.md",
]
# Exception: the variables template is delivered.
ALLOWED = {".env.example"}

MAX_MB = 50


def is_excluded(relative_path: Path) -> bool:
	if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts[:-1]):
		return True
	name = relative_path.name
	if name in ALLOWED:
		return False
	text = relative_path.as_posix()
	return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(text, pattern) for pattern in EXCLUDED_FILES)


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--group", required=True, help="group identifier, for example group03")
	args = parser.parse_args()
	if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.group):
		print("The group identifier only accepts letters, numbers, hyphen and underscore.", file=sys.stderr)
		return 1

	if not (ROOT / "docs" / "ENTREGA.md").exists():
		print("docs/ENTREGA.md is missing.", file=sys.stderr)
		return 1

	output_dir = ROOT / "deliveries"
	output_dir.mkdir(exist_ok=True)
	output = output_dir / f"{args.group}-{datetime.now():%Y%m%d-%H%M}.zip"

	files = sorted(
		p for p in ROOT.rglob("*") if p.is_file() and not p.is_symlink() and not is_excluded(p.relative_to(ROOT))
	)
	with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zip_output:
		for file in files:
			zip_output.write(file, Path(args.group) / file.relative_to(ROOT))

	size_mb = output.stat().st_size / (1024 * 1024)
	fingerprint = hashlib.sha256(output.read_bytes()).hexdigest()
	(output.parent / (output.name + ".sha256")).write_text(f"{fingerprint}  {output.name}\n", encoding="utf-8")

	print(f"File:     {output.relative_to(ROOT)}  ({len(files)} files, {size_mb:.1f} MB)")
	print(f"SHA-256:  {fingerprint}")
	if size_mb > MAX_MB:
		print(f"Warning: exceeds {MAX_MB} MB. Check whether you included files that are not code.", file=sys.stderr)
	return 0


if __name__ == "__main__":
	sys.exit(main())
