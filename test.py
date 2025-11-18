import subprocess
import sys
from typing import NoReturn


def install_dev_requirements() -> None:
    """Install dev requirements from requirements-dev.txt."""
    print("="*60)
    try:
        with open("requirements-dev.txt", "r") as _:
            print("Found requirements-dev.txt, installing dependencies...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
                check=True,
                capture_output=True,
                text=True
            )
            if "installed" in result.stdout:
                print(" Installation successful.")
                if result.stdout:
                    print(result.stdout)
            else:
                print(" Done.")
    except FileNotFoundError:
        print(" No requirements-dev.txt found.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f" Failed to install requirements-dev.txt: {e}")
        sys.exit(1)

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
    print(f" Installing {package}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            check=True
        )
        print(f" {package} installed successfully")
    except subprocess.CalledProcessError as e:
        print(f" Error installing {package}: {e}")
        sys.exit(1)


def ensure_packages_installed(packages: list[str]) -> None:
    """Ensure all required packages are installed."""
    for package in packages:
        if not is_package_installed(package):
            print(f" {package} is not installed")
            install_package(package)


def run_and_print_on_failure(cmd: list[str], fail_label: str) -> None:
    """
    Run `cmd`. If it fails, print stdout/stderr (if present) and exit with the subprocess return code.
    """

    print(" > "+"".join(part+" " for part in cmd))

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(" {} failed.".format(fail_label))
        if e.stdout:
            print(" stdout:\n{}".format(e.stdout))
        if e.stderr:
            print(" stderr:\n{}".format(e.stderr))
        # propagate the exit code from the subprocess
        sys.exit(e.returncode)

def run_pytest() -> None:
    """Run pytest with the current Python version."""
    print("=" * 60)
    print("Running pytest with current Python version...")

    ensure_packages_installed(["pytest"])
    run_and_print_on_failure(["pytest"], "Pytest")

def run_nox() -> None:
    """Run tests across multiple Python versions using nox."""
    print("=" * 60)
    print("Running tests across multiple Python versions with nox...")

    ensure_packages_installed(["nox", "uv"])
    run_and_print_on_failure(["nox", "--stop-on-first-error"], "Nox")

    print("Nox was successful!")

def run_mypy() -> None:

    print("="*60)
    print("Running mypy...")

    ensure_packages_installed(["mypy"])
    run_and_print_on_failure(["mypy", ".\\__init__.py", "--ignore-missing-imports"], "Mypy")
    run_and_print_on_failure(["mypy"], "Mypy")

    print(" Mypy was successful!")



def get_user_choice() -> str:
    print("="*60)
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
    print(" "*60)
    print("Python Test Runner")

    check_python_version()
    install_dev_requirements()
    run_mypy()

    if len(sys.argv) > 1 and (sys.argv[1] == "-y" or sys.argv[1] == "--nox"):
        choice = "2"
    else:
        choice = get_user_choice()

    if choice == "1":
        run_pytest()
    else:
        run_nox()

    print("\n" + "="*60)
    print(" All tests completed successfully!")
    print("="*60)
    sys.exit(0)


if __name__ == "__main__":
    main()