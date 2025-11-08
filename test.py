"""Test runner script that checks Python version and runs tests with pytest or nox."""

import subprocess
import sys
from typing import NoReturn


def check_python_version() -> None:
    """Check if Python 3.9 or higher is installed."""
    if sys.version_info < (3, 9):
        print(f"Error: Python 3.9 or higher is required.")
        print(f"Current version: {sys.version}")
        sys.exit(1)


def is_package_installed(package: str) -> bool:
    """Check if a Python package is installed."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def install_package(package: str) -> None:
    """Install a Python package using pip."""
    print(f"Installing {package}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            check=True
        )
        print(f"✓ {package} installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package}: {e}")
        sys.exit(1)


def ensure_packages_installed(packages: list[str]) -> None:
    """Ensure all required packages are installed."""
    for package in packages:
        if not is_package_installed(package):
            print(f"✗ {package} is not installed")
            install_package(package)


def run_pytest() -> None:
    """Run pytest with the current Python version."""
    print("\n" + "="*60)
    print("Running pytest with current Python version...")
    print("="*60 + "\n")

    ensure_packages_installed(["pytest"])

    # Check if requirements-dev.txt exists and install from it
    try:
        with open("requirements-dev.txt", "r") as _:
            print("Found requirements-dev.txt, installing dependencies...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
                check=True,
                capture_output=True
            )
    except FileNotFoundError:
        print("No requirements-dev.txt found, skipping...")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to install requirements-dev.txt: {e}")

    try:
        subprocess.run([sys.executable, "-m", "pytest", "tests/"], check=True)
    except subprocess.CalledProcessError:
        sys.exit(1)


def run_nox() -> None:
    """Run tests across multiple Python versions using nox."""
    print("\n" + "="*60)
    print("Running tests across multiple Python versions with nox...")
    print("="*60 + "\n")

    ensure_packages_installed(["nox", "uv"])

    try:
        subprocess.run(["nox"], check=True)
    except subprocess.CalledProcessError:
        sys.exit(1)


def get_user_choice() -> str:
    """Prompt user to choose between pytest and nox."""
    print("\n" + "="*60)
    print("Test Runner Options:")
    print(" 1. Run pytest with current Python version ({}.{})".format(sys.version_info.major, sys.version_info.minor))
    print(" 2. Test all Python versions using nox (3.9, 3.11, 3.13)")
    print("="*60)

    while True:
        choice = input("\nEnter your choice (1 or 2): ").strip()
        if choice in ["1", "2"]:
            return choice
        print("Invalid choice. Please enter 1 or 2.")


def main() -> NoReturn:
    """Main entry point for the test runner."""
    print(" "*60)
    print("Python Test Runner")
    print("="*60 + "\n")

    check_python_version()

    choice = get_user_choice()

    if choice == "1":
        run_pytest()
    else:
        run_nox()

    print("\n" + "="*60)
    print("✓ Tests completed successfully!")
    print("="*60)
    sys.exit(0)


if __name__ == "__main__":
    main()