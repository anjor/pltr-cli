#!/usr/bin/env python3
"""
Release script for pltr-cli

Usage:
    # Interactive mode (for humans)
    python scripts/release.py --version 0.1.1
    python scripts/release.py --type patch

    # Non-interactive mode (for AI agents/automation)
    python scripts/release.py --version 0.1.1 --yes --no-push
    python scripts/release.py --type patch --yes --push

    # Dry run to see what would happen
    python scripts/release.py --version 0.1.1 --dry-run

Flags:
    --yes, -y         Skip all confirmation prompts (non-interactive mode)
    --push            Push to origin without asking (requires --yes)
    --no-push         Don't push to origin (useful for testing)
    --dry-run         Show what would be done without making changes
"""

import argparse
import re
import subprocess
import sys
import tomllib
import tomli_w
from pathlib import Path


def get_current_version():
    """Get the current version from pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    return config["project"]["version"]


def update_version_in_pyproject(new_version):
    """Update version in pyproject.toml"""
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    config["project"]["version"] = new_version

    with open(pyproject_path, "wb") as f:
        tomli_w.dump(config, f)

    print(f"Updated pyproject.toml version to {new_version}")


def update_version_in_init_py(new_version):
    """Update __version__ in src/pltr/__init__.py"""
    init_py_path = Path("src/pltr/__init__.py")

    if not init_py_path.exists():
        print("Error: src/pltr/__init__.py not found")
        sys.exit(1)

    # Read the current content
    content = init_py_path.read_text()

    # Update the version using regex
    import re

    pattern = r'__version__ = "[^"]+"'
    replacement = f'__version__ = "{new_version}"'

    if not re.search(pattern, content):
        print("Error: Could not find __version__ in src/pltr/__init__.py")
        sys.exit(1)

    updated_content = re.sub(pattern, replacement, content)
    init_py_path.write_text(updated_content)

    print(f"Updated src/pltr/__init__.py __version__ to {new_version}")


def validate_version(version):
    """Validate semantic version format"""
    pattern = r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$"
    if not re.match(pattern, version):
        print(
            f"Error: Invalid version format '{version}'. Use semantic versioning (e.g., 1.0.0)"
        )
        sys.exit(1)


def run_git_command(cmd):
    """Run git command and return result"""
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {cmd}")
        print(f"Error output: {e.stderr}")
        sys.exit(1)


def check_git_status():
    """Check if git working directory is clean"""
    status = run_git_command("git status --porcelain")
    if status:
        print(
            "Error: Working directory is not clean. Please commit or stash changes first."
        )
        print("Uncommitted changes:")
        print(status)
        sys.exit(1)


def check_tag_exists(version):
    """Check if a git tag already exists for this version"""
    tag_name = f"v{version}"
    try:
        # Check if tag exists locally
        result = subprocess.run(
            ["git", "tag", "-l", tag_name], capture_output=True, text=True, check=True
        )
        if result.stdout.strip():
            print(f"Warning: Tag {tag_name} already exists locally.")
            return True
    except subprocess.CalledProcessError:
        pass

    try:
        # Check if tag exists on remote
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "origin", tag_name],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            print(f"Warning: Tag {tag_name} already exists on remote.")
            return True
    except subprocess.CalledProcessError:
        # Remote might not exist or be accessible, continue
        pass

    return False


def update_uv_lock():
    """Update uv.lock file after version change"""
    try:
        subprocess.run(["uv", "lock"], check=True, capture_output=True, text=True)
        print("Updated uv.lock file")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error updating uv.lock: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Warning: uv command not found. Skipping uv.lock update.")
        print("Please ensure uv is installed to keep lock file in sync.")
        return False


def create_release_commit_and_tag(version, release_type, push_mode="ask"):
    """Create release commit and tag"""
    # Stage the version file changes
    run_git_command("git add pyproject.toml src/pltr/__init__.py uv.lock")

    # Create release commit
    commit_message = f"{release_type}: Release version {version}"
    run_git_command(f'git commit -m "{commit_message}"')
    print(f"Created release commit: {commit_message}")

    # Create and push tag
    tag_name = f"v{version}"
    try:
        run_git_command(f'git tag -a {tag_name} -m "Release {version}"')
        print(f"Created tag: {tag_name}")
    except SystemExit:
        print(f"Error: Failed to create tag {tag_name}. It may already exist.")
        print(f"To delete the existing tag: git tag -d {tag_name}")
        print(f"To delete from remote: git push origin :refs/tags/{tag_name}")
        raise

    # Handle push based on mode
    if push_mode == "force":
        run_git_command("git push origin HEAD")
        run_git_command(f"git push origin {tag_name}")
        print("Pushed commit and tag to origin")
        print("GitHub Actions will now build and publish the release automatically")
        print("Monitor the workflow at: https://github.com/anjor/pltr-cli/actions")
    elif push_mode == "no":
        print("Not pushing to origin (--no-push specified).")
        print("You can push manually later with:")
        print("  git push origin HEAD")
        print(f"  git push origin {tag_name}")
    else:  # push_mode == "ask"
        push_choice = (
            input(f"Push commit and tag '{tag_name}' to origin? (y/N): ")
            .strip()
            .lower()
        )
        if push_choice in ["y", "yes"]:
            run_git_command("git push origin HEAD")
            run_git_command(f"git push origin {tag_name}")
            print("Pushed commit and tag to origin")
            print("GitHub Actions will now build and publish the release automatically")
            print("Monitor the workflow at: https://github.com/anjor/pltr-cli/actions")
        else:
            print("Not pushing to origin. You can push manually later with:")
            print("  git push origin HEAD")
            print(f"  git push origin {tag_name}")


def bump_version(current_version, bump_type):
    """Bump version based on type"""
    parts = current_version.split(".")
    if len(parts) != 3:
        print(
            f"Error: Current version '{current_version}' is not in semantic version format"
        )
        sys.exit(1)

    major, minor, patch = map(int, parts)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        print(f"Error: Invalid bump type '{bump_type}'. Use: major, minor, or patch")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Create a release for pltr-cli")
    parser.add_argument("--version", help="Specific version to release (e.g., 1.0.0)")
    parser.add_argument(
        "--type",
        choices=["major", "minor", "patch"],
        help="Version bump type (alternative to --version)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip all confirmation prompts (non-interactive mode)",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push to origin without asking (requires --yes)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push to origin (useful for testing)",
    )

    args = parser.parse_args()

    # Validate argument combinations
    if args.push and args.no_push:
        print("Error: Cannot specify both --push and --no-push")
        sys.exit(1)

    if args.push and not args.yes:
        print("Error: --push requires --yes (non-interactive mode)")
        sys.exit(1)

    # Ensure we're in a git repository
    try:
        run_git_command("git rev-parse --git-dir")
    except subprocess.CalledProcessError:
        print("Error: Not in a git repository")
        sys.exit(1)

    # Get current version
    current_version = get_current_version()
    print(f"Current version: {current_version}")

    # Determine new version
    if args.version and args.type:
        print("Error: Cannot specify both --version and --type")
        sys.exit(1)
    elif args.version:
        new_version = args.version
        validate_version(new_version)
        release_type = "release"
    elif args.type:
        new_version = bump_version(current_version, args.type)
        release_type = args.type
    else:
        print("Error: Must specify either --version or --type")
        sys.exit(1)

    print(f"New version: {new_version}")

    # Check if we're trying to release the same version
    if new_version == current_version:
        print(f"\nWarning: Version {new_version} is the same as current version.")
        print("This will create a new commit and tag for the same version.")
        if not args.yes:
            confirm_same = input("Continue anyway? (y/N): ").strip().lower()
            if confirm_same not in ["y", "yes"]:
                print("Release cancelled")
                sys.exit(0)

    if args.dry_run:
        print("\nDry run mode - would perform these actions:")
        print(f"1. Update pyproject.toml version to {new_version}")
        print(f"2. Update src/pltr/__init__.py __version__ to {new_version}")
        print("3. Update uv.lock file")
        print(f"4. Create git commit: '{release_type}: Release version {new_version}'")
        print(f"5. Create git tag: v{new_version}")
        print("6. Optionally push to origin")
        return

    # Check git status
    check_git_status()

    # Check if tag already exists
    if check_tag_exists(new_version):
        if not args.yes:
            confirm_tag = (
                input(f"Tag v{new_version} already exists. Continue anyway? (y/N): ")
                .strip()
                .lower()
            )
            if confirm_tag not in ["y", "yes"]:
                print("Release cancelled")
                sys.exit(0)
        else:
            print(f"Continuing despite existing tag v{new_version} (--yes specified)")

    # Confirm release
    print(f"\nAbout to create release {new_version}")
    print("This will:")
    print(f"1. Update pyproject.toml version to {new_version}")
    print(f"2. Update src/pltr/__init__.py __version__ to {new_version}")
    print("3. Update uv.lock file")
    print(f"4. Create git commit and tag v{new_version}")
    if args.push:
        print("5. Push to origin to trigger GitHub Actions publishing")
    elif args.no_push:
        print("5. NOT push to origin (--no-push specified)")
    else:
        print("5. Optionally push to trigger GitHub Actions publishing")

    if not args.yes:
        confirm = input("\nProceed with release? (y/N): ").strip().lower()
        if confirm not in ["y", "yes"]:
            print("Release cancelled")
            sys.exit(0)
    else:
        print("\nProceeding with release (--yes specified)...")

    # Determine push mode
    if args.push:
        push_mode = "force"
    elif args.no_push:
        push_mode = "no"
    else:
        push_mode = "ask"

    # Perform release
    update_version_in_pyproject(new_version)
    update_version_in_init_py(new_version)
    update_uv_lock()  # Update uv.lock with new version
    create_release_commit_and_tag(new_version, release_type, push_mode)

    print(f"\n✅ Release {new_version} created successfully!")


if __name__ == "__main__":
    main()
