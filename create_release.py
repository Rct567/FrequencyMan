import fnmatch
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import NoReturn, Optional
import zipfile


def copy_directory(src: Path, dst: Path, ignore_patterns: list[str]) -> None:

    for item in src.iterdir():
        src_item = item
        dst_item = dst / item.name

        if any(fnmatch.fnmatch(item.name, pattern) for pattern in ignore_patterns):
            continue

        if src_item.is_dir() and any(fnmatch.fnmatch(item.name+"/", pattern) for pattern in ignore_patterns):
            continue

        if item.name.startswith("."):
            continue

        if src_item.is_file():
            if not dst.exists():
                dst.mkdir(parents=True)
            shutil.copy2(src_item, dst_item)
        elif src_item.is_dir():
            if src_item.resolve() != dst_item.resolve():
                if not dst_item.exists():
                    dst_item.mkdir(parents=True)
                copy_directory(src_item, dst_item, ignore_patterns)


def ignore_patterns_from_gitignore_file(src: Path) -> list[str]:
    gitignore_path = src / '.gitignore'
    ignore_patterns = []
    if gitignore_path.exists():
        with gitignore_path.open('r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.append(line)

    return ignore_patterns


def is_valid_version(version: str) -> bool:
    pattern = r"^(\d+\.)?(\d+\.)?(\*|\d+)$"
    return bool(re.match(pattern, version))


def set_release_version(src_dir: Path) -> Optional[str]:
    provided_version_number = input("Version number? ")
    if not is_valid_version(provided_version_number):
        return None

    file_with_version = src_dir / 'frequencyman' / 'version.py'

    if file_with_version.exists():
        with file_with_version.open("r") as file:
            current_content = file.read()
        if provided_version_number in current_content:
            print("Version given is the current version!")
            return None

    with file_with_version.open("w") as file:
        file.write('FREQUENCYMAN_VERSION = "{}"'.format(provided_version_number))
    return provided_version_number


def commit_and_tag(version_number: str) -> None:

    git_tag = "v"+version_number

    # Commit changes with a message
    subprocess.run(["git", "commit", "-a", f"-m \"upgraded version to {version_number}\""], check=True)

    # Push changes to remote repository
    subprocess.run(["git", "push"], check=True)

    # Create a new tag with a message
    subprocess.run(["git", "tag", "-a", git_tag, f"-m \"version {git_tag}\""], check=True)

    # Push the new tag to remote repository
    subprocess.run(["git", "push", "origin", git_tag], check=True)


def has_unstaged_changes() -> bool:
    result = subprocess.run(["git", "diff", "--exit-code"], capture_output=True)
    return result.returncode != 0

def has_staged_changes() -> bool:
    result = subprocess.run(["git", "diff", "--cached", "--exit-code"], capture_output=True)
    return result.returncode != 0


def run_all_tests_with_success() -> bool:

    print("Running tests...")

    result = subprocess.run(["python", "test.py", "--nox"], capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr if result.stderr else result.stdout)
        return False

    print(" All tests completed successfully!")
    return True


def create_zip(directory: Path, zip_file: Path) -> None:

    import os
    with zipfile.ZipFile(zip_file, 'w') as zf:
        for root, _, files in os.walk(directory):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                zf.write(file_path, file_path.relative_to(directory))


def print_and_exit_error(message: str) -> NoReturn:
    print(message)
    sys.exit(1)


# create release

if has_unstaged_changes():
    print_and_exit_error("You have unstaged changes, please commit or stash them before creating a release!")

if has_staged_changes():
     print_and_exit_error("You have staged changes, please commit or stash them before creating a release!")


root_dir = Path.cwd()
releases_dir = root_dir / 'releases'

new_release_src_dir = root_dir

if not releases_dir.exists():
    releases_dir.mkdir()


if not run_all_tests_with_success():
    print_and_exit_error("Tests failed!")


new_release_version = set_release_version(new_release_src_dir)

if not new_release_version:
    print_and_exit_error("Failed to set new release version!")

new_release_obj_name = 'release-v'+new_release_version.replace('.', '_')
new_release_dst_dir = releases_dir / new_release_obj_name

if new_release_dst_dir.exists():
    print_and_exit_error("Release directory '{}' already exists!".format(new_release_dst_dir))

ignore_patterns = ignore_patterns_from_gitignore_file(new_release_src_dir)

ignore_patterns.extend([
    'tests/',
    'pytest.ini',
    'create_release.py',
    'create_default_wf_lists.py',
    'pyproject.toml',
    'requirements-dev.txt',
    'run_pytest_benchmark.py',
    'noxfile.py',
    'test.py',
])

copy_directory(new_release_src_dir, new_release_dst_dir, ignore_patterns)

release_zip_file = releases_dir / (new_release_obj_name + '.ankiaddon')
create_zip(new_release_dst_dir, release_zip_file)

print("Done!")

commit_tag_push = input("Use GIT to commit, tag and push to v{}? (Y/N) ".format(new_release_version))
if commit_tag_push.lower() == "y":
    commit_and_tag(new_release_version)
    print("New version committed!")
    print("\nNext step:\nCreate a new release on Github: https://github.com/Rct567/FrequencyMan/releases/new")
else:
    print("Skipped commit, tag and push...")
