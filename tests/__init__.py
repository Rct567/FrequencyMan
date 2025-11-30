import sys
import os

# Force offscreen Qt platform for tests to avoid display issues
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Ensure the project root is in sys.path so that 'frequencyman' package can be imported
# This is critical when running tests as a package (e.g. pytest tests/)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Check if we can import frequencyman.language_data (from the frequencyman/ subdirectory)
# If not, we need to add project_root to sys.path

try:

    import frequencyman.language_data # noqa: F401

except (ImportError, ModuleNotFoundError):

    if project_root not in sys.path:

        print(f"Adding {project_root} to sys.path")
        sys.path.insert(0, project_root)

    else:

        print(f"{project_root} already in sys.path")

        # If project_root is in sys.path but import still fails,
        # it means 'frequencyman' is resolving to the wrong module (root __init__.py)
        # Remove it from sys.modules and try again

        if "frequencyman" in sys.modules:
            del sys.modules["frequencyman"]

        # Also remove any frequencyman.* submodules

        to_remove = [key for key in sys.modules.keys() if key.startswith("frequencyman.")]

        for key in to_remove:
            del sys.modules[key]
