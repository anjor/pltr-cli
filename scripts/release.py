#!/usr/bin/env python3
"""
Release script for pltr-cli

Usage:
    python scripts/release.py --version 0.1.1 --type patch
    python scripts/release.py --version 0.2.0 --type minor
    python scripts/release.py --version 1.0.0 --type major
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


def create_release_commit_and_tag(version, release_type):
    """Create release commit and tag"""
    # Stage the pyproject.toml changes
    run_git_command("git add pyproject.toml")

    # Create release commit
    commit_message = f"{release_type}: Release version {version}"
    run_git_command(f'git commit -m "{commit_message}"')
    print(f"Created release commit: {commit_message}")

    # Create and push tag
    tag_name = f"v{version}"
    run_git_command(f'git tag -a {tag_name} -m "Release {version}"')
    print(f"Created tag: {tag_name}")

    # Ask user if they want to push
    push_choice = (
        input(f"Push commit and tag '{tag_name}' to origin? (y/N): ").strip().lower()
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

    args = parser.parse_args()

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

    if args.dry_run:
        print("\nDry run mode - would perform these actions:")
        print(f"1. Update pyproject.toml version to {new_version}")
        print(f"2. Create git commit: '{release_type}: Release version {new_version}'")
        print(f"3. Create git tag: v{new_version}")
        print("4. Optionally push to origin")
        return

    # Check git status
    check_git_status()

    # Confirm release
    print(f"\nAbout to create release {new_version}")
    print("This will:")
    print(f"1. Update pyproject.toml version to {new_version}")
    print(f"2. Create git commit and tag v{new_version}")
    print("3. Optionally push to trigger GitHub Actions publishing")

    confirm = input("\nProceed with release? (y/N): ").strip().lower()
    if confirm not in ["y", "yes"]:
        print("Release cancelled")
        sys.exit(0)

    # Perform release
    update_version_in_pyproject(new_version)
    create_release_commit_and_tag(new_version, release_type)

    print(f"\n✅ Release {new_version} created successfully!")


if __name__ == "__main__":
    main()
