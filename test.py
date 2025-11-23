from pathlib import Path
import subprocess
import sys
import time
from typing import NoReturn


def install_dev_requirements() -> None:
    """Install dev requirements from requirements-dev.txt."""
    print("="*60)
    try:
        with open("requirements-dev.txt", "r", encoding="utf-8"):
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
        print("Error: Python 3.9 or higher is required.")
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
    start_time = time.perf_counter()

    ensure_packages_installed(["pytest"])
    run_and_print_on_failure(["pytest"], "Pytest")

    elapsed_time = time.perf_counter() - start_time
    print("Pytest was successful! ({:.0f} seconds)".format(elapsed_time))

def run_nox() -> None:
    """Run tests across multiple Python versions using nox."""
    print("=" * 60)
    print("Running nox (tests across multiple Python versions)...")
    start_time = time.perf_counter()

    ensure_packages_installed(["nox", "uv"])
    run_and_print_on_failure(["nox", "--stop-on-first-error"], "Nox")

    elapsed_time = time.perf_counter() - start_time
    print("Nox was successful! ({:.0f} seconds)".format(elapsed_time))

def run_tox() -> None:
    """Run tests across multiple Python versions using nox."""
    print("=" * 60)
    print("Running tox (tests across multiple Python versions in parallel)...")
    start_time = time.perf_counter()

    ensure_packages_installed(["tox"])
    run_and_print_on_failure(["tox", "--parallel", "auto"], "Tox")

    elapsed_time = time.perf_counter() - start_time
    print("Tox was successful! ({:.0f} seconds)".format(elapsed_time))

def run_mypy() -> None:
    """Run mypy."""
    print("="*60)
    print("Running mypy...")
    start_time = time.perf_counter()

    ensure_packages_installed(["mypy"])

    for py_file in Path(__file__).parent.glob('*.py'):
        if py_file.name == "__init__.py":
            run_and_print_on_failure(["mypy", ".\\{}".format(py_file.name), "--ignore-missing-imports"], "Mypy")
        else:
            run_and_print_on_failure(["mypy", ".\\{}".format(py_file.name)], "Mypy")

    run_and_print_on_failure(["mypy"], "Mypy")

    elapsed_time = time.perf_counter() - start_time
    print(" Mypy was successful! ({:.0f} seconds)".format(elapsed_time))


def run_ruff() -> None:
    """Run ruff."""
    print("=" * 60)
    print("Running ruff...")
    start_time = time.perf_counter()

    ensure_packages_installed(["ruff"])
    run_and_print_on_failure(["ruff", "check", ".\\frequencyman", ".\\tests", "--preview"], "Ruff")

    for py_file in Path(__file__).parent.glob('*.py'):
        run_and_print_on_failure(["ruff", "check", str(py_file), "--preview"], "Ruff")

    elapsed_time = time.perf_counter() - start_time
    print(" Ruff was successful! ({:.0f} seconds)".format(elapsed_time))

def run_pyright() -> None:
    """Run pyright."""
    print("=" * 60)
    print("Running pyright...")
    start_time = time.perf_counter()

    ensure_packages_installed(["pyright"])
    run_and_print_on_failure(["pyright", "frequencyman", "tests"], "Pyright")

    for py_file in Path(__file__).parent.glob('*.py'):
        run_and_print_on_failure(["pyright", str(py_file)], "Pyright")

    elapsed_time = time.perf_counter() - start_time
    print(" Pyright was successful! ({:.0f} seconds)".format(elapsed_time))

def get_user_choice() -> str:
    print("="*60)
    print("Test Runner Options:")

    choices: dict[str, str] = {
        "1":  "pytest -- Run pytest with current Python version ({}.{})".format(sys.version_info.major, sys.version_info.minor),
        "2": "nox -- Test multiple Python versions using nox (3.9, 3.11, 3.13)"
    }

    if is_package_installed("tox") and is_package_installed("tox-uv"):
        choices["3"] = "tox -- Test multiple Python versions in parallel using tox (3.9, 3.11, 3.13)"

    for choice, description in choices.items():
        print(" {}. {}".format(choice, description))

    while True:
        choices_num_str = ", ".join(choices.keys())
        choices_num_str = choices_num_str.replace(", {}".format(len(choices)), " or {}".format(len(choices)))
        choice = input("\nEnter your choice ({}): ".format(choices_num_str).strip())
        if choice in choices:
            return choice
        print("Invalid choice. Please enter {}.".format(choices_num_str))


def main() -> NoReturn:
    print(" "*60)
    print("FrequencyMan Test Runner")

    start_time = time.perf_counter()

    check_python_version()
    install_dev_requirements()
    run_mypy()
    if is_package_installed("pyright"):
        run_pyright()
    run_ruff()

    use_nox_to_test = len(sys.argv) > 1 and (sys.argv[1] == "-y" or sys.argv[1] == "--nox")

    if use_nox_to_test:
        choice = "2"
    else:
        choice = get_user_choice()

    if choice == "1":
        run_pytest()
    elif choice == "2":
        run_nox()
    elif choice == "3" and is_package_installed("tox"):
        run_tox()
    else:
        raise Exception("Invalid choice.")

    elapsed_time = time.perf_counter() - start_time

    print("\n" + "="*60)
    if use_nox_to_test:
        print(" All tests completed successfully! ({:.0f} seconds)".format(elapsed_time))
    else:
        print(" All tests completed successfully!")
    print("="*60)
    sys.exit(0)


if __name__ == "__main__":
    main()