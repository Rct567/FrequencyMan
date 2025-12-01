"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import time
from typing import NoReturn, Callable, Optional
from dataclasses import dataclass

GREEN = "\033[92m"
RESET = "\033[0m"


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_TARGET_FOLDER: list[Path] = [PROJECT_ROOT / dir for dir in ["tests", "scripts", "frequencyman"]]

assert all(dir.is_dir() for dir in TEST_TARGET_FOLDER)

def relative_path(path: Path) -> str:
    return "./{}".format(path.relative_to(PROJECT_ROOT))


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
                print(f"{GREEN} Installation successful.{RESET}")
                if result.stdout:
                    print(result.stdout)
            else:
                print(" Nothing to install.")
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
        print(f"{GREEN} {package} installed successfully{RESET}")
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

    print(" > " + " ".join(cmd))

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
    print("Running pytest with local Python version...")
    start_time = time.perf_counter()

    ensure_packages_installed(["pytest"])
    run_and_print_on_failure(["pytest"], "Pytest")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN}Pytest was successful! ({elapsed_time:.0f} seconds){RESET}")

def run_nox() -> None:
    """Run tests across multiple Python versions using nox."""
    print("=" * 60)
    print("Running nox (tests across multiple Python versions)...")
    start_time = time.perf_counter()

    ensure_packages_installed(["nox", "uv"])
    run_and_print_on_failure(["nox", "--stop-on-first-error"], "Nox")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN}Nox was successful! ({elapsed_time:.0f} seconds){RESET}")

def run_tox() -> None:
    """Run tests across multiple Python versions using nox."""
    print("=" * 60)
    print("Running tox (tests across multiple Python versions in parallel)...")
    start_time = time.perf_counter()

    ensure_packages_installed(["tox"])
    run_and_print_on_failure(["tox", "--parallel", "auto"], "Tox")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN}Tox was successful! ({elapsed_time:.0f} seconds){RESET}")

def run_mypy() -> None:
    """Run mypy."""
    print("="*60)
    print("Running mypy...")
    start_time = time.perf_counter()

    ensure_packages_installed(["mypy"])

    root_files_to_run = [
        relative_path(py_file)
        for py_file in PROJECT_ROOT.glob('*.py')
        if py_file.name != "__init__.py"
    ]
    run_and_print_on_failure(["mypy"] + [relative_path(dir) for dir in TEST_TARGET_FOLDER] + root_files_to_run, "Mypy")

    run_and_print_on_failure(["mypy", "./__init__.py", "--ignore-missing-imports"], "Mypy")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN} Mypy was successful! ({elapsed_time:.0f} seconds){RESET}")


def run_ruff() -> None:
    """Run ruff."""
    print("=" * 60)
    print("Running ruff...")
    start_time = time.perf_counter()

    ensure_packages_installed(["ruff"])
    run_and_print_on_failure(["ruff", "check"] + [relative_path(dir) for dir in TEST_TARGET_FOLDER] + ["--preview"], "Ruff")

    root_files_to_run = [relative_path(py_file) for py_file in PROJECT_ROOT.glob('*.py')]
    run_and_print_on_failure(["ruff", "check"] + root_files_to_run + ["--preview"], "Ruff")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN} Ruff was successful! ({elapsed_time:.0f} seconds){RESET}")

def run_pyright() -> None:
    """Run pyright."""
    print("=" * 60)
    print("Running pyright...")
    start_time = time.perf_counter()

    ensure_packages_installed(["pyright"])
    run_and_print_on_failure(["pyright"] + [relative_path(dir) for dir in TEST_TARGET_FOLDER], "Pyright")

    root_files_to_run = [relative_path(py_file) for py_file in PROJECT_ROOT.glob('*.py')]
    run_and_print_on_failure(["pyright"] + root_files_to_run, "Pyright")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN} Pyright was successful! ({elapsed_time:.0f} seconds){RESET}")

@dataclass(frozen=True)
class MenuTestOption:
    key: str
    description: str
    action: Callable[[], None]
    available: Optional[Callable[[], bool]] = None

    def is_available(self) -> bool:
        return self.available() if self.available is not None else True

def get_test_menu_options() -> list[MenuTestOption]:
    return [
        MenuTestOption(
            key="pytest",
            description="Run pytest with local Python version ({}.{})".format(
                sys.version_info.major, sys.version_info.minor
            ),
            action=run_pytest,
        ),
        MenuTestOption(
            key="nox",
            description="Test multiple Python versions using nox (3.9, 3.11, 3.13)",
            action=run_nox,
        ),
        MenuTestOption(
            key="tox",
            description="Test multiple Python versions in parallel using tox (3.9, 3.11, 3.13)",
            action=run_tox,
            available=lambda: is_package_installed("tox") and is_package_installed("tox-uv"),
        ),
    ]

def parse_cli_choice() -> Optional[str]:
    args = sys.argv[1:]
    for arg in args:
        if arg == "-y":
            return "nox"
        if arg.startswith("--"):
            key = arg[2:]
            for opt in get_test_menu_options():
                if opt.key == key and opt.is_available():
                    return key
    return None

def get_user_choice() -> str:
    print("="*60)
    print("Test Runner Options:")

    menu_options = [option for option in get_test_menu_options() if option.is_available()]
    for i, opt in enumerate(menu_options, start=1):
        print(" {}. {} -- {}".format(i, opt.key, opt.description))

    valid_indices = [str(i) for i in range(1, len(menu_options) + 1)]
    while True:
        choices_num_str = ", ".join(valid_indices)
        if len(valid_indices) > 1:
            choices_num_str = choices_num_str.replace(
                ", {}".format(valid_indices[-1]), " or {}".format(valid_indices[-1])
            )
        choice = input("\nEnter your choice ({}): ".format(choices_num_str)).strip()
        if choice in valid_indices:
            return menu_options[int(choice) - 1].key
        for opt in menu_options:
            if choice.lower() == opt.key.lower():
                return opt.key
        print("Invalid choice. Please enter {}.".format(choices_num_str))


def main() -> NoReturn:
    print(" "*60)
    print("FrequencyMan Test Runner")

    start_time = time.perf_counter()

    check_python_version()
    install_dev_requirements()

    run_ruff()
    run_pyright()
    run_mypy()

    parsed_choice = parse_cli_choice()
    non_interactive = parsed_choice is not None
    choice_key = parsed_choice if parsed_choice is not None else get_user_choice()

    options_by_key = {opt.key: opt for opt in get_test_menu_options()}
    selected = options_by_key.get(choice_key)
    if selected is None or not selected.is_available():
        raise Exception("Invalid choice.")
    selected.action()

    elapsed_time = time.perf_counter() - start_time

    print("\n" + "="*60)
    if non_interactive:
        print(f"{GREEN} All tests completed successfully! ({elapsed_time:.0f} seconds){RESET}")
    else:
        print(f"{GREEN} All tests completed successfully!{RESET}")
    print("="*60)
    sys.exit(0)


if __name__ == "__main__":
    main()
