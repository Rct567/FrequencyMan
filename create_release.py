import fnmatch
import os
import re
import shutil
import subprocess
import sys
from typing import NoReturn, Optional
import zipfile


def copy_directory(src: str, dst: str, ignore_patterns: list[str]) -> None:

    for item in os.listdir(src):
        src_item = os.path.join(src, item)
        dst_item = os.path.join(dst, item)

        if any(fnmatch.fnmatch(item, pattern) for pattern in ignore_patterns):
            continue

        if os.path.isdir(src_item) and any(fnmatch.fnmatch(item+"/", pattern) for pattern in ignore_patterns):
            continue

        if item.startswith("."):
            continue

        if os.path.isfile(src_item):
            if not os.path.exists(dst):
                os.makedirs(dst)
            shutil.copy2(src_item, dst_item)
        elif os.path.isdir(src_item):
            if os.path.abspath(src_item) != os.path.abspath(dst_item):
                if not os.path.exists(dst_item):
                    os.makedirs(dst_item)
                copy_directory(src_item, dst_item, ignore_patterns)


def ignore_patterns_from_gitignore_file(src: str) -> list[str]:
    gitignore_path = os.path.join(src, '.gitignore')
    ignore_patterns = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.append(line)

    return ignore_patterns


def is_valid_version(version: str) -> bool:
    pattern = r"^(\d+\.)?(\d+\.)?(\*|\d+)$"
    return bool(re.match(pattern, version))


def set_release_version(src_dir: str) -> Optional[str]:
    provided_version_number = input("Version number? ")
    if not is_valid_version(provided_version_number):
        return None

    file_with_version = os.path.join(src_dir, 'frequencyman', 'version.py')

    if os.path.exists(file_with_version):
        with open(file_with_version, "r") as file:
            current_content = file.read()
        if provided_version_number in current_content:
            print("Version given is the current version!")
            return None

    with open(file_with_version, "w") as file:
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


def run_nox_with_success() -> bool:

    print("Running nox...")

    result = subprocess.run(["nox"], capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr)
        return False

    print("Nox was successful!")
    return True

def run_mypy_with_success() -> bool:

    print("Running mypy...")

    result_init_file = subprocess.run(["mypy", ".\\__init__.py", "--ignore-missing-imports"], capture_output=True, text=True)

    if result_init_file.returncode != 0:
        print(result_init_file.stdout)
        return False

    result_main = subprocess.run(["mypy"], capture_output=True, text=True)

    if result_main.returncode != 0:
        print(result_main.stdout)
        return False

    print("Mypy was successful!")
    return True


def create_zip(directory: str, zip_file: str) -> None:

    with zipfile.ZipFile(zip_file, 'w') as zf:
        for root, _, files in os.walk(directory):
            for file in files:
                zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), directory))


def print_and_exit_error(message: str) -> NoReturn:
    print(message)
    sys.exit(1)



# create release

if has_unstaged_changes():
    print_and_exit_error("You have unstaged changes, please commit or stash them before creating a release!")

if has_staged_changes():
     print_and_exit_error("You have staged changes, please commit or stash them before creating a release!")


root_dir = os.getcwd()
releases_dir = os.path.join(root_dir, 'releases')

new_release_src_dir = root_dir

if not os.path.exists(releases_dir):
    os.mkdir(releases_dir)

if not run_mypy_with_success():
    print_and_exit_error("Mypy failed!")

if not run_nox_with_success():
    print_and_exit_error("Nox failed!")


new_release_version = set_release_version(new_release_src_dir)

if not new_release_version:
    print_and_exit_error("Failed to set new release version!")

new_release_obj_name = 'release-v'+new_release_version.replace('.', '_')
new_release_dst_dir = os.path.join(releases_dir, new_release_obj_name)

if os.path.exists(new_release_dst_dir):
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
    'noxfile.py'
])

copy_directory(new_release_src_dir, new_release_dst_dir, ignore_patterns)

release_zip_file = os.path.join(releases_dir, new_release_obj_name+'.ankiaddon')
create_zip(new_release_dst_dir, release_zip_file)

print("Done!")

commit_tag_push = input("Use GIT to commit, tag and push to v{}? (Y/N) ".format(new_release_version))
if commit_tag_push.lower() == "y":
    commit_and_tag(new_release_version)
    print("New version committed!")
    print("\nNext step:\nCreate a new release on Github: https://github.com/Rct567/FrequencyMan/releases/new")
else:
    print("Skipped commit, tag and push...")
