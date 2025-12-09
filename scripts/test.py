"""
FrequencyMan by Rick Zuidhoek. Licensed under the GNU GPL-3.0.
See <https://www.gnu.org/licenses/gpl-3.0.html> for details.
"""

from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import time
from typing import NoReturn, Callable, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from collections.abc import Sequence

GREEN = "\033[92m"
RESET = "\033[0m"


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_TARGET_FOLDER: list[Path] = [PROJECT_ROOT / dir for dir in ["tests", "scripts", "frequencyman"]]

assert all(dir.is_dir() for dir in TEST_TARGET_FOLDER)


def relative_path(path: Path) -> str:
    return "./{}".format(path.relative_to(PROJECT_ROOT))


def get_staged_python_files() -> list[str]:
    """Get list of staged Python files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True
        )
        staged_files = result.stdout.strip().split('\n')
        python_files = [f for f in staged_files if f.endswith('.py')]
        return python_files
    except subprocess.CalledProcessError:
        # If git command fails (e.g., not in a git repo), return empty list
        return []


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


def check_staged_files(command_prefix: list[str], tool_name: str) -> bool:
    """Run a command on all staged Python files."""
    staged_files = get_staged_python_files()
    if staged_files:
        print(f"Checking {len(staged_files)} staged Python file(s) with {tool_name}")
        run_and_print_on_failure(command_prefix + staged_files, tool_name)
        return True
    else:
        print(f"No staged Python files found, skipping {tool_name}")
        return False

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


def things_to_type_check() -> list[str]:

    root_dirs = [relative_path(dir) for dir in TEST_TARGET_FOLDER]
    root_files_to_run = [relative_path(py_file) for py_file in PROJECT_ROOT.glob('*.py')]
    return root_dirs + root_files_to_run


def run_mypy(options: Sequence[str]) -> None:
    """Run mypy."""
    print("="*60)
    print("Running mypy...")
    start_time = time.perf_counter()

    ensure_packages_installed(["mypy"])

    if "staged" in options:
        check_staged_files(["mypy"], "mypy")
    else:
        run_and_print_on_failure(["mypy"] + things_to_type_check(),  "Mypy")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN} Mypy was successful! ({elapsed_time:.0f} seconds){RESET}")


def run_ruff(options: Sequence[str]) -> None:
    """Run ruff."""
    print("=" * 60)
    print("Running ruff...")
    start_time = time.perf_counter()

    ensure_packages_installed(["ruff"])

    if "staged" in options:
        check_staged_files(["ruff", "check"], "ruff")
    else:
        run_and_print_on_failure(["ruff", "check"] + things_to_type_check(), "Ruff")

    elapsed_time = time.perf_counter() - start_time
    print(f"{GREEN} Ruff was successful! ({elapsed_time:.0f} seconds){RESET}")


def run_pyright(options: Sequence[str]) -> None:
    """Run pyright."""
    print("=" * 60)
    print("Running pyright...")
    start_time = time.perf_counter()

    ensure_packages_installed(["pyright"])

    if "staged" in options:
        check_staged_files(["pyright"], "pyright")
    else:
        run_and_print_on_failure(["pyright"] + things_to_type_check(), "Pyright")

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

def parse_cli_args() -> list[str]:
    """Parse CLI arguments and return (choice, options_set)."""
    args = sys.argv[1:]

    selected_options = []

    for arg in args:
        if arg == "-y":
            selected_options.append("nox")
        elif arg == "--pytest":
            selected_options.append("pytest")
        elif arg == "--staged":
            selected_options.append("staged")
            selected_options.insert(0, "pytest")
        elif arg.startswith("--"):
            key = arg[2:]
            for opt in get_test_menu_options():
                if opt.key == key and opt.is_available():
                    selected_options.append(key)
                    break

    return selected_options

def get_user_choice() -> MenuTestOption:
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
            return menu_options[int(choice) - 1]
        for opt in menu_options:
            if choice.lower() == opt.key.lower():
                return opt
        print("Invalid choice. Please enter {}.".format(choices_num_str))


def main() -> NoReturn:
    print(" "*60)
    print("FrequencyMan Test Runner")

    start_time = time.perf_counter()

    check_python_version()
    install_dev_requirements()

    # Parse CLI arguments early so flags like --staged are set before running checks
    selected_options = parse_cli_args()

    run_ruff(selected_options)
    run_pyright(selected_options)
    run_mypy(selected_options)

    selected_menu_options = [option for option in get_test_menu_options() if option.is_available() and option.key in selected_options]

    if len(selected_menu_options) == 0:
        selected = get_user_choice()
    else:
        selected = selected_menu_options[0]

    selected.action() # run the selected menu option

    elapsed_time = time.perf_counter() - start_time

    print("\n" + "="*60)
    print(f"{GREEN} All tests completed successfully! ({elapsed_time:.0f} seconds){RESET}")
    print("="*60)
    sys.exit(0)


if __name__ == "__main__":
    main()
