#!/usr/bin/env python3
# Import libraries
import argparse
import fnmatch
import hashlib
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# Constants
ROOT = Path(__file__).resolve().parent.parent

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
	"*.pdf",
	"TA.txt",
	"CLAUDE.md",
]

ALLOWED = {".env.example"}

MAX_MB = 50


def is_excluded(relative_path: Path) -> bool:
	if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts[:-1]):
		return True
	name = relative_path.name

	# The allowed names win over the exclusion patterns
	if name in ALLOWED:
		return False

	# Patterns are matched against the file name and the full path
	text = relative_path.as_posix()
	return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(text, pattern) for pattern in EXCLUDED_FILES)


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Builds the project delivery ZIP and prints its SHA-256 fingerprint",
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("--group", required=True, help="group identifier, for example group03")
	args = parser.parse_args()

	# The group becomes part of the ZIP file name and of its folder names
	if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.group):
		print("The group identifier only accepts letters, numbers, hyphen and underscore.", file=sys.stderr)
		return 1

	# Refuse to package a project without the delivery form
	if not (ROOT / "docs" / "ENTREGA.md").exists():
		print("docs/ENTREGA.md is missing.", file=sys.stderr)
		return 1

	output_dir = ROOT / "deliveries"
	output_dir.mkdir(exist_ok=True)

	# The ZIP goes to the deliveries folder with the group and the date in its name
	output = output_dir / f"{args.group}-{datetime.now():%Y%m%d-%H%M}.zip"

	# Collect every regular file that is not excluded and not a symbolic link
	files = sorted(
		p for p in ROOT.rglob("*") if p.is_file() and not p.is_symlink() and not is_excluded(p.relative_to(ROOT))
	)

	# Store the files under the group folder inside the ZIP
	with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zip_output:
		for file in files:
			zip_output.write(file, Path(args.group) / file.relative_to(ROOT))

	size_mb = output.stat().st_size / (1024 * 1024)
	fingerprint = hashlib.sha256(output.read_bytes()).hexdigest()

	# Save the fingerprint in a file next to the ZIP
	(output.parent / (output.name + ".sha256")).write_text(f"{fingerprint}  {output.name}\n", encoding="utf-8")

	# The fingerprint is registered on the platform together with the ZIP
	print(f"File:     {output.relative_to(ROOT)}  ({len(files)} files, {size_mb:.1f} MB)")
	print(f"SHA-256:  {fingerprint}")
	if size_mb > MAX_MB:
		print(f"Warning: exceeds {MAX_MB} MB. Check whether you included files that are not code.", file=sys.stderr)
	return 0


if __name__ == "__main__":
	sys.exit(main())
