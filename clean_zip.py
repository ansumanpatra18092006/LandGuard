#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import shutil
import tempfile
import zipfile


# ============================================================
# DIRECTORIES TO EXCLUDE
# ============================================================

EXCLUDED_DIR_NAMES = {
    # Git / IDE
    ".git",
    ".github",
    ".idea",
    ".vscode",

    # Python caches
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".hypothesis",
    ".ipynb_checkpoints",

    # Standard virtual environments
    ".venv",
    "venv",
    "env",
    ".envdir",
    "virtualenv",

    # Node
    "node_modules",
    ".vite",
    ".next",
    ".nuxt",
    ".turbo",
    ".parcel-cache",

    # Build output
    "dist",
    "build",
    "coverage",
    "htmlcov",

    # Cache/temp/logs
    ".cache",
    "tmp",
    "temp",
    "logs",

    # Other build environments
    "target",
}


# Handles:
# .lacrris-venv
# bhoomi-venv
# test_venv
# anything ending in -venv / _venv
EXCLUDED_DIR_PATTERNS = {
    "*-venv",
    "*_venv",
    "venv-*",
    "venv_*",
    ".*-venv",
    ".*_venv",
}


# ============================================================
# FILES TO EXCLUDE
# ============================================================

EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".coverage",

    "npm-debug.log",
    "yarn-debug.log",
    "yarn-error.log",
    "pnpm-debug.log",
}


EXCLUDED_FILE_PATTERNS = {
    # Office temporary lock files
    "~$*",

    # Python generated
    "*.pyc",
    "*.pyo",
    "*.pyd",

    # Temporary/editor
    "*.tmp",
    "*.temp",
    "*.swp",
    "*.swo",
    "*.bak",
    "*~",

    # Logs
    "*.log",

    # Archives
    "*.zip",
    "*.rar",
    "*.7z",
    "*.tar",
    "*.tar.gz",
    "*.tgz",

    # Local databases
    "*.sqlite",
    "*.sqlite3",
    "*.db",

    # Presentations
    "*.pptx",

    # Other generated temp
    "*.lock.tmp",

    # Environment secrets
    ".env",
    ".env.*",
}


# Safe environment templates that SHOULD stay in source
ALLOWED_ENV_FILES = {
    ".env.example",
    ".env.sample",
    ".env.template",
}


# ============================================================
# HELPERS
# ============================================================

def matches_pattern(name: str, patterns: set[str]) -> bool:
    name = name.lower()

    return any(
        fnmatch.fnmatch(name, pattern.lower())
        for pattern in patterns
    )


def is_virtual_environment(path: Path) -> bool:
    """
    Detect Python virtual environments even when they have custom names
    such as .lacrris-venv.
    """
    try:
        return (
            path.is_dir()
            and (path / "pyvenv.cfg").exists()
        )
    except OSError:
        return False


def exclude_directory(path: Path) -> bool:
    name = path.name

    if name in EXCLUDED_DIR_NAMES:
        return True

    if matches_pattern(name, EXCLUDED_DIR_PATTERNS):
        return True

    if is_virtual_environment(path):
        return True

    return False


def exclude_file(path: Path) -> bool:
    name = path.name

    # Explicitly preserve environment examples
    if name in ALLOWED_ENV_FILES:
        return False

    if name in EXCLUDED_FILE_NAMES:
        return True

    if matches_pattern(name, EXCLUDED_FILE_PATTERNS):
        return True

    return False


def human_size(size: int) -> str:
    value = float(size)

    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} TB"


# ============================================================
# ZIP CREATION
# ============================================================

def create_clean_zip(
    project_dir: Path,
    output_zip: Path,
    verbose: bool = False,
):
    project_dir = project_dir.resolve()
    output_zip = output_zip.resolve()

    if not project_dir.exists():
        raise RuntimeError(
            f"Project directory does not exist: {project_dir}"
        )

    if not project_dir.is_dir():
        raise RuntimeError(
            f"Not a directory: {project_dir}"
        )

    included = 0
    excluded = 0
    skipped_locked = 0
    total_size = 0

    # --------------------------------------------------------
    # Build into temporary ZIP first.
    #
    # This avoids reading our own output ZIP while os.walk()
    # is scanning the project.
    # --------------------------------------------------------

    temp_zip = project_dir / (
        f".{project_dir.name}_clean_creating.zip"
    )

    # Remove stale temporary ZIP if one exists.
    try:
        if temp_zip.exists():
            temp_zip.unlink()
    except OSError:
        pass

    print(f"Project : {project_dir}")
    print(f"Output  : {output_zip}")
    print()

    try:
        with zipfile.ZipFile(
            temp_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as zf:

            for current_root, dirnames, filenames in os.walk(
                project_dir,
                topdown=True,
            ):
                current_path = Path(current_root)

                # ------------------------------------------------
                # Stop os.walk entering excluded folders
                # ------------------------------------------------

                allowed_dirs = []

                for dirname in dirnames:
                    folder = current_path / dirname

                    if exclude_directory(folder):
                        excluded += 1

                        if verbose:
                            print(
                                "[SKIP DIR ]",
                                folder.relative_to(project_dir),
                            )

                        continue

                    allowed_dirs.append(dirname)

                dirnames[:] = allowed_dirs

                # ------------------------------------------------
                # Files
                # ------------------------------------------------

                for filename in filenames:
                    file_path = current_path / filename

                    try:
                        resolved_file = file_path.resolve()
                    except OSError:
                        resolved_file = file_path

                    # Never zip the ZIP currently being generated.
                    if resolved_file == temp_zip:
                        continue

                    # Never zip final output file.
                    if resolved_file == output_zip:
                        continue

                    if exclude_file(file_path):
                        excluded += 1

                        if verbose:
                            print(
                                "[SKIP FILE]",
                                file_path.relative_to(project_dir),
                            )

                        continue

                    try:
                        size = file_path.stat().st_size

                        relative_path = file_path.relative_to(
                            project_dir
                        )

                        archive_path = (
                            Path(project_dir.name)
                            / relative_path
                        )

                        zf.write(
                            file_path,
                            archive_path.as_posix(),
                        )

                        included += 1
                        total_size += size

                        if verbose:
                            print(
                                "[ADD      ]",
                                relative_path,
                            )

                    except PermissionError:
                        skipped_locked += 1

                        print(
                            "[LOCKED   ] skipped:",
                            file_path.relative_to(project_dir),
                        )

                    except OSError as exc:
                        skipped_locked += 1

                        print(
                            "[UNREADABLE] skipped:",
                            file_path.relative_to(project_dir),
                            f"({exc})",
                        )

        # --------------------------------------------------------
        # Replace old final archive
        # --------------------------------------------------------

        try:
            if output_zip.exists():
                output_zip.unlink()

        except PermissionError:
            raise RuntimeError(
                "\nCannot replace the existing ZIP because Windows "
                "currently has it open:\n\n"
                f"    {output_zip}\n\n"
                "Close File Explorer preview, WinRAR, 7-Zip, VS Code, "
                "or any application using the ZIP, then run again."
            )

        shutil.move(
            str(temp_zip),
            str(output_zip),
        )

    finally:
        # Clean leftover temp file after failures
        if temp_zip.exists():
            try:
                temp_zip.unlink()
            except OSError:
                pass

    final_size = (
        output_zip.stat().st_size
        if output_zip.exists()
        else 0
    )

    return {
        "included": included,
        "excluded": excluded,
        "locked": skipped_locked,
        "source_size": total_size,
        "zip_size": final_size,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a clean source ZIP while excluding "
            "venvs, node_modules, caches, builds and secrets."
        )
    )

    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project folder. Default: current directory.",
    )

    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional output ZIP path.",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show included/excluded paths.",
    )

    args = parser.parse_args()

    project_dir = Path(
        args.project_dir
    ).resolve()

    # --------------------------------------------------------
    # DEFAULT ZIP IS INSIDE PROJECT DIRECTORY
    # --------------------------------------------------------

    if args.output:
        output_zip = Path(args.output).resolve()

    else:
        output_zip = (
            project_dir
            / f"{project_dir.name}_clean.zip"
        )

    result = create_clean_zip(
        project_dir,
        output_zip,
        verbose=args.verbose,
    )

    print()
    print("=" * 65)
    print("CLEAN ZIP COMPLETE")
    print("=" * 65)

    print(
        f"Created          : {output_zip}"
    )

    print(
        f"Included files   : {result['included']}"
    )

    print(
        f"Excluded entries : {result['excluded']}"
    )

    print(
        f"Locked skipped   : {result['locked']}"
    )

    print(
        f"Raw included size: "
        f"{human_size(result['source_size'])}"
    )

    print(
        f"Final ZIP size   : "
        f"{human_size(result['zip_size'])}"
    )

    print("=" * 65)


if __name__ == "__main__":
    main()