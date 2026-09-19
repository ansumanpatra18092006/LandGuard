#!/usr/bin/env python3
"""
clean_zip.py

Create a clean ZIP archive of a project while excluding heavy, generated,
private, and irrelevant files/folders such as node_modules, .git, caches,
build output, virtual environments, and environment secrets.

Usage:
    python clean_zip.py
    python clean_zip.py C:\\LandGuard
    python clean_zip.py C:\\LandGuard --output C:\\LandGuard_clean.zip

By default, the current directory is zipped.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import zipfile


EXCLUDED_DIR_NAMES = {
    ".git", ".github", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".next", ".nuxt", ".turbo", ".cache", ".parcel-cache",
    "__pycache__", "node_modules", "dist", "build", "coverage", "htmlcov",
    "venv", ".venv", "env", ".envdir", "target", "tmp", "temp", "logs",
}

EXCLUDED_FILE_NAMES = {
    ".DS_Store", "Thumbs.db", "desktop.ini", ".coverage", "npm-debug.log",
    "yarn-debug.log", "yarn-error.log", "pnpm-debug.log",
}

EXCLUDED_PATTERNS = [
    "*.pyc", "*.pyo", "*.pyd", "*.log", "*.tmp", "*.temp", "*.swp",
    "*.swo", "*.bak", "*.zip", "*.tar", "*.tar.gz", "*.7z", "*.rar",
    "*.sqlite", "*.sqlite3", "*.db", "*.lock.tmp", ".env", ".env.*",
]

ALLOWED_ENV_FILES = {".env.example", ".env.sample", ".env.template"}


def should_exclude(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)

    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
        return True

    if path.is_dir() and path.name in EXCLUDED_DIR_NAMES:
        return True

    if path.is_file():
        if path.name in ALLOWED_ENV_FILES:
            return False
        if path.name in EXCLUDED_FILE_NAMES:
            return True
        for pattern in EXCLUDED_PATTERNS:
            if fnmatch.fnmatch(path.name, pattern):
                return True

    return False


def create_clean_zip(project_dir: Path, output_zip: Path) -> tuple[int, int]:
    project_dir = project_dir.resolve()
    output_zip = output_zip.resolve()

    if not project_dir.exists() or not project_dir.is_dir():
        raise ValueError(f"Project directory does not exist: {project_dir}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    included = 0
    excluded = 0

    try:
        output_rel = output_zip.relative_to(project_dir)
    except ValueError:
        output_rel = None

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for current_root, dirnames, filenames in os.walk(project_dir):
            current_path = Path(current_root)

            kept_dirs = []
            for dirname in dirnames:
                candidate = current_path / dirname
                if should_exclude(candidate, project_dir):
                    excluded += 1
                else:
                    kept_dirs.append(dirname)
            dirnames[:] = kept_dirs

            for filename in filenames:
                file_path = current_path / filename
                rel_path = file_path.relative_to(project_dir)

                if output_rel is not None and rel_path == output_rel:
                    excluded += 1
                    continue

                if should_exclude(file_path, project_dir):
                    excluded += 1
                    continue

                archive_name = Path(project_dir.name) / rel_path
                zf.write(file_path, archive_name)
                included += 1

    return included, excluded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a clean ZIP of a project, excluding generated/private files."
    )
    parser.add_argument(
        "project_dir", nargs="?", default=".",
        help="Project directory to zip. Defaults to current directory."
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output ZIP path. Defaults to <project_name>_clean.zip next to the project."
    )

    args = parser.parse_args()
    project_dir = Path(args.project_dir)

    if args.output:
        output_zip = Path(args.output)
    else:
        resolved = project_dir.resolve()
        output_zip = resolved / f"{resolved.name}_clean.zip"

    included, excluded = create_clean_zip(project_dir, output_zip)

    print(f"Created: {output_zip}")
    print(f"Included files: {included}")
    print(f"Excluded entries: {excluded}")


if __name__ == "__main__":
    main()
