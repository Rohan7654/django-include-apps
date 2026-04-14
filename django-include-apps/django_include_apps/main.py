import os
import re
import shutil
import subprocess
import sys
import json
from datetime import datetime
import requests
from pathlib import Path
import inquirer
import typer
from typing import List, Set, Optional
from importlib.metadata import PackageNotFoundError, version

# Ensure UTF-8 output on Windows (prevents cp1252 encoding errors with Unicode chars)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    help="Intelligently manage Django apps in INSTALLED_APPS with smart package mapping and automatic configuration.",
    context_settings={"help_option_names": ["-h", "--help"]}
)

# Get version from package metadata
try:
    __version__ = version("django-include-apps")
except PackageNotFoundError:
    __version__ = "1.1.2"


def version_callback(value: bool):
    """Show version and exit"""
    if value:
        typer.echo(f"django-include-apps version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    Intelligently manage Django apps in INSTALLED_APPS with smart package mapping and automatic configuration.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# ============================================================================
# Core Utility Functions
# ============================================================================


def parse_package_spec(package_spec: str) -> tuple:
    """
    Parse package specification into name and version specifier.

    Handles various version specifiers:
    - djangorestframework -> ('djangorestframework', None)
    - djangorestframework==3.14.0 -> ('djangorestframework', '==3.14.0')
    - django-filter>=2.0 -> ('django-filter', '>=2.0')
    - django-cors-headers~=4.0.0 -> ('django-cors-headers', '~=4.0.0')

    Returns:
        tuple: (package_name, version_spec or None)
    """
    # Pattern to match version specifiers
    pattern = r"^([a-zA-Z0-9\-_.]+)(==|>=|<=|>|<|~=|!=)(.+)$"
    match = re.match(pattern, package_spec)

    if match:
        package_name = match.group(1)
        version_operator = match.group(2)
        version_number = match.group(3)
        version_spec = f"{version_operator}{version_number}"
        return (package_name, version_spec)
    else:
        # No version specifier
        return (package_spec, None)


# ============================================================================
# Core Utility Functions
# ============================================================================


def find_settings_file(start_dir: Path) -> Optional[Path]:
    """Find settings.py file in the project directory"""
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file == "settings.py":
                return Path(root) / file
    return None


def is_package_installed(package_name: str) -> bool:
    """Check if a package is installed in the current environment"""
    try:
        version(package_name)
        return True
    except PackageNotFoundError:
        return False


def install_package(package: str):
    """Install a package using pip"""
    subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)


def is_django_package(package: str) -> bool:
    """Check if package name contains 'django'"""
    return "django" in package.lower()


def is_django_related(package: str) -> bool:
    """Check if a package is related to Django by querying PyPI"""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        if is_django_package(package):
            return True
        else:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            keywords = data.get("info", {}).get("keywords", "")
            if keywords != "":
                if isinstance(keywords, str):
                    return "django" in keywords.lower()
                elif isinstance(keywords, list):
                    return any("django" in keyword.lower() for keyword in keywords)
            else:
                classifiers = data.get("info", {}).get("classifiers", [])
                return any("django" in classifier.lower() for classifier in classifiers)
    except requests.RequestException as e:
        typer.secho(
            f"Error checking package '{package}' on PyPI: {e}", fg=typer.colors.RED
        )
        return False


def is_default_django_app(app_name: str) -> bool:
    """Check if an app is a default Django app (starts with 'django.')"""
    return app_name.startswith("django.")


# ============================================================================
# Package Mapping Functions
# ============================================================================


def _migrate_old_mappings():
    """Migrate old package_mappings.json entries into package_configs.json."""
    old_file = Path(__file__).parent / "package_mappings.json"
    if not old_file.exists():
        return

    try:
        with open(old_file, "r") as f:
            old_mappings = json.load(f)
    except (json.JSONDecodeError, Exception):
        return

    configs = load_package_configs()
    migrated = 0
    for pkg, app_name in old_mappings.items():
        if pkg not in configs:
            configs[pkg] = {"installed_apps": app_name}
            migrated += 1

    if migrated > 0:
        save_package_configs(configs)
        typer.secho(
            f"Migrated {migrated} mapping(s) from package_mappings.json into package_configs.json.",
            fg=typer.colors.BLUE,
        )

    # Remove old file after successful migration
    try:
        old_file.unlink()
    except Exception:
        pass


def load_package_mappings() -> dict:
    """Load package-to-app-name mappings from the unified package_configs.json."""
    # Run one-time migration from old package_mappings.json if it still exists
    _migrate_old_mappings()

    configs = load_package_configs()
    mappings = {}
    for pkg, cfg in configs.items():
        if isinstance(cfg, dict):
            mappings[pkg] = cfg.get("installed_apps")
        else:
            mappings[pkg] = cfg  # fallback for simple entries
    return mappings


def update_package_mappings(package_name: str, app_name: str):
    """Add or update a package-to-app mapping in the unified package_configs.json."""
    configs = load_package_configs()

    # Check if mapping already exists
    if package_name in configs:
        current_value = (
            configs[package_name].get("installed_apps")
            if isinstance(configs[package_name], dict)
            else configs[package_name]
        )

        # If same value, no need to update
        if current_value == app_name:
            typer.secho(
                f"Mapping already exists with same value: {package_name} \u2192 {app_name}",
                fg=typer.colors.CYAN,
            )
            return

        # Ask for confirmation to update
        typer.secho(
            f"\nMapping already exists: {package_name} \u2192 {current_value}",
            fg=typer.colors.YELLOW,
        )
        questions = [
            inquirer.Confirm(
                "update", message=f"Update mapping to '{app_name}'?", default=False
            )
        ]
        answers = inquirer.prompt(questions)

        if not answers or not answers["update"]:
            typer.secho("Keeping existing mapping.", fg=typer.colors.CYAN)
            return

        typer.secho(f"Updating: {package_name} \u2192 {app_name}", fg=typer.colors.BLUE)
        configs[package_name]["installed_apps"] = app_name
    else:
        # Add new entry with just the mapping
        configs[package_name] = {"installed_apps": app_name}

    # Save back
    try:
        save_package_configs(configs)
        typer.secho(
            f"Saved mapping: {package_name} \u2192 {app_name}", fg=typer.colors.GREEN
        )
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)


def get_app_name_from_mapping(package_name: str, mappings: dict) -> Optional[str]:
    """Get app name from mappings, return None if not found or if value is null"""
    app_name = mappings.get(package_name)
    # Return None if mapping doesn't exist or if it's explicitly null (dependency-only package)
    return app_name if app_name is not None else None


# ============================================================================
# requirements.txt Management Functions
# ============================================================================


def find_requirements_file(start_dir: Path) -> Optional[Path]:
    """Find requirements.txt in project root"""
    req_file = start_dir / "requirements.txt"
    if req_file.exists():
        return req_file
    return None


def get_package_version(package_name: str) -> Optional[str]:
    """Get the installed version of a package"""
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def add_to_requirements(req_file: Path, package_name: str, package_version: str):
    """Add or update a package in requirements.txt"""
    if req_file.exists():
        with open(req_file, "r") as f:
            lines = f.readlines()

        # Check if package already exists
        package_found = False
        new_lines = []
        for line in lines:
            line_stripped = line.strip()
            if (
                line_stripped.startswith(package_name + "==")
                or line_stripped == package_name
            ):
                # Update version
                new_lines.append(f"{package_name}=={package_version}\n")
                package_found = True
            else:
                new_lines.append(line)

        if not package_found:
            new_lines.append(f"{package_name}=={package_version}\n")

        with open(req_file, "w") as f:
            f.writelines(new_lines)
    else:
        # Create new requirements.txt
        with open(req_file, "w") as f:
            f.write(f"{package_name}=={package_version}\n")


def remove_from_requirements(req_file: Path, package_name: str):
    """Remove a package from requirements.txt"""
    if not req_file.exists():
        return

    with open(req_file, "r") as f:
        lines = f.readlines()

    new_lines = [line for line in lines if not line.strip().startswith(package_name)]

    with open(req_file, "w") as f:
        f.writelines(new_lines)


def generate_requirements_from_project(
    start_dir: Path, settings_file: Path, mappings: dict
) -> List[str]:
    """Scan project and generate list of required packages based on INSTALLED_APPS"""
    # Read INSTALLED_APPS
    with open(settings_file, "r") as f:
        content = f.read()

    pattern = re.compile(r"INSTALLED_APPS\s*=\s*\[(.*?)\]", re.DOTALL)
    match = pattern.search(content)
    if not match:
        return []

    apps_list = match.group(1)
    installed_apps = re.findall(r"['\"]([^'\"]+)['\"]", apps_list)

    # Filter out default Django apps
    non_default_apps = [app for app in installed_apps if not is_default_django_app(app)]

    # Create reverse mapping (app_name -> package_name)
    reverse_mappings = {v: k for k, v in mappings.items() if v is not None}

    # Get package names
    packages = []
    for app in non_default_apps:
        # Check if it's a mapped app
        package_name = reverse_mappings.get(app, app)

        # Check if package is installed
        if is_package_installed(package_name):
            pkg_version = get_package_version(package_name)
            if pkg_version:
                packages.append(f"{package_name}=={pkg_version}")

    return packages


# ============================================================================
# Unused App Detection Functions
# ============================================================================


def scan_python_files(start_dir: Path) -> List[Path]:
    """Recursively find all .py files in the project"""
    python_files = []
    for root, dirs, files in os.walk(start_dir):
        # Skip virtual environments and common non-project directories
        dirs[:] = [
            d
            for d in dirs
            if d
            not in [
                "venv",
                "env",
                ".venv",
                "node_modules",
                "__pycache__",
                ".git",
                "migrations",
            ]
        ]
        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)
    return python_files


def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file"""
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Match: import package, from package import ...
            import_pattern = re.compile(
                r"^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE
            )
            for match in import_pattern.finditer(content):
                module = match.group(1).split(".")[0]  # Get root module
                imports.add(module)
    except Exception:
        # Silently skip files that can't be read
        pass
    return imports


def detect_unused_apps(
    settings_file: Path, start_dir: Path, mappings: dict
) -> List[str]:
    """Detect apps in INSTALLED_APPS that are not imported anywhere in the project"""
    # Read INSTALLED_APPS
    with open(settings_file, "r") as f:
        content = f.read()

    pattern = re.compile(r"INSTALLED_APPS\s*=\s*\[(.*?)\]", re.DOTALL)
    match = pattern.search(content)
    if not match:
        return []

    # Extract app names from INSTALLED_APPS
    apps_list = match.group(1)
    installed_apps = re.findall(r"['\"]([^'\"]+)['\"]", apps_list)

    # Filter out default Django apps
    non_default_apps = [app for app in installed_apps if not is_default_django_app(app)]

    # Scan all Python files for imports
    typer.secho("Scanning Python files for imports...", fg=typer.colors.BLUE)
    python_files = scan_python_files(start_dir)
    all_imports = set()
    for py_file in python_files:
        all_imports.update(extract_imports_from_file(py_file))

    # Create reverse mapping (app_name -> package_name)
    reverse_mappings = {v: k for k, v in mappings.items() if v is not None}

    # Check which apps are not imported
    unused_apps = []
    for app in non_default_apps:
        # Check if app itself is imported
        app_root = app.split(".")[0]

        # Also check if it's a mapped package (e.g., rest_framework -> djangorestframework)
        package_name = reverse_mappings.get(app, app)
        package_root = package_name.split(".")[0].replace("-", "_")

        if app_root not in all_imports and package_root not in all_imports:
            unused_apps.append(app)

    return unused_apps


# ============================================================================
# Install from requirements.txt Functions
# ============================================================================


def parse_requirements_file(req_file: Path) -> List[str]:
    """
    Parse requirements.txt file and extract package names without version specifiers

    Handles:
    - Package names with version specifiers (==, >=, <=, ~=, !=, >, <)
    - Comments (lines starting with #)
    - Empty lines
    - Package names with extras (e.g., package[extra])
    - Git URLs and editable installs (skipped)

    Returns:
        List of package names without version specifiers
    """
    packages = []

    if not req_file.exists():
        return packages

    try:
        with open(req_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Skip git URLs and editable installs
                if line.startswith(("git+", "hg+", "svn+", "bzr+", "-e", "--editable")):
                    continue

                # Remove inline comments
                if "#" in line:
                    line = line.split("#")[0].strip()

                # Extract package name (remove version specifiers and extras)
                # Handle: package==1.0.0, package>=1.0, package[extra]==1.0
                package_name = re.split(r"[=<>!~\[]", line)[0].strip()

                if package_name:
                    packages.append(package_name)

    except Exception as e:
        typer.secho(f"Error parsing requirements file: {e}", fg=typer.colors.RED)

    return packages


def install_from_requirements_file(req_file: Path) -> bool:
    """
    Install all packages from requirements.txt using pip

    Returns:
        True if installation successful, False otherwise
    """
    try:
        typer.secho(
            f"Installing packages from {req_file.name}...", fg=typer.colors.BLUE
        )
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            typer.secho(
                f"Successfully installed packages from {req_file.name}",
                fg=typer.colors.GREEN,
            )
            return True
        else:
            typer.secho(
                f"Error installing packages: {result.stderr}", fg=typer.colors.RED
            )
            return False

    except Exception as e:
        typer.secho(f"Error during installation: {e}", fg=typer.colors.RED)
        return False


def detect_django_packages_from_list(packages: List[str], mappings: dict) -> List[dict]:
    """
    Detect which packages are Django-related and get their app names

    Args:
        packages: List of package names
        mappings: Package mappings dictionary

    Returns:
        List of dicts with:
        - package_name: str
        - app_name: str (from mapping or None)
        - is_django: bool
        - is_mapped: bool
    """
    django_packages = []

    typer.secho("\\nDetecting Django-related packages...", fg=typer.colors.BLUE)

    for package in packages:
        # Check if package is installed
        if not is_package_installed(package):
            continue

        # Check if it's Django-related
        if is_django_related(package):
            app_name = get_app_name_from_mapping(package, mappings)

            # Skip dependency-only packages (mapped to null)
            if app_name is None and package in mappings:
                continue

            django_packages.append(
                {
                    "package_name": package,
                    "app_name": app_name,
                    "is_django": True,
                    "is_mapped": app_name is not None,
                }
            )

    return django_packages


# ============================================================================
# INSTALLED_APPS Management Functions
# ============================================================================


def append_to_installed_apps(file_path: Path, new_app: str):
    """Add a single app to INSTALLED_APPS"""
    with open(file_path, "r") as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho(
            "The specified INSTALLED_APPS list was not found in the file.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    start, apps_list, end = match.groups()

    if f"'{new_app}'" in apps_list:
        typer.secho(
            f"The app '{new_app}' already exists and will not be added to INSTALLED_APPS.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    new_apps_list = apps_list + f"\n\t'{new_app}',"
    new_content = content[: match.start(2)] + new_apps_list + content[match.end(2) :]

    with open(file_path, "w") as file:
        file.write(new_content)

    typer.secho(
        f"App '{new_app}' has been added to INSTALLED_APPS.", fg=typer.colors.GREEN
    )


def append_to_installed_apps_multi(file_path: Path, new_app: str):
    """Add an app to INSTALLED_APPS (multi-app version that doesn't exit on error)"""
    with open(file_path, "r") as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho(
            "The specified INSTALLED_APPS list was not found in the file.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    start, apps_list, end = match.groups()

    if f"'{new_app}'" not in apps_list:
        new_apps_list = apps_list + f"\n\t'{new_app}',"
        new_content = (
            content[: match.start(2)] + new_apps_list + content[match.end(2) :]
        )

        with open(file_path, "w") as file:
            file.write(new_content)

        typer.secho(
            f"App '{new_app}' has been added to INSTALLED_APPS.", fg=typer.colors.GREEN
        )
    else:
        typer.secho(
            f"App '{new_app}' has already been added to INSTALLED_APPS. Skipping!",
            fg=typer.colors.BRIGHT_BLUE,
        )


def remove_from_installed_apps(file_path: Path, app_to_remove: str):
    """Remove a single app from INSTALLED_APPS in settings.py"""
    with open(file_path, "r") as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho(
            "The specified INSTALLED_APPS list was not found in the file.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    start, apps_list, end = match.groups()

    # Check if app exists in the list (handle both single and double quotes)
    if f"'{app_to_remove}'" not in apps_list and f'"{app_to_remove}"' not in apps_list:
        typer.secho(
            f"The app '{app_to_remove}' was not found in INSTALLED_APPS.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    # Remove the app entry (handles both quote styles and trailing comma)
    app_pattern = re.compile(
        rf"\s*['\"]({re.escape(app_to_remove)})['\"],?\s*\n?", re.MULTILINE
    )

    new_apps_list = app_pattern.sub("", apps_list)
    new_content = content[: match.start(2)] + new_apps_list + content[match.end(2) :]

    with open(file_path, "w") as file:
        file.write(new_content)

    typer.secho(
        f"App '{app_to_remove}' has been removed from INSTALLED_APPS.",
        fg=typer.colors.GREEN,
    )


def remove_from_installed_apps_multi(file_path: Path, app_to_remove: str):
    """Remove an app from INSTALLED_APPS (multi-app version that doesn't exit on error)"""
    with open(file_path, "r") as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho(
            "The specified INSTALLED_APPS list was not found in the file.",
            fg=typer.colors.RED,
        )
        return

    start, apps_list, end = match.groups()

    # Check if app exists in the list
    if f"'{app_to_remove}'" not in apps_list and f'"{app_to_remove}"' not in apps_list:
        typer.secho(
            f"App '{app_to_remove}' was not found in INSTALLED_APPS. Skipping!",
            fg=typer.colors.BRIGHT_BLUE,
        )
        return

    # Remove the app entry
    app_pattern = re.compile(
        rf"\s*['\"]({re.escape(app_to_remove)})['\"],?\s*\n?", re.MULTILINE
    )

    new_apps_list = app_pattern.sub("", apps_list)
    new_content = content[: match.start(2)] + new_apps_list + content[match.end(2) :]

    with open(file_path, "w") as file:
        file.write(new_content)

    typer.secho(
        f"App '{app_to_remove}' has been removed from INSTALLED_APPS.",
        fg=typer.colors.GREEN,
    )


# ============================================================================
# Helper Functions for Add/Remove Commands
# ============================================================================


def handle_requirements_after_add(start_dir: Path, package_name: str):
    """Handle requirements.txt management after adding a package"""
    req_file_path = find_requirements_file(start_dir)
    pkg_version = get_package_version(package_name)

    if not pkg_version:
        return

    if req_file_path:
        # requirements.txt exists
        questions = [
            inquirer.Confirm(
                "add_to_req",
                message=f"Add '{package_name}=={pkg_version}' to requirements.txt?",
                default=True,
            )
        ]
        answers = inquirer.prompt(questions)

        if answers and answers["add_to_req"]:
            add_to_requirements(req_file_path, package_name, pkg_version)
            typer.secho(
                f"Added '{package_name}=={pkg_version}' to requirements.txt",
                fg=typer.colors.GREEN,
            )
    else:
        # requirements.txt doesn't exist
        questions = [
            inquirer.List(
                "req_action",
                message="requirements.txt not found. What would you like to do?",
                choices=[
                    "Create requirements.txt with this package",
                    "Create requirements.txt with all project packages",
                    "None/Skip",
                ],
            )
        ]
        answers = inquirer.prompt(questions)

        if not answers:
            return

        if answers["req_action"] == "None/Skip":
            return
        elif answers["req_action"] == "Create requirements.txt with this package":
            req_file_path = start_dir / "requirements.txt"
            add_to_requirements(req_file_path, package_name, pkg_version)
            typer.secho(
                f"Created requirements.txt with '{package_name}=={pkg_version}'",
                fg=typer.colors.GREEN,
            )

        elif (
            answers["req_action"] == "Create requirements.txt with all project packages"
        ):
            req_file_path = start_dir / "requirements.txt"
            settings_file_path = find_settings_file(start_dir)
            if settings_file_path:
                mappings = load_package_mappings()
                packages = generate_requirements_from_project(
                    start_dir, settings_file_path, mappings
                )

                with open(req_file_path, "w") as f:
                    f.write("\n".join(packages) + "\n")

                typer.secho(
                    f"Created requirements.txt with {len(packages)} packages",
                    fg=typer.colors.GREEN,
                )


def handle_requirements_after_remove(start_dir: Path, app_name: str):
    """Handle requirements.txt management after removing an app"""
    req_file_path = find_requirements_file(start_dir)

    if not req_file_path:
        return

    # Check if package is in requirements.txt
    with open(req_file_path, "r") as f:
        content = f.read()

    # Get package name from reverse mapping
    mappings = load_package_mappings()
    reverse_mappings = {v: k for k, v in mappings.items() if v is not None}
    package_name = reverse_mappings.get(app_name, app_name)

    if package_name in content:
        questions = [
            inquirer.Confirm(
                "remove_from_req",
                message=f"Remove '{package_name}' from requirements.txt?",
                default=True,
            )
        ]
        answers = inquirer.prompt(questions)

        if answers and answers["remove_from_req"]:
            remove_from_requirements(req_file_path, package_name)
            typer.secho(
                f"Removed '{package_name}' from requirements.txt", fg=typer.colors.GREEN
            )


# ============================================================================
# Backup & Rollback System
# ============================================================================


def get_backup_dir(start_dir: Path) -> Path:
    """Get or create the backup directory"""
    backup_dir = start_dir / ".django-include-apps" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(settings_file: Path, start_dir: Path) -> Optional[Path]:
    """Create a backup of settings.py before making changes"""
    backup_dir = get_backup_dir(start_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"settings_{timestamp}.py.bak"

    try:
        shutil.copy2(settings_file, backup_file)
        return backup_file
    except Exception as e:
        typer.secho(f"Warning: Could not create backup: {e}", fg=typer.colors.YELLOW)
        return None


def list_backups(start_dir: Path) -> List[Path]:
    """List all available backups, sorted by date (newest first)"""
    backup_dir = get_backup_dir(start_dir)
    backups = list(backup_dir.glob("settings_*.py.bak"))
    return sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True)


def restore_backup(backup_file: Path, settings_file: Path) -> bool:
    """Restore a backup to settings.py"""
    try:
        shutil.copy2(backup_file, settings_file)
        return True
    except Exception as e:
        typer.secho(f"Error restoring backup: {e}", fg=typer.colors.RED)
        return False


# ============================================================================
# Extended Package Configuration
# ============================================================================


def load_package_configs() -> dict:
    """Load extended package configurations from JSON file"""
    config_file = Path(__file__).parent / "package_configs.json"
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            typer.secho(
                "Error loading package configs. Using empty config.",
                fg=typer.colors.YELLOW,
            )
            return {}
    return {}


def save_package_configs(configs: dict):
    """Save extended package configurations to JSON file"""
    config_file = Path(__file__).parent / "package_configs.json"
    with open(config_file, "w") as f:
        json.dump(configs, f, indent=4)


def get_package_config(package_name: str) -> Optional[dict]:
    """Get extended configuration for a specific package"""
    configs = load_package_configs()
    return configs.get(package_name)


def find_manage_py(start_dir: Path) -> Optional[Path]:
    """Find manage.py file in the project directory or its parents"""
    # First, search within start_dir
    for root, dirs, files in os.walk(start_dir):
        if "manage.py" in files:
            return Path(root) / "manage.py"
    # Also check parent directories
    current = start_dir
    while current != current.parent:
        manage_path = current / "manage.py"
        if manage_path.exists():
            return manage_path
        current = current.parent
    return None


def run_migrations_if_needed(package_name: str, start_dir: Path):
    """Check if a package requires migrations and prompt to run them"""
    config = get_package_config(package_name)
    if not config or not config.get("requires_migrations"):
        return

    typer.echo()
    typer.secho(
        f"⚠️  '{package_name}' requires database migrations.",
        fg=typer.colors.YELLOW,
        bold=True,
    )

    migrate_q = [
        inquirer.Confirm(
            "migrate",
            message="Run 'python manage.py migrate' now?",
            default=True,
        )
    ]
    migrate_ans = inquirer.prompt(migrate_q)

    if migrate_ans and migrate_ans["migrate"]:
        manage_py = find_manage_py(start_dir)
        if manage_py:
            typer.secho("Running migrations...", fg=typer.colors.BLUE)
            try:
                result = subprocess.run(
                    [sys.executable, str(manage_py), "migrate"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    typer.secho(
                        "✅ Migrations applied successfully.", fg=typer.colors.GREEN
                    )
                else:
                    typer.secho("❌ Migration failed:", fg=typer.colors.RED)
                    if result.stderr:
                        typer.echo(result.stderr)
                    typer.secho(
                        "You can run migrations manually: python manage.py migrate",
                        fg=typer.colors.YELLOW,
                    )
            except Exception as e:
                typer.secho(f"Error running migrations: {e}", fg=typer.colors.RED)
                typer.secho(
                    "You can run migrations manually: python manage.py migrate",
                    fg=typer.colors.YELLOW,
                )
        else:
            typer.secho(
                "manage.py not found. Run migrations manually: python manage.py migrate",
                fg=typer.colors.YELLOW,
            )


def configure_package_interactive(package_name: str):
    """Interactive prompts to create/edit package configuration"""
    configs = load_package_configs()
    current_config = configs.get(package_name, {})

    typer.secho(f"\n🔧 Configuring '{package_name}'", fg=typer.colors.CYAN)

    # Middleware
    if current_config.get("middleware"):
        typer.echo(f"Current Middleware: {current_config['middleware']}")

    mw_q = [
        inquirer.List(
            "action",
            message="Middleware Configuration",
            choices=["Keep current", "Set new", "Clear"],
            default="Keep current",
        )
    ]
    mw_ans = inquirer.prompt(mw_q)

    if mw_ans["action"] == "Set new":
        mw_text = inquirer.prompt(
            [inquirer.Text("mw", message="Enter middleware path (or comma separated)")]
        )
        if mw_text and mw_text["mw"]:
            mws = [m.strip() for m in mw_text["mw"].split(",")]
            if len(mws) == 1:
                current_config["middleware"] = mws[0]
            else:
                current_config["middleware"] = mws
    elif mw_ans["action"] == "Clear":
        current_config.pop("middleware", None)

    # URL Patterns
    if current_config.get("url_patterns"):
        typer.echo(f"Current URL Patterns: {current_config['url_patterns']}")

    url_q = [
        inquirer.List(
            "action",
            message="URL Configuration",
            choices=["Keep current", "Add Pattern", "Clear"],
            default="Keep current",
        )
    ]
    url_ans = inquirer.prompt(url_q)

    if url_ans["action"] == "Add Pattern":
        pat_q = [
            inquirer.Text("route", message="Enter route (e.g. 'api/')"),
            inquirer.Text("include", message="Enter include path (e.g. 'api.urls')"),
        ]
        pat_ans = inquirer.prompt(pat_q)
        if pat_ans["route"] and pat_ans["include"]:
            new_pat = {"pattern": pat_ans["route"], "include": pat_ans["include"]}
            # Simple handling: overwrite or append?
            # Supporting structure: could be list or dict. Let's make it a list if multiple.
            # For simplicity in this prompt, just single pattern or list of patterns.
            current_config["url_patterns"] = new_pat
    elif url_ans["action"] == "Clear":
        current_config.pop("url_patterns", None)

    # Required Settings
    if current_config.get("required_settings"):
        typer.echo(f"Current Settings: {current_config['required_settings']}")

    set_q = [
        inquirer.List(
            "action",
            message="Settings Configuration",
            choices=["Keep current", "Add Setting", "Clear"],
            default="Keep current",
        )
    ]
    set_ans = inquirer.prompt(set_q)

    if set_ans["action"] == "Add Setting":
        s_q = [
            inquirer.Text("key", message="Enter Setting KEY"),
            inquirer.Text(
                "value",
                message='Enter Setting Value (JSON format, e.g. "value", true, 123)',
            ),
        ]
        s_ans = inquirer.prompt(s_q)
        if s_ans["key"] and s_ans["value"]:
            try:
                val = json.loads(s_ans["value"])
            except:
                val = s_ans["value"]  # Fallback to string

            if "required_settings" not in current_config:
                current_config["required_settings"] = {}
            current_config["required_settings"][s_ans["key"]] = val
    elif set_ans["action"] == "Clear":
        current_config.pop("required_settings", None)

    # Migrations
    mig_q = [
        inquirer.Confirm(
            "migrations",
            message="Does this package require migrations?",
            default=current_config.get("requires_migrations", False),
        )
    ]
    mig_ans = inquirer.prompt(mig_q)
    current_config["requires_migrations"] = mig_ans["migrations"]

    # Save
    configs[package_name] = current_config
    save_package_configs(configs)
    typer.secho(f"Configuration for '{package_name}' saved.", fg=typer.colors.GREEN)


# ============================================================================
# Extended Configuration Application Logic
# ============================================================================


def inject_middleware(
    settings_path: Path,
    middleware_class: str,
    position: str = "last",
    relative_to: str = None,
):
    """Inject middleware into settings.py"""
    with open(settings_path, "r") as f:
        content = f.read()

    if middleware_class in content:
        return  # Already added

    pattern = re.compile(r"(MIDDLEWARE\s*=\s*\[)(.*?)(\])", re.DOTALL)
    match = pattern.search(content)

    if match:
        start, middleware_list, end = match.groups()
        new_middleware_entry = f"    '{middleware_class}',\n"

        if position == "top":
            new_list = "\n" + new_middleware_entry + middleware_list
        elif position == "before" and relative_to and relative_to in middleware_list:
            # Simple insertion before a known middleware
            parts = middleware_list.split(f"'{relative_to}'")
            if len(parts) > 1:
                new_list = (
                    parts[0]
                    + f"'{middleware_class}',\n    '{relative_to}'"
                    + "".join(parts[1:])
                )
            else:
                new_list = middleware_list + new_middleware_entry
        else:
            new_list = middleware_list + new_middleware_entry

        new_content = content[: match.start(2)] + new_list + content[match.end(2) :]

        with open(settings_path, "w") as f:
            f.write(new_content)

        typer.secho(f"Added middleware: {middleware_class}", fg=typer.colors.GREEN)


def inject_settings(settings_path: Path, settings_dict: dict):
    """Append required settings to settings.py"""
    with open(settings_path, "r") as f:
        content = f.read()

    new_settings = ""
    for key, value in settings_dict.items():
        if f"{key} =" in content:
            continue

        formatted_value = json.dumps(value, indent=4)
        if formatted_value == "true":
            formatted_value = "True"
        if formatted_value == "false":
            formatted_value = "False"
        if formatted_value == "null":
            formatted_value = "None"

        new_settings += f"\n{key} = {formatted_value}\n"

    if new_settings:
        with open(settings_path, "a") as f:
            f.write(new_settings)
        typer.secho(
            f"Added {len(settings_dict)} configuration settings.",
            fg=typer.colors.GREEN,
        )


def inject_url_pattern(urls_path: Path, pattern: dict):
    """Inject URL pattern into urls.py"""
    if not urls_path.exists():
        return

    with open(urls_path, "r") as f:
        content = f.read()

    url_code = f"path('{pattern['pattern']}', include('{pattern['include']}'))"
    if url_code in content:
        return

    # Check for include import
    if (
        "from django.urls import" in content
        and "include" not in content.split("from django.urls import")[1].split("\n")[0]
    ):
        content = content.replace(
            "from django.urls import path", "from django.urls import path, include"
        )

    # Find urlpatterns
    match = re.search(r"(urlpatterns\s*=\s*\[)(.*?)(\])", content, re.DOTALL)
    if match:
        new_url_entry = f"\n    {url_code},"
        new_content = content[: match.end(2)] + new_url_entry + content[match.end(2) :]

        with open(urls_path, "w") as f:
            f.write(new_content)

        typer.secho(f"Added URL pattern: {pattern['pattern']}", fg=typer.colors.GREEN)


def inject_import(settings_path: Path, import_code: str):
    """Inject import statements at the top of settings.py"""
    with open(settings_path, "r") as f:
        content = f.read()

    # Simple check to avoid duplicates
    if import_code.strip() in content:
        return

    # Add to top
    new_content = import_code + "\n" + content

    with open(settings_path, "w") as f:
        f.write(new_content)

    typer.secho("Added imports to settings.py", fg=typer.colors.GREEN)


def inject_list_setting(settings_path: Path, setting_name: str, items: List[str]):
    """Inject items into a list setting (e.g. AUTHENTICATION_BACKENDS)"""
    with open(settings_path, "r") as f:
        content = f.read()

    # Check if setting exists
    pattern = re.compile(f"({setting_name}\\s*=\\s*\\[)(.*?)(\\])", re.DOTALL)
    match = pattern.search(content)

    if match:
        start, current_list, end = match.groups()
        new_items = ""
        for item in items:
            if item not in current_list:
                new_items += f"    '{item}',\\n"

        if new_items:
            new_content = (
                content[: match.start(2)]
                + current_list
                + new_items
                + content[match.end(2) :]
            )
            with open(settings_path, "w") as f:
                f.write(new_content)
            typer.secho(f"Updated {setting_name}", fg=typer.colors.GREEN)
    else:
        # Create new setting
        new_setting = f"\\n{setting_name} = [\\n"
        for item in items:
            new_setting += f"    '{item}',\\n"
        new_setting += "]\\n"

        with open(settings_path, "a") as f:
            f.write(new_setting)
        typer.secho(f"Created {setting_name}", fg=typer.colors.GREEN)


# ============================================================================
# Extended Configuration Removal Logic
# ============================================================================


def remove_middleware(settings_path: Path, middleware_class: str):
    """Remove middleware from settings.py"""
    if not settings_path.exists():
        return

    with open(settings_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    in_middleware = False
    middleware_removed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("MIDDLEWARE = [") or stripped.startswith(
            "MIDDLEWARE_CLASSES = ["
        ):
            in_middleware = True
            new_lines.append(line)
            continue

        if in_middleware:
            if stripped == "]":
                in_middleware = False
                new_lines.append(line)
                continue

            # Check if this line contains the middleware to remove
            if f"'{middleware_class}'" in line or f'"{middleware_class}"' in line:
                middleware_removed = True
                continue  # Skip adding this line

        new_lines.append(line)

    if middleware_removed:
        with open(settings_path, "w") as f:
            f.writelines(new_lines)
        typer.secho(f"Removed middleware '{middleware_class}'", fg=typer.colors.YELLOW)


def remove_from_list_setting(settings_path: Path, setting_name: str, item: str):
    """Remove an item from a list setting in settings.py"""
    if not settings_path.exists():
        return

    with open(settings_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    in_setting = False
    item_removed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{setting_name} = ["):
            in_setting = True
            new_lines.append(line)
            continue

        if in_setting:
            if stripped == "]":
                in_setting = False
                new_lines.append(line)
                continue

            if f"'{item}'" in line or f'"{item}"' in line:
                item_removed = True
                continue

        new_lines.append(line)

    if item_removed:
        with open(settings_path, "w") as f:
            f.writelines(new_lines)
        typer.secho(f"Removed '{item}' from {setting_name}", fg=typer.colors.YELLOW)


def remove_setting(settings_path: Path, setting_name: str):
    """Remove a specific setting (and its value) from settings.py"""
    if not settings_path.exists():
        return

    # Read file content
    with open(settings_path, "r") as f:
        lines = f.readlines()

    final_lines = []
    iterator = iter(lines)
    removed = False

    try:
        while True:
            line = next(iterator)
            if line.strip().startswith(f"{setting_name} ="):
                removed = True
                # Check if it opens a block and skip logic could be complex.
                # For now, simplistic approach: if it ends with bracket, assume block end is on new line with matching bracket?
                # Too risky to guess block end without parsing.
                # Safest: only remove if it looks like a one-liner or we can confidently identify block end.

                # Heuristic: if line doesn't end with [ { (, just skip it.
                strip = line.strip()
                if not (
                    strip.endswith("[") or strip.endswith("{") or strip.endswith("(")
                ):
                    continue

                # If block, we attempt to skip until closing.
                # This is dangerous. Let's just comment it out?
                # Or just notify user?
                # Let's try a simple block skipper that counts brackets.
                open_brackets = line.count("[") + line.count("{") + line.count("(")
                close_brackets = line.count("]") + line.count("}") + line.count(")")

                while open_brackets > close_brackets:
                    try:
                        next_line = next(iterator)
                    except StopIteration:
                        break
                    open_brackets += (
                        next_line.count("[")
                        + next_line.count("{")
                        + next_line.count("(")
                    )
                    close_brackets += (
                        next_line.count("]")
                        + next_line.count("}")
                        + next_line.count(")")
                    )
                continue

            final_lines.append(line)
    except StopIteration:
        pass

    if removed:
        with open(settings_path, "w") as f:
            f.writelines(final_lines)
        typer.secho(f"Removed setting '{setting_name}'", fg=typer.colors.YELLOW)


def remove_url_pattern(urls_path: Path, pattern_str: str):
    """Remove a URL pattern from urls.py"""
    if not urls_path.exists():
        return

    with open(urls_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    removed = False

    # Extract path string from pattern dict or string
    target_path = pattern_str
    if isinstance(pattern_str, dict):
        target_path = pattern_str.get("route", "")

    for line in lines:
        if target_path in line and ("path(" in line or "url(" in line):
            removed = True
            continue
        new_lines.append(line)

    if removed:
        with open(urls_path, "w") as f:
            f.writelines(new_lines)
        typer.secho(
            f"Removed URL pattern containing '{target_path}'", fg=typer.colors.YELLOW
        )


def remove_import(settings_path: Path, import_str: str):
    """Remove an import statement"""
    if not settings_path.exists():
        return

    with open(settings_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    removed = False

    for line in lines:
        if import_str.strip() in line:
            removed = True
            continue
        new_lines.append(line)

    if removed:
        with open(settings_path, "w") as f:
            f.writelines(new_lines)


def inject_database_config(settings_path: Path, engine: str):
    """Inject a commented-out database configuration template"""
    with open(settings_path, "a") as f:
        f.write(f"\n# Recommended Database Configuration for this package\n")
        f.write(f"# DATABASES = {{\n")
        f.write(f"#     'default': {{\n")
        f.write(f"#         'ENGINE': '{engine}',\n")
        f.write(f"#         'NAME': 'db_name',\n")
        f.write(f"#         'USER': 'db_user',\n")
        f.write(f"#         'PASSWORD': 'db_password',\n")
        f.write(f"#         'HOST': 'localhost',\n")
        f.write(f"#         'PORT': '',\n")
        f.write(f"#     }}\n")
        f.write(f"# }}\n")
    typer.secho(
        f"Added database configuration template (commented out)", fg=typer.colors.GREEN
    )


def apply_extended_config(package_name: str, start_dir: Path):
    """Apply extended configuration for a package with granular control"""
    config = get_package_config(package_name)
    if not config:
        return

    settings_path = find_settings_file(start_dir)
    if not settings_path:
        return

    # Check actionable configs
    available_actions = []
    if config.get("middleware"):
        available_actions.append(("Middleware", "middleware"))
    if config.get("url_patterns"):
        available_actions.append(("URL Patterns", "url_patterns"))
    if config.get("required_settings"):
        available_actions.append(("Required Settings", "required_settings"))
    if config.get("authentication_backends"):
        available_actions.append(("Authentication Backends", "authentication_backends"))
    if config.get("channel_layers"):
        available_actions.append(("Channel Layers", "channel_layers"))
    if config.get("staticfiles_finders"):
        available_actions.append(("Staticfiles Finders", "staticfiles_finders"))
    if config.get("settings_import"):
        available_actions.append(("Settings Imports", "settings_import"))
    if config.get("database_engine"):
        available_actions.append(("Database Configuration", "database_engine"))

    if not available_actions:
        return

    typer.echo()
    typer.secho(
        f"Configuration for: {package_name}",
        fg=typer.colors.CYAN,
        bold=True,
    )

    # Show details for context — display actual values being added
    if config.get("middleware"):
        position_info = ""
        if config.get("middleware_before"):
            position_info = (
                f" (position: before {config['middleware_before'].split('.')[-1]})"
            )
        elif config.get("middleware_position") == "top":
            position_info = " (position: top of MIDDLEWARE)"
        typer.echo(f"  • Middleware: {config['middleware']}{position_info}")

    if config.get("url_patterns"):
        if isinstance(config["url_patterns"], dict):
            pattern = config["url_patterns"].get("pattern", "")
            include_path = config["url_patterns"].get("include", "")
            namespace = config["url_patterns"].get("namespace", "")
            ns_part = f", namespace='{namespace}'" if namespace else ""
            typer.echo(
                f"  • URL Pattern: path('{pattern}', include('{include_path}'{ns_part}))"
            )
        else:
            for up in config["url_patterns"]:
                typer.echo(f"  • URL Pattern: {up}")

    if config.get("required_settings"):
        typer.echo("  • Settings:")
        for key, value in config["required_settings"].items():
            if isinstance(value, (dict, list)):
                formatted = json.dumps(value, indent=4)
                # Indent each line to align under the key
                lines = formatted.split("\n")
                typer.echo(f"      {key} = {lines[0]}")
                for line in lines[1:]:
                    typer.echo(f"      {line}")
            else:
                typer.echo(f"      {key} = {value}")

    if config.get("authentication_backends"):
        backends = config["authentication_backends"]
        if isinstance(backends, list):
            for b in backends:
                typer.echo(f"  • Auth Backend: {b}")
        else:
            typer.echo(f"  • Auth Backend: {backends}")

    if config.get("channel_layers"):
        typer.echo("  • Channel Layers:")
        for layer_name, layer_cfg in config["channel_layers"].items():
            typer.echo(f"      {layer_name}: {layer_cfg.get('BACKEND', 'Unknown')}")

    if config.get("staticfiles_finders"):
        finders = config["staticfiles_finders"]
        if isinstance(finders, list):
            for f in finders:
                typer.echo(f"  • Staticfiles Finder: {f}")
        else:
            typer.echo(f"  • Staticfiles Finder: {finders}")

    if config.get("settings_import"):
        typer.echo(f"  • Import: {config['settings_import']}")

    # Database / Other Recommendations
    if config.get("database_engine"):
        typer.secho(
            f"  • Database Engine: {config['database_engine']}",
            fg=typer.colors.BLUE,
        )

    # Prompt user to select actions
    questions = [
        inquirer.Checkbox(
            "actions",
            message=f"Found additional configuration for package '{package_name}' (Space to toggle)",
            choices=[action[0] for action in available_actions],
            default=[action[0] for action in available_actions],
        )
    ]
    answers = inquirer.prompt(questions)

    if not answers or not answers["actions"]:
        typer.secho(
            f"Skipping configuration for '{package_name}'.", fg=typer.colors.YELLOW
        )
        return

    selected_labels = answers["actions"]

    # Dry Run / Apply Confirmation
    typer.secho("\nSelected actions:", fg=typer.colors.CYAN)
    for label in selected_labels:
        typer.echo(f"  - {label}")

    confirm_q = [
        inquirer.List(
            "confirmation",
            message="Proceed?",
            choices=["Yes, apply changes", "Dry Run (Simulate only)", "No, cancel"],
            default="Yes, apply changes",
        )
    ]
    confirm_ans = inquirer.prompt(confirm_q)

    if confirm_ans["confirmation"] == "No, cancel":
        typer.secho("Operation cancelled.", fg=typer.colors.YELLOW)
        return

    is_dry_run = confirm_ans["confirmation"] == "Dry Run (Simulate only)"

    if is_dry_run:
        typer.secho(
            "\nDry Run Mode - No changes will be written:", fg=typer.colors.MAGENTA
        )

    # Map labels back to keys
    selected_keys = [
        action[1] for action in available_actions if action[0] in selected_labels
    ]

    # Helper to apply or simulate
    def apply_or_simulate(key, func, *args):
        if is_dry_run:
            typer.echo(f"  [Dry Run] Would apply {key}")
        else:
            func(*args)

    # 0. Imports
    if "settings_import" in selected_keys:
        apply_or_simulate(
            "Imports", inject_import, settings_path, config["settings_import"]
        )

    # Database
    if "database_engine" in selected_keys:
        apply_or_simulate(
            "Database Config",
            inject_database_config,
            settings_path,
            config["database_engine"],
        )

    # 1. Middleware
    if "middleware" in selected_keys:
        apply_or_simulate(
            "Middleware",
            inject_middleware,
            settings_path,
            config["middleware"],
            config.get("middleware_position", "last"),
            config.get("middleware_before"),
        )

    # 2. Auth Backends
    if "authentication_backends" in selected_keys:
        apply_or_simulate(
            "Auth Backends",
            inject_list_setting,
            settings_path,
            "AUTHENTICATION_BACKENDS",
            config["authentication_backends"],
        )

    # 3. Staticfiles Finders
    if "staticfiles_finders" in selected_keys:
        apply_or_simulate(
            "Staticfiles Finders",
            inject_list_setting,
            settings_path,
            "STATICFILES_FINDERS",
            config["staticfiles_finders"],
        )

    # 4. Channel Layers
    if "channel_layers" in selected_keys:
        apply_or_simulate(
            "Channel Layers",
            inject_settings,
            settings_path,
            {"CHANNEL_LAYERS": config["channel_layers"]},
        )

    # 5. Required Settings
    if "required_settings" in selected_keys:
        apply_or_simulate(
            "Required Settings",
            inject_settings,
            settings_path,
            config["required_settings"],
        )

    # 6. URL Patterns
    if "url_patterns" in selected_keys and config.get("url_patterns"):
        urls_path = settings_path.parent / "urls.py"
        if urls_path.exists():
            if isinstance(config["url_patterns"], list):
                for pattern in config["url_patterns"]:
                    apply_or_simulate(
                        "URL Pattern", inject_url_pattern, urls_path, pattern
                    )
            elif isinstance(config["url_patterns"], dict):
                apply_or_simulate(
                    "URL Pattern", inject_url_pattern, urls_path, config["url_patterns"]
                )
        else:
            if is_dry_run:
                typer.echo("  [Dry Run] Urls.py not found, would skip URL injection")

    if not is_dry_run:
        typer.secho(
            f"\nConfiguration applied for '{package_name}'.", fg=typer.colors.GREEN
        )

        # Post-install Prompts
        # 1. Profile
        profile_q = [
            inquirer.Confirm(
                "save_profile",
                message="Save this configuration to a profile?",
                default=False,
            )
        ]
        if inquirer.prompt(profile_q)["save_profile"]:
            profile_name_q = [inquirer.Text("name", message="Enter profile name")]
            p_ans = inquirer.prompt(profile_name_q)
            if p_ans and p_ans["name"]:
                save_profile(p_ans["name"], [package_name])

        # 2. Migrations
        if config.get("requires_migrations"):
            typer.echo()
            typer.secho(
                f"Found pending migrations for package '{package_name}'.",
                fg=typer.colors.YELLOW,
            )

            mig_q = [
                inquirer.Confirm(
                    "migrate",
                    message="Run 'python manage.py migrate' now?",
                    default=True,
                )
            ]
            if inquirer.prompt(mig_q)["migrate"]:
                typer.secho("Running migrations...", fg=typer.colors.BLUE)
                try:
                    subprocess.run(
                        [sys.executable, "manage.py", "migrate"],
                        check=True,
                        cwd=start_dir,
                    )
                    typer.secho(
                        "Migrations applied successfully.", fg=typer.colors.GREEN
                    )
                except subprocess.CalledProcessError:
                    typer.secho("Migration failed.", fg=typer.colors.RED)
                except FileNotFoundError:
                    typer.secho("manage.py not found.", fg=typer.colors.RED)


def remove_extended_config(package_name: str, start_dir: Path):
    """Remove extended configuration for a package with granular control"""
    config = get_package_config(package_name)
    if not config:
        return

    settings_path = find_settings_file(start_dir)
    if not settings_path:
        return

    # Check actionable configs to remove
    available_actions = []
    if config.get("middleware"):
        available_actions.append(("Middleware", "middleware"))
    if config.get("url_patterns"):
        available_actions.append(("URL Patterns", "url_patterns"))
    # We generally don't want to automatically remove generic required settings as they might be used by other apps
    # But if they are specific to this app, the user might want to.
    # We will list them but maybe default to unchecked? Or just let user decide.
    if config.get("required_settings"):
        available_actions.append(("Required Settings", "required_settings"))
    if config.get("authentication_backends"):
        available_actions.append(("Authentication Backends", "authentication_backends"))
    if config.get("channel_layers"):
        available_actions.append(("Channel Layers", "channel_layers"))
    if config.get("staticfiles_finders"):
        available_actions.append(("Staticfiles Finders", "staticfiles_finders"))
    if config.get("settings_import"):
        available_actions.append(("Settings Imports", "settings_import"))

    if not available_actions:
        return

    typer.echo()
    typer.secho(
        f"Configuration Cleanup for '{package_name}':",
        fg=typer.colors.CYAN,
        bold=True,
    )

    # Show details
    typer.secho(
        "The following configurations are associated with this package:",
        fg=typer.colors.YELLOW,
    )
    for action in available_actions:
        typer.echo(f"  - {action[0]}")

    questions = [
        inquirer.Checkbox(
            "actions",
            message="Select configurations to REMOVE (Space to select)",
            choices=[action[0] for action in available_actions],
            #            default=[action[0] for action in available_actions], # Default to all? Maybe safer to let user pick.
        )
    ]
    answers = inquirer.prompt(questions)

    if not answers or not answers["actions"]:
        typer.secho(
            f"Skipping configuration removal for '{package_name}'.",
            fg=typer.colors.YELLOW,
        )
        return

    selected_labels = answers["actions"]
    selected_keys = [
        action[1] for action in available_actions if action[0] in selected_labels
    ]

    # Confirm again
    confirm_q = [
        inquirer.Confirm(
            "confirm",
            message=f"Are you sure you want to remove selected configurations for {package_name}?",
            default=True,
        )
    ]
    if not inquirer.prompt(confirm_q)["confirm"]:
        typer.secho("Removal cancelled.", fg=typer.colors.YELLOW)
        return

    # Execute Removal

    # 0. Imports
    if "settings_import" in selected_keys:
        remove_import(settings_path, config["settings_import"])

    # 1. Middleware
    if "middleware" in selected_keys:
        # Multi-middleware support? current schema supports one string or list?
        # config['middleware'] is usually a list in apply logic if we look at inject_middleware it handles list or str?
        # Looking at schema: "middleware": ["corsheaders.middleware.CorsMiddleware"]
        mw = config["middleware"]
        if isinstance(mw, list):
            for m in mw:
                remove_middleware(settings_path, m)
        else:
            remove_middleware(settings_path, mw)

    # 2. Auth Backends
    if "authentication_backends" in selected_keys:
        for backend in config["authentication_backends"]:
            remove_from_list_setting(settings_path, "AUTHENTICATION_BACKENDS", backend)

    # 3. Staticfiles Finders
    if "staticfiles_finders" in selected_keys:
        for finder in config["staticfiles_finders"]:
            remove_from_list_setting(settings_path, "STATICFILES_FINDERS", finder)

    # 4. Channel Layers
    if "channel_layers" in selected_keys:
        remove_setting(settings_path, "CHANNEL_LAYERS")

    # 5. Required Settings
    if "required_settings" in selected_keys:
        for key in config["required_settings"].keys():
            remove_setting(settings_path, key)

    # 6. URL Patterns
    if "url_patterns" in selected_keys and config.get("url_patterns"):
        urls_path = settings_path.parent / "urls.py"
        if urls_path.exists():
            if isinstance(config["url_patterns"], list):
                for pattern in config["url_patterns"]:
                    remove_url_pattern(urls_path, pattern)
            elif isinstance(config["url_patterns"], dict):
                remove_url_pattern(urls_path, config["url_patterns"])

    typer.secho(
        f"Configuration cleanup completed for '{package_name}'.", fg=typer.colors.GREEN
    )


# ============================================================================
# Styled Output Functions
# ============================================================================


def show_success(
    title: str, items: List[str], footer: str = None, docs_url: str = None
):
    """Display a beautiful success message box"""
    width = 60
    typer.echo()
    typer.secho("┌" + "─" * (width - 2) + "┐", fg=typer.colors.GREEN)
    typer.secho(f"│  {title:<{width-4}}│", fg=typer.colors.GREEN)
    typer.secho("├" + "─" * (width - 2) + "┤", fg=typer.colors.GREEN)

    for item in items:
        typer.secho(f"│  ✓ {item:<{width-6}}│", fg=typer.colors.GREEN)

    if docs_url:
        typer.secho("│" + " " * (width - 2) + "│", fg=typer.colors.GREEN)
        typer.secho(f"│  Docs: {docs_url:<{width-10}}│", fg=typer.colors.CYAN)

    if footer:
        typer.secho("│" + " " * (width - 2) + "│", fg=typer.colors.GREEN)
        typer.secho(f"│  {footer:<{width-4}}│", fg=typer.colors.YELLOW)

    typer.secho("└" + "─" * (width - 2) + "┘", fg=typer.colors.GREEN)
    typer.echo()


def show_error(title: str, message: str, suggestions: List[str] = None):
    """Display a beautiful error message box with suggestions"""
    width = 60
    typer.echo()
    typer.secho("┌" + "─" * (width - 2) + "┐", fg=typer.colors.RED)
    typer.secho(f"│  {title:<{width-4}}│", fg=typer.colors.RED)
    typer.secho("├" + "─" * (width - 2) + "┤", fg=typer.colors.RED)
    typer.secho(f"│  {message:<{width-4}}│", fg=typer.colors.RED)

    if suggestions:
        typer.secho("│" + " " * (width - 2) + "│", fg=typer.colors.RED)
        typer.secho(f"│  Did you mean:{'':>{width-18}}│", fg=typer.colors.YELLOW)
        for suggestion in suggestions[:3]:
            typer.secho(f"│     • {suggestion:<{width-10}}│", fg=typer.colors.CYAN)

    typer.secho("└" + "─" * (width - 2) + "┘", fg=typer.colors.RED)
    typer.echo()


def find_similar_packages(package_name: str, mappings: dict) -> List[str]:
    """Find packages with similar names for suggestions"""
    similar = []
    package_lower = package_name.lower()

    for pkg in mappings.keys():
        pkg_lower = pkg.lower()
        # Check for substring match or similar prefix
        if (
            package_lower in pkg_lower
            or pkg_lower in package_lower
            or package_lower[:4] == pkg_lower[:4]
        ):
            similar.append(pkg)

    return similar[:5]


# ============================================================================
# CLI Commands
# ============================================================================


@app.command()
def add_app(
    packages: List[str] = typer.Argument(
        ...,
        help="Package(s) to add to INSTALLED_APPS (supports version specifiers like package==1.0.0)",
    ),
    start_dir: Path = typer.Option(
        None,
        "--start-dir",
        "-d",
        help="The directory to search for settings.py. Defaults to current directory.",
    ),
    version_flag: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    Add one or more apps to INSTALLED_APPS in settings.py.
    Uses smart package mapping to automatically determine the correct app names.

    Examples:
        django-include-apps add-app djangorestframework
        django-include-apps add-app djangorestframework django-cors-headers
        django-include-apps add-app djangorestframework==3.14.0 django-filter>=2.0
    """
    start_dir = start_dir or Path.cwd()
    settings_file_path = find_settings_file(start_dir)

    if not settings_file_path:
        typer.secho(
            "settings.py not found in the specified directory or its subdirectories.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Load mappings once
    mappings = load_package_mappings()
    migration_packages = []

    typer.secho(
        "\n IMPORTANT: Configurations applied are based on the latest package documentation.",
        fg=typer.colors.RED,
        bold=True,
    )

    for package_spec in packages:
        # Parse package specification
        package_name, version_spec = parse_package_spec(package_spec)
        package_to_install = package_spec  # Use full spec for installation

        typer.secho(f"\n{'='*60}", fg=typer.colors.CYAN)
        typer.secho(f"Processing: {package_name}", fg=typer.colors.CYAN)
        if version_spec:
            typer.secho(f"Version: {version_spec}", fg=typer.colors.CYAN)
        typer.secho(f"{'='*60}", fg=typer.colors.CYAN)

        # Check if installed
        installed = is_package_installed(package_name)
        if not installed:
            install = [
                inquirer.Confirm(
                    "confirm",
                    message=f"{package_name} is not installed. Do you want to install it?",
                )
            ]
            install_confirm = inquirer.prompt(install)
            if install_confirm and install_confirm["confirm"]:
                typer.secho(
                    f"Installing package '{package_to_install}'...",
                    fg=typer.colors.BLUE,
                )
                install_package(package_to_install)
                typer.secho(
                    f"Package '{package_name}' has been installed.",
                    fg=typer.colors.GREEN,
                )
            else:
                typer.secho(
                    f"Skipping installation of '{package_name}'.",
                    fg=typer.colors.YELLOW,
                )
                continue
        else:
            typer.secho(
                f"Package '{package_name}' is already installed.",
                fg=typer.colors.BRIGHT_YELLOW,
            )

        # Check if Django-related
        if not is_django_related(package_name):
            typer.secho(
                f"The package '{package_name}' is not related to Django. Skipping!",
                fg=typer.colors.RED,
            )
            continue

        # Get mapped app name
        mapped_app_name = get_app_name_from_mapping(package_name, mappings)

        # Ask user for choice
        confirmation = [
            inquirer.List(
                "choice",
                message="Do you want to use the same name or a different one?",
                choices=["Use same", "Use different", "None/Skip"],
            ),
        ]
        answers = inquirer.prompt(confirmation)

        if not answers or answers["choice"] == "None/Skip":
            typer.secho(f"Skipping '{package_name}'.", fg=typer.colors.YELLOW)
            continue

        app_name_to_add = None
        save_mapping = False

        if answers["choice"] == "Use different":
            packagename_question = [
                inquirer.Text(
                    "package_name",
                    message="Enter the app name as mentioned in the source documentation",
                )
            ]
            second_answers = inquirer.prompt(packagename_question)
            if second_answers and second_answers["package_name"]:
                app_name_to_add = second_answers["package_name"]

                if mapped_app_name is None:
                    save_q = [
                        inquirer.Confirm(
                            "save",
                            message=f"Save this mapping ({package_name} → {app_name_to_add}) for future use?",
                            default=True,
                        )
                    ]
                    save_ans = inquirer.prompt(save_q)
                    if save_ans and save_ans["save"]:
                        save_mapping = True
        else:
            if mapped_app_name:
                app_name_to_add = mapped_app_name
                typer.secho(
                    f"Using mapped app name '{mapped_app_name}' for package '{package_name}'.",
                    fg=typer.colors.BRIGHT_CYAN,
                )
            else:
                typer.secho(
                    f"Package '{package_name}' not found in mappings.",
                    fg=typer.colors.YELLOW,
                )
                prompt_q = [
                    inquirer.Text(
                        "app_name", message=f"Enter app name to add to INSTALLED_APPS:"
                    )
                ]
                prompt_ans = inquirer.prompt(prompt_q)
                if prompt_ans and prompt_ans["app_name"]:
                    app_name_to_add = prompt_ans["app_name"]

                    save_q = [
                        inquirer.Confirm(
                            "save",
                            message=f"Save this mapping ({package_name} → {app_name_to_add}) for future use?",
                            default=True,
                        )
                    ]
                    save_ans = inquirer.prompt(save_q)
                    if save_ans and save_ans["save"]:
                        save_mapping = True

        if not app_name_to_add:
            typer.secho(
                f"No app name provided for '{package_name}'. Skipping!",
                fg=typer.colors.YELLOW,
            )
            continue

        # Add to INSTALLED_APPS
        append_to_installed_apps_multi(settings_file_path, app_name_to_add)

        # Save mapping if requested
        if save_mapping:
            update_package_mappings(package_name, app_name_to_add)

        # Handle requirements.txt
        handle_requirements_after_add(start_dir, package_name)

        # Apply extended configuration (Middleware, URLs, Settings)
        apply_extended_config(package_name, start_dir)

        # Track packages that need migrations
        config = get_package_config(package_name)
        if config and config.get("requires_migrations"):
            migration_packages.append(package_name)

    # Prompt to run migrations once for all packages that need it
    if migration_packages:
        typer.echo()
        typer.secho(
            f"⚠️  The following package(s) require database migrations: {', '.join(migration_packages)}",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        migrate_q = [
            inquirer.Confirm(
                "migrate",
                message="Run 'python manage.py migrate' now?",
                default=True,
            )
        ]
        migrate_ans = inquirer.prompt(migrate_q)
        if migrate_ans and migrate_ans["migrate"]:
            manage_py = find_manage_py(start_dir)
            if manage_py:
                typer.secho("Running migrations...", fg=typer.colors.BLUE)
                try:
                    result = subprocess.run(
                        [sys.executable, str(manage_py), "migrate"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        typer.secho(
                            "✅ Migrations applied successfully.", fg=typer.colors.GREEN
                        )
                    else:
                        typer.secho("❌ Migration failed:", fg=typer.colors.RED)
                        if result.stderr:
                            typer.echo(result.stderr)
                        typer.secho(
                            "You can run migrations manually: python manage.py migrate",
                            fg=typer.colors.YELLOW,
                        )
                except Exception as e:
                    typer.secho(f"Error running migrations: {e}", fg=typer.colors.RED)
                    typer.secho(
                        "You can run migrations manually: python manage.py migrate",
                        fg=typer.colors.YELLOW,
                    )
            else:
                typer.secho(
                    "manage.py not found. Run migrations manually: python manage.py migrate",
                    fg=typer.colors.YELLOW,
                )


@app.command()
def remove_app(
    app_names: Optional[List[str]] = typer.Argument(
        None,
        help="App(s) to remove from INSTALLED_APPS. If not specified, scans for unused apps.",
    ),
    start_dir: Path = typer.Option(
        None,
        "--start-dir",
        "-d",
        help="The directory to search for settings.py. Defaults to current directory.",
    ),
    ignore: Optional[List[str]] = typer.Option(
        None,
        "--ignore",
        "-i",
        help="Apps to ignore/protect from removal (in addition to django.* apps)",
    ),
):
    """
    Remove one or more apps from INSTALLED_APPS in settings.py.

    If no apps specified, scans project and shows unused apps for multi-selection.
    Default Django apps (starting with 'django.') are protected from removal.

    Examples:
        django-include-apps remove-app rest_framework
        django-include-apps remove-app rest_framework corsheaders
        django-include-apps remove-app --ignore my_core some_app
        django-include-apps remove-app  # Scan and select unused apps
    """
    start_dir = start_dir or Path.cwd()
    settings_file_path = find_settings_file(start_dir)

    if not settings_file_path:
        typer.secho(
            "settings.py not found in the specified directory or its subdirectories.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    ignored_apps = set(ignore or [])

    # If no apps specified, scan and show multi-select
    if not app_names:
        typer.secho("Scanning project for unused apps...", fg=typer.colors.BLUE)
        mappings = load_package_mappings()
        unused_apps = detect_unused_apps(settings_file_path, start_dir, mappings)

        if not unused_apps:
            typer.secho("No unused apps detected!", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)

        typer.secho(
            f"\nFound {len(unused_apps)} unused app(s):", fg=typer.colors.YELLOW
        )
        for app in unused_apps:
            typer.secho(f"  • {app}", fg=typer.colors.YELLOW)

        # Ask user to select apps to remove (multi-select)
        questions = [
            inquirer.Checkbox(
                "apps_to_remove",
                message="Select apps to remove (use space to select, enter to confirm)",
                choices=unused_apps,
            ),
        ]
        answers = inquirer.prompt(questions)

        if not answers or not answers["apps_to_remove"]:
            typer.secho("No apps selected for removal.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        selected_apps = answers["apps_to_remove"]

        # Confirm before removing
        typer.secho(f"\nApps to be removed:", fg=typer.colors.CYAN)
        for app in selected_apps:
            typer.secho(f"  • {app}", fg=typer.colors.CYAN)

        confirmation = [
            inquirer.Confirm(
                "confirm",
                message=f"Are you sure you want to remove these {len(selected_apps)} app(s)?",
            )
        ]
        confirm_answer = inquirer.prompt(confirmation)

        if not confirm_answer or not confirm_answer["confirm"]:
            typer.secho("Removal cancelled.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        # Remove selected apps
        mappings = load_package_mappings()
        migration_packages = []
        for app in selected_apps:
            # Find package name for config removal
            package_name = next((pkg for pkg, a in mappings.items() if a == app), app)
            remove_extended_config(package_name, start_dir)
            remove_from_installed_apps_multi(settings_file_path, app)
            handle_requirements_after_remove(start_dir, app)
            # Track packages that need migrations
            config = get_package_config(package_name)
            if config and config.get("requires_migrations"):
                migration_packages.append(package_name)

        # Prompt to run migrations if any removed packages had migrations
        if migration_packages:
            typer.echo()
            typer.secho(
                f"⚠️  The following removed package(s) had database migrations: {', '.join(migration_packages)}",
                fg=typer.colors.YELLOW,
                bold=True,
            )
            migrate_q = [
                inquirer.Confirm(
                    "migrate",
                    message="Run 'python manage.py migrate' now to clean up?",
                    default=True,
                )
            ]
            migrate_ans = inquirer.prompt(migrate_q)
            if migrate_ans and migrate_ans["migrate"]:
                manage_py = find_manage_py(start_dir)
                if manage_py:
                    typer.secho("Running migrations...", fg=typer.colors.BLUE)
                    try:
                        result = subprocess.run(
                            [sys.executable, str(manage_py), "migrate"],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            typer.secho(
                                "✅ Migrations applied successfully.",
                                fg=typer.colors.GREEN,
                            )
                        else:
                            typer.secho("❌ Migration failed:", fg=typer.colors.RED)
                            if result.stderr:
                                typer.echo(result.stderr)
                    except Exception as e:
                        typer.secho(
                            f"Error running migrations: {e}", fg=typer.colors.RED
                        )
                else:
                    typer.secho(
                        "manage.py not found. Run migrations manually: python manage.py migrate",
                        fg=typer.colors.YELLOW,
                    )

        return

    # Filter out protected Django apps and ignored apps
    apps_to_remove = []
    protected_apps = []

    for app_name in app_names:
        if is_default_django_app(app_name):
            protected_apps.append(app_name)
        elif app_name in ignored_apps:
            protected_apps.append(app_name)
        else:
            apps_to_remove.append(app_name)

    # Warn about protected apps
    if protected_apps:
        typer.secho(
            f"\nThe following apps are protected and will NOT be removed:",
            fg=typer.colors.YELLOW,
        )
        for app in protected_apps:
            typer.secho(f"  • {app}", fg=typer.colors.YELLOW)

    # Check if there are any apps to remove
    if not apps_to_remove:
        typer.secho(
            "\nNo apps to remove after filtering protected apps.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Show apps that will be removed
    typer.secho(f"\nThe following apps will be removed:", fg=typer.colors.CYAN)
    for app in apps_to_remove:
        typer.secho(f"  • {app}", fg=typer.colors.CYAN)

    typer.secho(
        "\nNote: If any removed apps have database migrations, you will be prompted to run them.",
        fg=typer.colors.YELLOW,
    )

    # Confirmation
    confirmation = [
        inquirer.Confirm(
            "confirm",
            message=f"Are you sure you want to remove these {len(apps_to_remove)} app(s)?",
        )
    ]
    confirm_answer = inquirer.prompt(confirmation)

    if not confirm_answer or not confirm_answer["confirm"]:
        typer.secho("Removal cancelled.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    typer.secho(f"\nRemoving apps from INSTALLED_APPS...", fg=typer.colors.BLUE)

    # Load mappings to identify package names for config removal
    mappings = load_package_mappings()

    # Remove each app
    migration_packages = []
    for app_name in apps_to_remove:
        # Attempt to find the package name for this app
        package_name = None
        for pkg, app in mappings.items():
            if app == app_name:
                package_name = pkg
                break

        # If we found a package name, check/remove extended configs
        if package_name:
            remove_extended_config(package_name, start_dir)
        else:
            # Fallback: try using app_name as package name (e.g. if they are the same)
            remove_extended_config(app_name, start_dir)
            package_name = app_name

        remove_from_installed_apps_multi(settings_file_path, app_name)
        handle_requirements_after_remove(start_dir, app_name)

        # Track packages that need migrations
        config = get_package_config(package_name)
        if config and config.get("requires_migrations"):
            migration_packages.append(package_name)

    # Prompt to run migrations if any removed packages had migrations
    if migration_packages:
        typer.echo()
        typer.secho(
            f"⚠️  The following removed package(s) had database migrations: {', '.join(migration_packages)}",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        migrate_q = [
            inquirer.Confirm(
                "migrate",
                message="Run 'python manage.py migrate' now to clean up?",
                default=True,
            )
        ]
        migrate_ans = inquirer.prompt(migrate_q)
        if migrate_ans and migrate_ans["migrate"]:
            manage_py = find_manage_py(start_dir)
            if manage_py:
                typer.secho("Running migrations...", fg=typer.colors.BLUE)
                try:
                    result = subprocess.run(
                        [sys.executable, str(manage_py), "migrate"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        typer.secho(
                            "✅ Migrations applied successfully.", fg=typer.colors.GREEN
                        )
                    else:
                        typer.secho("❌ Migration failed:", fg=typer.colors.RED)
                        if result.stderr:
                            typer.echo(result.stderr)
                except Exception as e:
                    typer.secho(f"Error running migrations: {e}", fg=typer.colors.RED)
            else:
                typer.secho(
                    "manage.py not found. Run migrations manually: python manage.py migrate",
                    fg=typer.colors.YELLOW,
                )


@app.command()
def install_requirements(
    requirements_file: Path = typer.Option(
        ..., "--requirements", "-r", help="Path to requirements.txt file"
    ),
    start_dir: Path = typer.Option(
        None,
        "--start-dir",
        "-d",
        help="Directory to search for settings.py. Defaults to current directory.",
    ),
):
    """
    Install packages from requirements.txt and automatically add Django packages to INSTALLED_APPS.

    This command will:
    1. Install all packages from the requirements file
    2. Detect which packages are Django-related
    3. Prompt you to select packages to add to INSTALLED_APPS
    4. Use smart package mapping for known packages
    """
    start_dir = start_dir or Path.cwd()

    # Check if requirements file exists
    if not requirements_file.exists():
        typer.secho(
            f"Error: Requirements file '{requirements_file}' not found.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Find settings.py
    settings_file_path = find_settings_file(start_dir)
    if not settings_file_path:
        typer.secho(
            "settings.py not found in the specified directory or its subdirectories.",
            fg=typer.colors.RED,
        )
        typer.secho(
            "Packages will be installed but not added to INSTALLED_APPS.",
            fg=typer.colors.YELLOW,
        )

        # Ask if user wants to continue
        questions = [
            inquirer.Confirm(
                "continue", message="Continue with installation only?", default=True
            )
        ]
        answers = inquirer.prompt(questions)

        if not answers or not answers["continue"]:
            raise typer.Exit(code=0)

        # Install packages only
        install_from_requirements_file(requirements_file)
        raise typer.Exit(code=0)

    # Parse requirements file
    packages = parse_requirements_file(requirements_file)

    if not packages:
        typer.secho("No packages found in requirements file.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    typer.secho(
        f"Found {len(packages)} package(s) in {requirements_file.name}",
        fg=typer.colors.CYAN,
    )

    # Install packages
    if not install_from_requirements_file(requirements_file):
        typer.secho("Installation failed. Exiting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Load package mappings
    mappings = load_package_mappings()

    # Detect Django packages
    django_packages = detect_django_packages_from_list(packages, mappings)

    if not django_packages:
        typer.secho("\nNo Django-related packages detected.", fg=typer.colors.YELLOW)
        typer.secho(
            "All packages have been installed successfully.", fg=typer.colors.GREEN
        )
        raise typer.Exit(code=0)

    # Show detected Django packages
    typer.secho(
        f"\nFound {len(django_packages)} Django package(s):", fg=typer.colors.GREEN
    )
    for pkg in django_packages:
        if pkg["is_mapped"]:
            typer.secho(
                f"  • {pkg['package_name']} → {pkg['app_name']}", fg=typer.colors.CYAN
            )
        else:
            typer.secho(
                f"  • {pkg['package_name']} (unmapped - will prompt for app name)",
                fg=typer.colors.YELLOW,
            )

    # Create choices for checkbox selection
    choices = []
    for pkg in django_packages:
        if pkg["is_mapped"]:
            label = f"{pkg['package_name']} ({pkg['app_name']})"
        else:
            label = f"{pkg['package_name']} (unmapped - will prompt for app name)"
        choices.append(label)

    # Prompt user to select packages
    questions = [
        inquirer.Checkbox(
            "selected_packages",
            message="Select packages to add to INSTALLED_APPS (use space to select, enter to confirm)",
            choices=choices,
            default=choices,  # Pre-select all by default
        ),
    ]
    answers = inquirer.prompt(questions)

    if not answers or not answers["selected_packages"]:
        typer.secho(
            "\nNo packages selected. Installation complete.", fg=typer.colors.YELLOW
        )
        raise typer.Exit(code=0)

    # Process selected packages
    typer.secho("\nAdding selected packages to INSTALLED_APPS...", fg=typer.colors.BLUE)

    typer.secho(
        "\n IMPORTANT: Configurations applied are based on the latest package documentation.",
        fg=typer.colors.RED,
        bold=True,
    )

    added_count = 0
    migration_packages = []
    for i, pkg in enumerate(django_packages):
        if choices[i] in answers["selected_packages"]:
            app_name = pkg["app_name"]

            # If not mapped, prompt for app name
            if not pkg["is_mapped"]:
                prompt_q = [
                    inquirer.Text(
                        "app_name",
                        message=f"Enter app name for '{pkg['package_name']}' to add to INSTALLED_APPS",
                    )
                ]
                prompt_ans = inquirer.prompt(prompt_q)

                if prompt_ans and prompt_ans["app_name"]:
                    app_name = prompt_ans["app_name"]

                    # Ask if they want to save this mapping
                    save_q = [
                        inquirer.Confirm(
                            "save",
                            message=f"Save this mapping ({pkg['package_name']} → {app_name}) for future use?",
                            default=True,
                        )
                    ]
                    save_ans = inquirer.prompt(save_q)
                    if save_ans and save_ans["save"]:
                        update_package_mappings(pkg["package_name"], app_name)
                else:
                    typer.secho(
                        f"Skipping '{pkg['package_name']}' (no app name provided)",
                        fg=typer.colors.YELLOW,
                    )
                    continue

            # Add to INSTALLED_APPS
            try:
                append_to_installed_apps_multi(settings_file_path, app_name)
                added_count += 1
            except Exception as e:
                typer.secho(f"Error adding '{app_name}': {e}", fg=typer.colors.RED)

            # Apply extended configuration (Middleware, URLs, Settings)
            apply_extended_config(pkg["package_name"], start_dir)

            # Track packages that need migrations
            pkg_config = get_package_config(pkg["package_name"])
            if pkg_config and pkg_config.get("requires_migrations"):
                migration_packages.append(pkg["package_name"])

    # Summary
    typer.secho(
        f"\nDone! {added_count} package(s) added to INSTALLED_APPS.",
        fg=typer.colors.GREEN,
    )

    # Prompt to run migrations once for all packages that need it
    if migration_packages:
        typer.echo()
        typer.secho(
            f"⚠️  The following package(s) require database migrations: {', '.join(migration_packages)}",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        migrate_q = [
            inquirer.Confirm(
                "migrate",
                message="Run 'python manage.py migrate' now?",
                default=True,
            )
        ]
        migrate_ans = inquirer.prompt(migrate_q)
        if migrate_ans and migrate_ans["migrate"]:
            manage_py = find_manage_py(start_dir)
            if manage_py:
                typer.secho("Running migrations...", fg=typer.colors.BLUE)
                try:
                    result = subprocess.run(
                        [sys.executable, str(manage_py), "migrate"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        typer.secho(
                            "✅ Migrations applied successfully.", fg=typer.colors.GREEN
                        )
                    else:
                        typer.secho("❌ Migration failed:", fg=typer.colors.RED)
                        if result.stderr:
                            typer.echo(result.stderr)
                except Exception as e:
                    typer.secho(f"Error running migrations: {e}", fg=typer.colors.RED)
            else:
                typer.secho(
                    "manage.py not found. Run migrations manually: python manage.py migrate",
                    fg=typer.colors.YELLOW,
                )


@app.command()
def secure_settings(
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    )
):
    """
    Move sensitive settings (SECRET_KEY, DEBUG, DB credentials) to .env.
    """
    start_dir = start_dir or Path.cwd()
    settings_path = find_settings_file(start_dir)

    if not settings_path:
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    # Backup
    backup_path = create_backup(settings_path, start_dir)
    typer.secho(f"Created backup at {backup_path}", fg=typer.colors.BLUE)

    content = settings_path.read_text()
    env_content = ""
    replacements = []

    # 1. SECRET_KEY
    sk_match = re.search(r"^SECRET_KEY\s*=\s*['\"](.+?)['\"]", content, re.MULTILINE)
    if sk_match:
        secret_key = sk_match.group(1)
        env_content += f"SECRET_KEY={secret_key}\n"
        replacements.append(
            (
                sk_match.group(0),
                "SECRET_KEY = os.getenv('SECRET_KEY', 'unsafe-default-key')",
            )
        )
        typer.secho("Found SECRET_KEY", fg=typer.colors.GREEN)

    # 2. DEBUG
    debug_match = re.search(r"^DEBUG\s*=\s*(True|False)", content, re.MULTILINE)
    if debug_match:
        debug_val = debug_match.group(1)
        env_content += f"DEBUG={debug_val}\n"
        replacements.append(
            (debug_match.group(0), "DEBUG = os.getenv('DEBUG', 'False') == 'True'")
        )
        typer.secho("Found DEBUG", fg=typer.colors.GREEN)

    # 3. Database Credentials (Simple scanning for now)
    # Looking for 'PASSWORD': '...' inside DATABASES
    # This naive regex might need improvement for multi-line but works for standard default dict
    db_pass_match = re.search(r"'PASSWORD':\s*['\"](.+?)['\"]", content)
    if db_pass_match:
        db_pass = db_pass_match.group(1)
        if db_pass and "os.getenv" not in db_pass:
            env_content += f"DB_PASSWORD={db_pass}\n"
            replacements.append(
                (db_pass_match.group(0), "'PASSWORD': os.getenv('DB_PASSWORD', '')")
            )
            typer.secho("Found Database PASSWORD", fg=typer.colors.GREEN)

    if not replacements:
        typer.secho(
            "No hardcoded secrets found or already using os.getenv.",
            fg=typer.colors.YELLOW,
        )
        return

    # Write .env
    env_file = (
        settings_path.parent.parent / ".env"
    )  # Assuming settings is in inner proj folder
    if not env_file.exists():
        env_file.write_text(env_content)
        typer.secho(f"Created .env file at {env_file}", fg=typer.colors.GREEN)
    else:
        typer.secho(
            f".env file already exists at {env_file}. Appending...",
            fg=typer.colors.YELLOW,
        )
        with open(env_file, "a") as f:
            f.write("\n" + env_content)

    # Apply changes to settings.py
    new_content = content

    # Ensure import os
    if "import os" not in new_content:
        new_content = "import os\n" + new_content

    for old, new in replacements:
        new_content = new_content.replace(old, new)

    settings_path.write_text(new_content)

    show_success(
        "Settings Secured",
        [
            "Moved secrets to .env",
            "Updated settings.py to use os.getenv",
            f"Backup created: {backup_path.name}",
        ],
        footer="Make sure python-dotenv is installed and loaded!",
    )

    # Check/Add python-dotenv to requirements
    req_file = find_requirements_file(start_dir)
    if req_file:
        add_to_requirements(req_file, "python-dotenv", "")


@app.command()
def view_mappings(
    filter_pattern: str = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter by package name (supports wildcards like django-*)",
    ),
    null_only: bool = typer.Option(
        False,
        "--null-only",
        help="Show only dependency packages (not added to INSTALLED_APPS)",
    ),
    apps_only: bool = typer.Option(
        False, "--apps-only", help="Show only packages with app names"
    ),
):
    """
    View all package mappings in a table format.

    Displays the mapping between PyPI package names and their INSTALLED_APPS names.
    """
    mappings = load_package_mappings()

    # Apply filters
    filtered_mappings = {}
    for pkg, app in mappings.items():
        # Apply null filter
        if null_only and app is not None:
            continue
        if apps_only and app is None:
            continue

        # Apply pattern filter
        if filter_pattern:
            import fnmatch

            if not fnmatch.fnmatch(pkg, filter_pattern):
                continue

        filtered_mappings[pkg] = app

    if not filtered_mappings:
        typer.secho("No mappings found matching the criteria.", fg=typer.colors.YELLOW)
        return

    # Display header
    total_count = len(mappings)
    filtered_count = len(filtered_mappings)

    if filter_pattern or null_only or apps_only:
        typer.secho(
            f"\nPackage Mappings ({filtered_count} of {total_count} total)\n",
            fg=typer.colors.CYAN,
            bold=True,
        )
    else:
        typer.secho(
            f"\nPackage Mappings ({total_count} total)\n",
            fg=typer.colors.CYAN,
            bold=True,
        )

    # Calculate column widths
    max_pkg_len = max(len(pkg) for pkg in filtered_mappings.keys())
    max_app_len = max(
        len(str(app) if app else "(not added to INSTALLED_APPS)")
        for app in filtered_mappings.values()
    )

    # Ensure minimum widths
    pkg_width = max(max_pkg_len, 20)
    app_width = max(max_app_len, 25)

    # Print table header
    header = f"{'Package Name':<{pkg_width}}  {'INSTALLED_APPS Name':<{app_width}}"
    separator = "─" * pkg_width + "  " + "─" * app_width

    typer.secho(header, fg=typer.colors.BRIGHT_WHITE, bold=True)
    typer.secho(separator, fg=typer.colors.BRIGHT_BLACK)

    # Print table rows
    for pkg, app in sorted(filtered_mappings.items()):
        app_display = (
            app
            if app
            else typer.style("(not added to INSTALLED_APPS)", fg=typer.colors.YELLOW)
        )
        pkg_display = typer.style(pkg, fg=typer.colors.CYAN)

        if app:
            app_display = typer.style(app, fg=typer.colors.GREEN)

        typer.echo(f"{pkg_display:<{pkg_width}}  {app_display}")

    typer.echo()  # Empty line at end


# Create mapping subcommand group
mapping_app = typer.Typer(help="Manage package mappings")
app.add_typer(mapping_app, name="mapping")

@mapping_app.callback(invoke_without_command=True)
def mapping_callback(ctx: typer.Context):
    """Manage package mappings."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@mapping_app.command("list")
def mapping_list(
    filter_pattern: str = typer.Option(
        None, "--filter", "-f", help="Filter by package name"
    ),
    null_only: bool = typer.Option(
        False, "--null-only", help="Show only dependency packages"
    ),
    apps_only: bool = typer.Option(
        False, "--apps-only", help="Show only packages with app names"
    ),
):
    """List all package mappings (alias for view-mappings)"""
    view_mappings(filter_pattern, null_only, apps_only)


@mapping_app.command("add")
def mapping_add(
    package_name: str = typer.Argument(
        ..., help="Package name (e.g., django-cors-headers)"
    ),
    app_name: str = typer.Argument(
        None, help="App name for INSTALLED_APPS (e.g., corsheaders)"
    ),
    null: bool = typer.Option(
        False,
        "--null",
        help="Mark as dependency-only package (not added to INSTALLED_APPS)",
    ),
):
    """
    Add a new package mapping.

    Examples:
        django-include-apps mapping add django-cors-headers corsheaders
        django-include-apps mapping add gunicorn --null
    """
    if null:
        app_name = None
    elif not app_name:
        typer.secho(
            "Error: app_name is required unless --null is specified",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    configs = load_package_configs()

    # Check if mapping already exists
    if package_name in configs:
        current_value = (
            configs[package_name].get("installed_apps")
            if isinstance(configs[package_name], dict)
            else configs[package_name]
        )
        typer.secho(
            f"Mapping already exists: {package_name} \u2192 {current_value}",
            fg=typer.colors.YELLOW,
        )
        typer.secho(
            "Use 'mapping update' to modify existing mappings.", fg=typer.colors.CYAN
        )
        raise typer.Exit(code=1)

    # Add new entry
    configs[package_name] = {"installed_apps": app_name}

    try:
        save_package_configs(configs)

        if app_name:
            typer.secho(
                f"Added mapping: {package_name} \u2192 {app_name}",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"Added mapping: {package_name} \u2192 (not added to INSTALLED_APPS)",
                fg=typer.colors.GREEN,
            )
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@mapping_app.command("update")
def mapping_update(
    package_name: str = typer.Argument(..., help="Package name to update"),
    app_name: str = typer.Argument(None, help="New app name for INSTALLED_APPS"),
    null: bool = typer.Option(False, "--null", help="Mark as dependency-only package"),
):
    """
    Update an existing package mapping.

    Examples:
        django-include-apps mapping update django-cors-headers new_name
        django-include-apps mapping update gunicorn --null
    """
    if null:
        app_name = None
    elif not app_name:
        typer.secho(
            "Error: app_name is required unless --null is specified",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    configs = load_package_configs()

    # Check if mapping exists
    if package_name not in configs:
        typer.secho(f"Mapping not found: {package_name}", fg=typer.colors.RED)
        typer.secho("Use 'mapping add' to create new mappings.", fg=typer.colors.CYAN)
        raise typer.Exit(code=1)

    current_value = (
        configs[package_name].get("installed_apps")
        if isinstance(configs[package_name], dict)
        else configs[package_name]
    )

    # Update mapping
    if isinstance(configs[package_name], dict):
        configs[package_name]["installed_apps"] = app_name
    else:
        configs[package_name] = {"installed_apps": app_name}

    try:
        save_package_configs(configs)

        typer.secho(f"Updated mapping: {package_name}", fg=typer.colors.GREEN)
        typer.secho(f"  Old: {current_value}", fg=typer.colors.YELLOW)
        typer.secho(
            f"  New: {app_name if app_name else '(not added to INSTALLED_APPS)'}",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@mapping_app.command("remove")
def mapping_remove(
    package_name: str = typer.Argument(..., help="Package name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """
    Remove a package mapping.

    Example:
        django-include-apps mapping remove my-custom-package
    """
    configs = load_package_configs()

    # Check if mapping exists
    if package_name not in configs:
        typer.secho(f"Mapping not found: {package_name}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    current_value = (
        configs[package_name].get("installed_apps")
        if isinstance(configs[package_name], dict)
        else configs[package_name]
    )

    # Ask for confirmation unless --force
    if not force:
        typer.secho(
            f"\nCurrent mapping: {package_name} \u2192 {current_value}",
            fg=typer.colors.YELLOW,
        )
        questions = [
            inquirer.Confirm("remove", message=f"Remove this mapping?", default=False)
        ]
        answers = inquirer.prompt(questions)

        if not answers or not answers["remove"]:
            typer.secho("Cancelled.", fg=typer.colors.CYAN)
            return

    # Remove entry
    del configs[package_name]

    try:
        save_package_configs(configs)
        typer.secho(f"Removed mapping: {package_name}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def rollback(
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    )
):
    """
    Rollback settings.py to a previous backup.

    Shows available backups and lets you choose one to restore.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    settings_file = find_settings_file(start_dir)
    if not settings_file:
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    backups = list_backups(start_dir)

    if not backups:
        typer.secho("No backups available.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    # Show available backups
    typer.echo("\nAvailable backups:\n")
    backup_choices = []
    for i, backup in enumerate(backups[:10], 1):
        timestamp = backup.stem.replace("settings_", "").replace(".py", "")
        size = backup.stat().st_size
        backup_choices.append(f"{i}. {timestamp} ({size} bytes)")

    questions = [
        inquirer.List(
            "backup",
            message="Select backup to restore",
            choices=backup_choices + ["Cancel"],
        )
    ]
    answers = inquirer.prompt(questions)

    if not answers or answers["backup"] == "Cancel":
        typer.secho("Rollback cancelled.", fg=typer.colors.YELLOW)
        return

    # Get selected backup index
    selected_idx = int(answers["backup"].split(".")[0]) - 1
    selected_backup = backups[selected_idx]

    if restore_backup(selected_backup, settings_file):
        show_success(
            "Rollback Complete",
            [f"Restored from: {selected_backup.name}"],
            f"Tip: Run 'python manage.py check' to verify",
        )


@app.command()
def status(
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    )
):
    """
    Show status of installed Django packages.

    Displays all third-party apps in INSTALLED_APPS and their status.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    settings_file = find_settings_file(start_dir)
    if not settings_file:
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    with open(settings_file, "r") as f:
        content = f.read()

    # Extract INSTALLED_APPS
    pattern = r"INSTALLED_APPS\s*=\s*\[(.*?)\]"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        typer.secho("INSTALLED_APPS not found in settings.py", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    apps_content = match.group(1)
    apps = re.findall(r'["\']([^"\']+)["\']', apps_content)

    # Categorize apps
    django_apps = [a for a in apps if a.startswith("django.")]
    third_party = [a for a in apps if not a.startswith("django.")]

    typer.echo()
    typer.secho("┌─────────────────────────────────────────────┐", fg=typer.colors.CYAN)
    typer.secho(
        f"│  Django Project Status                      │", fg=typer.colors.CYAN
    )
    typer.secho("├─────────────────────────────────────────────┤", fg=typer.colors.CYAN)
    typer.secho(f"│  Django Apps: {len(django_apps):<30}│", fg=typer.colors.WHITE)
    typer.secho(f"│  Third-party Apps: {len(third_party):<25}│", fg=typer.colors.WHITE)
    typer.secho("└─────────────────────────────────────────────┘", fg=typer.colors.CYAN)

    if third_party:
        typer.echo("\nThird-party apps:")
        for app in third_party:
            typer.secho(f"  ✓ {app}", fg=typer.colors.GREEN)

    # Check requirements.txt
    req_file = find_requirements_file(start_dir)
    if req_file:
        with open(req_file, "r") as f:
            req_content = f.read()
        req_count = len(
            [l for l in req_content.split("\n") if l.strip() and not l.startswith("#")]
        )
        typer.secho(f"\n  requirements.txt: {req_count} packages", fg=typer.colors.CYAN)

    # Check backups
    backups = list_backups(start_dir)
    if backups:
        typer.secho(f"  Backups available: {len(backups)}", fg=typer.colors.CYAN)

    # ── Configuration Audit (merged from V1 status) ──
    typer.secho("\n── Configuration Audit ──", fg=typer.colors.CYAN, bold=True)
    typer.secho("=" * 60, fg=typer.colors.CYAN)

    urls_content = ""
    urls_path = settings_file.parent / "urls.py"
    if urls_path.exists():
        try:
            urls_content = urls_path.read_text()
        except Exception:
            pass

    configs = load_package_configs()
    mappings = load_package_mappings()

    installed_count = 0
    issues_found = 0

    for pkg_name, pkg_config in configs.items():
        if not is_package_installed(pkg_name):
            continue

        installed_count += 1
        missing_items = []

        # Check Middleware
        if pkg_config.get("middleware"):
            mw = pkg_config["middleware"]
            if isinstance(mw, str):
                if mw not in content:
                    missing_items.append(f"Middleware missing: {mw}")
            elif isinstance(mw, list):
                for m in mw:
                    if m not in content:
                        missing_items.append(f"Middleware missing: {m}")

        # Check Required Settings
        if pkg_config.get("required_settings"):
            for key in pkg_config["required_settings"].keys():
                if key not in content:
                    missing_items.append(f"Setting missing: {key}")

        # Check Imports
        if pkg_config.get("settings_import"):
            imp = pkg_config["settings_import"]
            if imp.strip() not in content:
                missing_items.append(f"Import missing: {imp.strip()}")

        # Check URL Patterns
        if pkg_config.get("url_patterns") and urls_content:
            patterns = pkg_config["url_patterns"]
            if isinstance(patterns, dict):
                inc = patterns.get("include")
                if inc and inc not in urls_content:
                    missing_items.append(f"URL include likely missing: {inc}")
            elif isinstance(patterns, list):
                for p in patterns:
                    if isinstance(p, dict):
                        inc = p.get("include")
                        if inc and inc not in urls_content:
                            missing_items.append(f"URL include likely missing: {inc}")

        if missing_items:
            issues_found += 1
            typer.secho(f" {pkg_name}", fg=typer.colors.YELLOW, bold=True)
            for item in missing_items:
                typer.secho(f"  - {item}", fg=typer.colors.YELLOW)
        else:
            typer.secho(f" {pkg_name} (Configured)", fg=typer.colors.GREEN)

    if installed_count == 0:
        typer.secho(
            "No supported packages found in environment.", fg=typer.colors.YELLOW
        )
    elif issues_found == 0:
        typer.secho(
            f"\nAll {installed_count} supported packages appear consistent.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        typer.secho(
            f"\nFound issues in {issues_found} package(s).",
            fg=typer.colors.YELLOW,
            bold=True,
        )

    typer.echo()


@app.command()
def doctor(
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    )
):
    """
    Run health checks on your Django project configuration.

    Checks for common issues like missing middleware, incorrect settings,
    and security problems.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    typer.secho("Running Health Check...", fg=typer.colors.CYAN, bold=True)

    # ── Environment Info (merged from V1 doctor) ──
    py_version = sys.version.split()[0]
    typer.secho(f"Python Version: {py_version}", fg=typer.colors.GREEN)

    settings_file = find_settings_file(start_dir)
    if settings_file:
        typer.secho(f"settings.py found: {settings_file}", fg=typer.colors.GREEN)
    else:
        typer.secho("settings.py NOT found", fg=typer.colors.RED)
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    req_path = find_requirements_file(start_dir)
    if req_path:
        typer.secho(f"requirements.txt found: {req_path}", fg=typer.colors.GREEN)
    else:
        typer.secho("requirements.txt not found", fg=typer.colors.YELLOW)

    mappings = load_package_mappings()
    configs_data = load_package_configs()
    typer.secho(f"Mappings loaded: {len(mappings)} items", fg=typer.colors.GREEN)
    typer.secho(
        f"Configurations loaded: {len(configs_data)} items", fg=typer.colors.GREEN
    )

    # ── Project Configuration Checks ──
    with open(settings_file, "r") as f:
        content = f.read()

    issues = []
    warnings = []
    passed = []

    # Check 1: INSTALLED_APPS exists
    if "INSTALLED_APPS" in content:
        passed.append("INSTALLED_APPS defined")
    else:
        issues.append("INSTALLED_APPS not found")

    # Check 2: MIDDLEWARE exists
    if "MIDDLEWARE" in content:
        passed.append("MIDDLEWARE defined")
    else:
        warnings.append("MIDDLEWARE not found")

    # Check 3: DEBUG setting
    if "DEBUG = True" in content:
        warnings.append("DEBUG is True (not safe for production)")
    else:
        passed.append("DEBUG is secure")

    # Check 4: SECRET_KEY hardcoded
    if re.search(r'SECRET_KEY\s*=\s*["\'][^"\']+["\']', content):
        warnings.append("SECRET_KEY appears hardcoded (use env variable)")
    else:
        passed.append("SECRET_KEY not hardcoded")

    # Check 5: ALLOWED_HOSTS
    if "ALLOWED_HOSTS" in content:
        if "ALLOWED_HOSTS = []" in content or "ALLOWED_HOSTS=[]" in content:
            warnings.append("ALLOWED_HOSTS is empty")
        else:
            passed.append("ALLOWED_HOSTS configured")
    else:
        warnings.append("ALLOWED_HOSTS not defined")

    # Check 6: Package Configurations
    # Extract installed apps
    pattern = r"INSTALLED_APPS\s*=\s*\[(.*?)\]"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        apps_content = match.group(1)
        installed_apps = set(re.findall(r'["\']([^"\']+)["\']', apps_content))
        third_party_apps = {a for a in installed_apps if not a.startswith("django.")}

        configs = load_package_configs()
        mappings = load_package_mappings()
        reverse_mappings = {}
        for k, v in mappings.items():
            if v:
                if isinstance(v, list):
                    for app_name in v:
                        reverse_mappings[app_name] = k
                else:
                    reverse_mappings[v] = k

        missing_configs = []
        for app in third_party_apps:
            pkg_name = reverse_mappings.get(
                app, app
            )  # fallback to app name if no mapping
            # Ignore some common ones if needed, or just report all
            if pkg_name not in configs:
                # Check if we even have a potential config (optional check)
                missing_configs.append(f"{app} (package: {pkg_name})")

        if missing_configs:
            for m in missing_configs:
                warnings.append(f"No extended config for '{m}'")

    # Display results
    typer.echo()
    typer.secho(
        f"┌─────────────────────────────────────────────┐\n"
        f"│  Doctor Check Results                       │\n"
        f"└─────────────────────────────────────────────┘",
        fg=typer.colors.CYAN,
        bold=True,
    )
    if passed:
        typer.echo("\nPassed:")
        for item in passed:
            typer.secho(f"   ✓ {item}", fg=typer.colors.GREEN)

    if warnings:
        typer.echo("\nWarnings:")
        for item in warnings:
            typer.secho(f"   ! {item}", fg=typer.colors.YELLOW)

    if issues:
        typer.echo("\nIssues:")
        for item in issues:
            typer.secho(f"   ✗ {item}", fg=typer.colors.RED)

    if not issues and not warnings:
        typer.secho(
            "\nAll checks passed! Your project is healthy.", fg=typer.colors.GREEN
        )

    typer.echo()


@app.command("show-config")
def show_config(
    package_name: str = typer.Argument(
        ..., help="Package name to show configuration for"
    ),
    raw_json: bool = typer.Option(
        False, "--json", help="Output raw JSON configuration"
    ),
):
    """
    Show extended configuration for a package.

    Displays middleware, settings, URL patterns, and other configuration
    that would be applied when adding this package.
    """
    config = get_package_config(package_name)

    if not config:
        # Try to find similar packages
        configs = load_package_configs()
        similar = find_similar_packages(package_name, configs)

        if similar:
            show_error(
                "Package Not Found", f"Package: {package_name}", suggestions=similar
            )
        else:
            show_error(
                "Package Not Found", f"No configuration found for: {package_name}"
            )
        raise typer.Exit(code=1)

    # Raw JSON output mode (merged from V1)
    if raw_json:
        typer.secho(
            f"Configuration for '{package_name}':", fg=typer.colors.CYAN, bold=True
        )
        typer.echo(json.dumps(config, indent=4))
        return

    typer.echo()
    typer.secho(f"Configuration for: {package_name}", fg=typer.colors.CYAN, bold=True)
    typer.secho("─" * 50, fg=typer.colors.BRIGHT_BLACK)

    # INSTALLED_APPS
    if config.get("installed_apps"):
        apps = config["installed_apps"]
        if isinstance(apps, list):
            typer.secho("\nINSTALLED_APPS:", fg=typer.colors.GREEN)
            for app in apps:
                typer.echo(f"   • {app}")
        else:
            typer.secho(f"\nINSTALLED_APPS: {apps}", fg=typer.colors.MAGENTA)

    # Middleware
    if config.get("middleware"):
        typer.secho(f"\nMiddleware: {config['middleware']}", fg=typer.colors.YELLOW)
        if config.get("middleware_position"):
            typer.echo(f"   Position: {config['middleware_position']}")

    # Settings
    if config.get("required_settings"):
        typer.secho("\nSettings:", fg=typer.colors.BLUE)
        for key, value in config["required_settings"].items():
            typer.echo(
                f"   {key}: {json.dumps(value, indent=6) if isinstance(value, dict) else value}"
            )

    # URL Patterns
    if config.get("url_patterns"):
        typer.secho("\nURL Patterns:", fg=typer.colors.MAGENTA)
        patterns = config["url_patterns"]
        if isinstance(patterns, list):
            for p in patterns:
                typer.echo(f"   path('{p['pattern']}', include('{p['include']}'))")
        else:
            typer.echo(
                f"   path('{patterns['pattern']}', include('{patterns['include']}'))"
            )

    # Dependencies
    if config.get("dependencies"):
        typer.secho(
            f"\nDependencies: {', '.join(config['dependencies'])}",
            fg=typer.colors.CYAN,
        )

    # Migrations
    if config.get("requires_migrations"):
        typer.secho(f"\nRequires migrations: Yes", fg=typer.colors.YELLOW)

    typer.echo()


@app.command()
def completion(
    shell: str = typer.Argument(None, help="Shell type: bash, zsh, or fish"),
    install: bool = typer.Option(
        False, "--install", help="Install completion for the specified shell"
    ),
):
    """
    Generate shell completion scripts for bash, zsh, or fish.

    Examples:
        # Show completion script for bash
        django-include-apps completion bash

        # Install completion for bash
        django-include-apps completion bash --install
    """
    if not shell:
        typer.echo("Shell completion setup:\n")
        typer.echo("Bash:")
        typer.echo("  django-include-apps completion bash --install")
        typer.echo("  Or manually: django-include-apps completion bash >> ~/.bashrc\n")

        typer.echo("Zsh:")
        typer.echo("  django-include-apps completion zsh --install")
        typer.echo("  Or manually: django-include-apps completion zsh >> ~/.zshrc\n")

        typer.echo("Fish:")
        typer.echo("  django-include-apps completion fish --install")
        typer.echo(
            "  Or manually: django-include-apps completion fish > ~/.config/fish/completions/django-include-apps.fish\n"
        )
        return

    shell = shell.lower()

    if shell not in ["bash", "zsh", "fish"]:
        typer.secho(
            f"Unsupported shell: {shell}. Supported shells: bash, zsh, fish",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Generate completion script using typer's built-in support
    completion_script = typer.completion.get_completion_script(
        prog_name="django-include-apps",
        complete_var="_DJANGO_INCLUDE_APPS_COMPLETE",
        shell=shell,
    )

    if install:
        import platform

        home = Path.home()

        if shell == "bash":
            rc_file = home / ".bashrc"
            marker = "# django-include-apps completion"

            if rc_file.exists():
                content = rc_file.read_text()
                if marker in content:
                    typer.secho(
                        "Completion already installed in ~/.bashrc",
                        fg=typer.colors.YELLOW,
                    )
                    return

            with open(rc_file, "a") as f:
                f.write(f"\n{marker}\n")
                f.write(completion_script)
                f.write("\n")

            typer.secho(f"Completion installed to {rc_file}", fg=typer.colors.GREEN)
            typer.secho(
                "Run 'source ~/.bashrc' or restart your terminal", fg=typer.colors.CYAN
            )

        elif shell == "zsh":
            rc_file = home / ".zshrc"
            marker = "# django-include-apps completion"

            if rc_file.exists():
                content = rc_file.read_text()
                if marker in content:
                    typer.secho(
                        "Completion already installed in ~/.zshrc",
                        fg=typer.colors.YELLOW,
                    )
                    return

            with open(rc_file, "a") as f:
                f.write(f"\n{marker}\n")
                f.write(completion_script)
                f.write("\n")

            typer.secho(f"Completion installed to {rc_file}", fg=typer.colors.GREEN)
            typer.secho(
                "Run 'source ~/.zshrc' or restart your terminal", fg=typer.colors.CYAN
            )

        elif shell == "fish":
            fish_dir = home / ".config" / "fish" / "completions"
            fish_dir.mkdir(parents=True, exist_ok=True)
            fish_file = fish_dir / "django-include-apps.fish"

            with open(fish_file, "w") as f:
                f.write(completion_script)

            typer.secho(f"Completion installed to {fish_file}", fg=typer.colors.GREEN)
            typer.secho(
                "Restart your terminal or run 'source ~/.config/fish/config.fish'",
                fg=typer.colors.CYAN,
            )
    else:
        # Just print the completion script
        typer.echo(completion_script)


# ============================================================================
# Virtual Environment & Python Commands
# ============================================================================


@app.command("init-env")
def init_env(
    python_version: str = typer.Option(
        None, "--python", "-p", help="Python version (e.g., 3.10, 3.11)"
    ),
    name: str = typer.Option("venv", "--name", "-n", help="Virtual environment name"),
    start_dir: Path = typer.Option(None, "--start-dir", "-d", help="Project directory"),
):
    """
    Create a virtual environment with optional Python version selection.

    Examples:
        django-include-apps init-env
        django-include-apps init-env --python 3.11
        django-include-apps init-env --name .venv --python 3.10
    """
    import subprocess
    import platform

    if start_dir is None:
        start_dir = Path.cwd()

    venv_path = start_dir / name

    if venv_path.exists():
        typer.secho(
            f"Virtual environment '{name}' already exists.", fg=typer.colors.YELLOW
        )
        questions = [
            inquirer.Confirm(
                "recreate", message="Do you want to recreate it?", default=False
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers or not answers["recreate"]:
            return
        shutil.rmtree(venv_path)

    # Determine Python executable
    if python_version:
        # Try to find specific Python version
        if platform.system() == "Windows":
            python_cmd = f"py -{python_version}"
        else:
            python_cmd = f"python{python_version}"
    else:
        python_cmd = "python"

    typer.secho(f"Creating virtual environment '{name}'...", fg=typer.colors.CYAN)

    try:
        result = subprocess.run(
            f"{python_cmd} -m venv {venv_path}",
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            show_error(
                "Failed to create virtual environment",
                result.stderr[:100] if result.stderr else "Unknown error",
            )
            raise typer.Exit(code=1)

        # Show activation instructions
        if platform.system() == "Windows":
            activate_cmd = f"{name}\\Scripts\\activate"
        else:
            activate_cmd = f"source {name}/bin/activate"

        show_success(
            "Virtual Environment Created",
            [f"Location: {venv_path}", f"Python: {python_version or 'default'}"],
            footer=f"Activate with: {activate_cmd}",
        )

        # Auto-add to .gitignore (merged from V1 init_env)
        gitignore_path = start_dir / ".gitignore"
        if gitignore_path.exists():
            gi_content = gitignore_path.read_text()
            if name not in gi_content:
                with open(gitignore_path, "a") as gi_f:
                    gi_f.write(f"\n{name}/\n")
                typer.secho(f"Added '{name}/' to .gitignore", fg=typer.colors.GREEN)
        else:
            # Create .gitignore with the env directory
            with open(gitignore_path, "w") as gi_f:
                gi_f.write(f"{name}/\n")
            typer.secho(f"Created .gitignore with '{name}/'", fg=typer.colors.GREEN)

    except Exception as e:
        show_error("Error creating virtual environment", str(e))
        raise typer.Exit(code=1)


@app.command()
def diff(
    package_name: str = typer.Argument(..., help="Package to preview changes for"),
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    ),
):
    """
    Preview changes that would be made when adding a package.

    Shows what would be added to INSTALLED_APPS, middleware, settings, etc.
    without actually making any changes.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    # Get package configuration
    config = get_package_config(package_name)
    mappings = load_package_mappings()

    typer.echo()
    typer.secho(f"Preview: Adding {package_name}", fg=typer.colors.CYAN, bold=True)
    typer.secho("─" * 50, fg=typer.colors.BRIGHT_BLACK)
    typer.secho("(Dry run - no changes will be made)\n", fg=typer.colors.YELLOW)

    # INSTALLED_APPS
    app_name = None
    if config and config.get("installed_apps"):
        app_name = config["installed_apps"]
    elif package_name in mappings:
        app_name = mappings[package_name]

    if app_name:
        typer.secho("INSTALLED_APPS:", fg=typer.colors.GREEN)
        if isinstance(app_name, list):
            for a in app_name:
                typer.secho(f"   + '{a}',", fg=typer.colors.GREEN)
        else:
            typer.secho(f"   + '{app_name}',", fg=typer.colors.GREEN)
    else:
        typer.secho(
            "INSTALLED_APPS: (will prompt for app name)", fg=typer.colors.YELLOW
        )

    if config:
        # Middleware
        if config.get("middleware"):
            typer.secho(f"\nMIDDLEWARE:", fg=typer.colors.YELLOW)
            typer.secho(f"   + '{config['middleware']}',", fg=typer.colors.YELLOW)
            if config.get("middleware_position"):
                typer.echo(f"   (Position: {config['middleware_position']})")

        # Settings
        if config.get("required_settings"):
            typer.secho(f"\nSettings to add:", fg=typer.colors.BLUE)
            for key in config["required_settings"]:
                typer.echo(f"   + {key} = ...")

        # URL patterns
        if config.get("url_patterns"):
            typer.secho(f"\nURL Patterns:", fg=typer.colors.MAGENTA)
            patterns = config["url_patterns"]
            if isinstance(patterns, list):
                for p in patterns:
                    typer.echo(f"   + path('{p.get('pattern', '')}', ...)")
            else:
                typer.echo(f"   + path('{patterns.get('pattern', '')}', ...)")

        # Dependencies
        if config.get("dependencies"):
            typer.secho(f"\nAdditional packages:", fg=typer.colors.CYAN)
            for dep in config["dependencies"]:
                typer.echo(f"   + {dep}")

        # Migrations
        if config.get("requires_migrations"):
            typer.secho(
                f"\nWill require: python manage.py migrate", fg=typer.colors.YELLOW
            )

        # Database Configuration (merged from V1 diff)
        if config.get("database_engine"):
            typer.secho("\nDatabase:", fg=typer.colors.MAGENTA)
            typer.echo(f"   + Would inject database configuration template")
            typer.echo(f"     Engine: {config['database_engine']}")

    typer.echo()


@app.command()
def sync(
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
):
    """
    Synchronize INSTALLED_APPS with requirements.txt.

    Shows packages in requirements.txt not in INSTALLED_APPS and vice versa.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    settings_file = find_settings_file(start_dir)
    req_file = find_requirements_file(start_dir)

    if not settings_file:
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    if not req_file:
        show_error(
            "Requirements Not Found", f"No requirements.txt found in {start_dir}"
        )
        raise typer.Exit(code=1)

    # Get apps from settings.py
    with open(settings_file, "r") as f:
        content = f.read()

    pattern = r"INSTALLED_APPS\s*=\s*\[(.*?)\]"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        typer.secho("INSTALLED_APPS not found in settings.py", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    apps_content = match.group(1)
    installed_apps = set(re.findall(r'["\']([^"\']+)["\']', apps_content))
    third_party_apps = {a for a in installed_apps if not a.startswith("django.")}

    # Get packages from requirements.txt
    with open(req_file, "r") as f:
        req_content = f.read()

    req_packages = set()
    for line in req_content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            # Extract package name (without version specifier)
            pkg_name = re.split(r"[=<>~!]", line)[0].strip()
            req_packages.add(pkg_name)

    # Load mappings for comparison
    mappings = load_package_mappings()
    reverse_mappings = {}
    for k, v in mappings.items():
        if v:
            if isinstance(v, list):
                for app_name in v:
                    reverse_mappings[app_name] = k
            else:
                reverse_mappings[v] = k

    # Find mismatches
    typer.echo()
    typer.secho("┌─────────────────────────────────────────────┐", fg=typer.colors.CYAN)
    typer.secho("│  Sync Analysis                              │", fg=typer.colors.CYAN)
    typer.secho("└─────────────────────────────────────────────┘", fg=typer.colors.CYAN)

    # Django packages in requirements but not in INSTALLED_APPS
    missing_in_settings = []
    for pkg in req_packages:
        if pkg in mappings and mappings[pkg]:
            if mappings[pkg] not in third_party_apps:
                missing_in_settings.append((pkg, mappings[pkg]))

    if missing_in_settings:
        typer.echo("\nIn requirements.txt but not in INSTALLED_APPS:")
        for pkg, app in missing_in_settings:
            typer.secho(f"   • {pkg} → {app}", fg=typer.colors.YELLOW)

    # Apps in INSTALLED_APPS potentially not in requirements
    missing_in_req = []
    for app in third_party_apps:
        pkg = reverse_mappings.get(app, app)
        found = False
        for req_pkg in req_packages:
            if pkg.lower() in req_pkg.lower() or req_pkg.lower() in pkg.lower():
                found = True
                break
        if not found:
            missing_in_req.append((app, pkg))

    if missing_in_req:
        typer.echo("\nIn INSTALLED_APPS but not in requirements.txt:")
        for app, pkg in missing_in_req:
            typer.secho(f"   • {app} (package: {pkg})", fg=typer.colors.YELLOW)

    if not missing_in_settings and not missing_in_req:
        typer.secho("\nEverything is in sync!", fg=typer.colors.GREEN)

    typer.echo()


@app.command("update-configs")
def update_configs():
    """
    Check for updated package configurations.

    Shows information about the current configuration file and
    provides instructions for updating to the latest version.
    """
    config_file = Path(__file__).parent / "package_configs.json"

    typer.echo()
    typer.secho("Configuration Status", fg=typer.colors.CYAN, bold=True)
    typer.secho("─" * 40, fg=typer.colors.BRIGHT_BLACK)

    # Check package_configs.json
    if config_file.exists():
        configs = load_package_configs()
        mappings = load_package_mappings()
        typer.secho(
            f"\npackage_configs.json: {len(configs)} packages, {len(mappings)} mappings",
            fg=typer.colors.GREEN,
        )
        typer.echo(f"  Location: {config_file}")
    else:
        typer.secho("\npackage_configs.json: Not found", fg=typer.colors.RED)

    typer.echo()
    typer.secho("To update to the latest configurations:", fg=typer.colors.YELLOW)

    # Simple check for latest version on PyPI
    try:
        response = requests.get(
            "https://pypi.org/pypi/django-include-apps/json", timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            latest_version = data["info"]["version"]
            import django_include_apps

            current_version = getattr(django_include_apps, "__version__", "0.0.0")

            if latest_version != current_version:
                typer.secho(
                    f"New version {latest_version} available (Current: {current_version})",
                    fg=typer.colors.GREEN,
                )
                typer.echo("   pip install --upgrade django-include-apps")
            else:
                typer.secho("You are using the latest version.", fg=typer.colors.GREEN)
    except Exception:
        pass

    typer.echo("   pip install --upgrade django-include-apps")
    typer.echo()


# ============================================================================
# Config Profiles
# ============================================================================

profile_app = typer.Typer(help="Manage configuration profiles")
app.add_typer(profile_app, name="profile")

@profile_app.callback(invoke_without_command=True)
def profile_callback(ctx: typer.Context):
    """Manage configuration profiles."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@profile_app.command("save")
def profile_save(
    name: str = typer.Argument(..., help="Profile name"),
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    ),
):
    """
    Save current INSTALLED_APPS configuration as a profile.

    Example:
        django-include-apps profile save my-api-setup
    """
    if start_dir is None:
        start_dir = Path.cwd()

    settings_file = find_settings_file(start_dir)
    if not settings_file:
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    with open(settings_file, "r") as f:
        content = f.read()

    # Extract INSTALLED_APPS
    pattern = r"INSTALLED_APPS\s*=\s*\[(.*?)\]"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        typer.secho("INSTALLED_APPS not found in settings.py", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    apps_content = match.group(1)
    apps = re.findall(r'["\']([^"\']+)["\']', apps_content)
    third_party = [a for a in apps if not a.startswith("django.")]

    # Save profile
    profiles_dir = Path(__file__).parent / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    profile_file = profiles_dir / f"{name}.json"
    profile_data = {
        "name": name,
        "created": datetime.now().isoformat(),
        "apps": third_party,
    }

    with open(profile_file, "w") as f:
        json.dump(profile_data, f, indent=2)

    show_success(
        f"Profile '{name}' Saved",
        [f"{len(third_party)} apps saved"],
        footer=f"Apply with: django-include-apps profile apply {name}",
    )


@profile_app.command("list")
def profile_list():
    """
    List all saved profiles.
    """
    profiles_dir = Path(__file__).parent / "profiles"

    if not profiles_dir.exists():
        typer.secho("No profiles saved yet.", fg=typer.colors.YELLOW)
        return

    profiles = list(profiles_dir.glob("*.json"))

    if not profiles:
        typer.secho("No profiles saved yet.", fg=typer.colors.YELLOW)
        return

    typer.echo()
    typer.secho("Saved Profiles:", fg=typer.colors.CYAN, bold=True)
    typer.secho("─" * 40, fg=typer.colors.BRIGHT_BLACK)

    for profile_file in profiles:
        with open(profile_file, "r") as f:
            data = json.load(f)

        name = data.get("name", profile_file.stem)
        apps_count = len(data.get("apps", []))
        typer.echo(f"  • {name} ({apps_count} apps)")

    typer.echo()


@profile_app.command("apply")
def profile_apply(
    name: str = typer.Argument(..., help="Profile name to apply"),
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    ),
):
    """
    Apply a saved profile to the current project.

    Example:
        django-include-apps profile apply my-api-setup
    """
    if start_dir is None:
        start_dir = Path.cwd()

    profiles_dir = Path(__file__).parent / "profiles"
    profile_file = profiles_dir / f"{name}.json"

    if not profile_file.exists():
        show_error("Profile Not Found", f"No profile named '{name}'")
        raise typer.Exit(code=1)

    with open(profile_file, "r") as f:
        profile_data = json.load(f)

    apps = profile_data.get("apps", [])

    if not apps:
        typer.secho("Profile is empty.", fg=typer.colors.YELLOW)
        return

    typer.echo(f"\nProfile '{name}' contains {len(apps)} apps:")
    for app in apps:
        typer.secho(f"   • {app}", fg=typer.colors.CYAN)

    questions = [
        inquirer.Confirm(
            "apply", message="Add these apps to INSTALLED_APPS?", default=True
        )
    ]
    answers = inquirer.prompt(questions)

    if not answers or not answers["apply"]:
        typer.secho("Cancelled.", fg=typer.colors.YELLOW)
        return

    settings_file = find_settings_file(start_dir)
    if not settings_file:
        show_error("Settings Not Found", f"No settings.py found in {start_dir}")
        raise typer.Exit(code=1)

    # Create backup
    create_backup(settings_file, start_dir)

    # Add apps
    added = 0
    for app in apps:
        try:
            add_app_to_installed_apps(settings_file, app)
            added += 1
        except Exception:
            pass  # App might already exist

    show_success(f"Profile '{name}' Applied", [f"Added {added} apps to INSTALLED_APPS"])


@profile_app.command("export")
def profile_export(name: str = typer.Argument(..., help="Profile name to export")):
    """
    Export a profile as JSON (outputs to stdout).

    Example:
        django-include-apps profile export my-api-setup > setup.json
    """
    profiles_dir = Path(__file__).parent / "profiles"
    profile_file = profiles_dir / f"{name}.json"

    if not profile_file.exists():
        show_error("Profile Not Found", f"No profile named '{name}'")
        raise typer.Exit(code=1)

    with open(profile_file, "r") as f:
        content = f.read()

    typer.echo(content)


# ============================================================================
# Dependency Graph Visualization
# ============================================================================


@app.command("graph")
def dependency_graph(
    start_dir: Path = typer.Option(
        None, "--start-dir", "-d", help="Directory to search for settings.py"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (supports .txt, .json)"
    ),
    format_type: str = typer.Option(
        "ascii", "--format", "-f", help="Output format: ascii, json"
    ),
):
    """
    Visualize package dependencies as a graph.

    Shows which packages depend on other packages based on package_configs.json.

    Examples:
        django-include-apps graph
        django-include-apps graph --format json --output deps.json
    """
    if start_dir is None:
        start_dir = Path.cwd()

    settings_file = find_settings_file(start_dir)

    # Get installed apps
    installed_apps = set()
    if settings_file:
        with open(settings_file, "r") as f:
            content = f.read()
        pattern = r"INSTALLED_APPS\s*=\s*\[(.*?)\]"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            apps_content = match.group(1)
            installed_apps = set(re.findall(r'["\']([^"\']+)["\']', apps_content))

    # Load configs
    configs = load_package_configs()
    mappings = load_package_mappings()

    # Reverse lookup: app_name -> package_name
    app_to_pkg = {}
    for pkg, app in mappings.items():
        if app:
            if isinstance(app, list):
                for app_name in app:
                    app_to_pkg[app_name] = pkg
            else:
                app_to_pkg[app] = pkg

    # Build dependency graph
    graph = {}
    for pkg, config in configs.items():
        if config.get("installed_apps"):
            app_name = config["installed_apps"]
            if isinstance(app_name, list):
                app_name = app_name[0]

            deps = config.get("dependencies", [])
            graph[pkg] = {
                "app_name": app_name,
                "dependencies": deps,
                "installed": app_name in installed_apps
                or any(
                    a in installed_apps
                    for a in config.get("installed_apps", [])
                    if isinstance(config.get("installed_apps"), list)
                ),
            }

    if format_type == "json":
        import json as json_module

        output_data = json_module.dumps(graph, indent=2)
        if output:
            with open(output, "w") as f:
                f.write(output_data)
            typer.secho(f"Graph saved to {output}", fg=typer.colors.GREEN)
        else:
            typer.echo(output_data)
        return

    # ASCII format
    typer.echo()
    typer.secho("Dependency Graph", fg=typer.colors.CYAN, bold=True)
    typer.secho("═" * 50, fg=typer.colors.CYAN)

    # Show packages with dependencies
    has_deps = False
    for pkg, info in sorted(graph.items()):
        if info["dependencies"]:
            has_deps = True
            status = "✓" if info["installed"] else "○"
            color = (
                typer.colors.GREEN if info["installed"] else typer.colors.BRIGHT_BLACK
            )
            typer.secho(f"\n{status} {pkg}", fg=color, bold=True)
            for dep in info["dependencies"]:
                dep_installed = graph.get(dep, {}).get("installed", False)
                dep_status = "✓" if dep_installed else "○"
                dep_color = typer.colors.GREEN if dep_installed else typer.colors.YELLOW
                typer.secho(f"   └── {dep_status} {dep}", fg=dep_color)

    if not has_deps:
        typer.secho(
            "\nNo dependencies found in installed packages.", fg=typer.colors.YELLOW
        )

    typer.echo()
    typer.secho(
        "Legend: ✓ = installed, ○ = not installed", fg=typer.colors.BRIGHT_BLACK
    )
    typer.echo()

    if output:
        # Save ASCII to file
        lines = []
        lines.append("Dependency Graph")
        lines.append("=" * 50)
        for pkg, info in sorted(graph.items()):
            if info["dependencies"]:
                status = "[x]" if info["installed"] else "[ ]"
                lines.append(f"\n{status} {pkg}")
                for dep in info["dependencies"]:
                    dep_installed = graph.get(dep, {}).get("installed", False)
                    dep_status = "[x]" if dep_installed else "[ ]"
                    lines.append(f"    └── {dep_status} {dep}")

        with open(output, "w") as f:
            f.write("\n".join(lines))
        typer.secho(f"Graph saved to {output}", fg=typer.colors.GREEN)


# ============================================================================
# Pre-commit Hooks Setup
# ============================================================================


@app.command("setup-hooks")
def setup_hooks(
    start_dir: Path = typer.Option(None, "--start-dir", "-d", help="Project directory"),
    tools: str = typer.Option(
        "black,isort,flake8", "--tools", "-t", help="Comma-separated list of tools"
    ),
):
    """
    Set up pre-commit hooks for code quality.

    Installs and configures pre-commit with common Python tools.

    Available tools: black, isort, flake8, mypy, pylint

    Examples:
        django-include-apps setup-hooks
        django-include-apps setup-hooks --tools black,isort,mypy
    """
    if start_dir is None:
        start_dir = Path.cwd()

    tool_list = [t.strip() for t in tools.split(",")]

    typer.echo()
    typer.secho("Setting up pre-commit hooks", fg=typer.colors.CYAN, bold=True)
    typer.secho("─" * 40, fg=typer.colors.BRIGHT_BLACK)
    typer.echo(f"Tools: {', '.join(tool_list)}")
    typer.echo()

    # Define hook configurations
    hook_configs = {
        "black": {
            "repo": "https://github.com/psf/black",
            "rev": "24.10.0",
            "hooks": [{"id": "black", "language_version": "python3"}],
        },
        "isort": {
            "repo": "https://github.com/pycqa/isort",
            "rev": "5.13.2",
            "hooks": [{"id": "isort", "args": ["--profile", "black"]}],
        },
        "flake8": {
            "repo": "https://github.com/pycqa/flake8",
            "rev": "7.1.1",
            "hooks": [
                {
                    "id": "flake8",
                    "args": ["--max-line-length=88", "--extend-ignore=E203"],
                }
            ],
        },
        "mypy": {
            "repo": "https://github.com/pre-commit/mirrors-mypy",
            "rev": "v1.13.0",
            "hooks": [{"id": "mypy"}],
        },
        "pylint": {
            "repo": "https://github.com/pylint-dev/pylint",
            "rev": "v3.3.2",
            "hooks": [{"id": "pylint"}],
        },
    }

    # Build pre-commit config
    repos = []
    for tool in tool_list:
        if tool in hook_configs:
            repos.append(hook_configs[tool])
        else:
            typer.secho(f"Unknown tool: {tool}", fg=typer.colors.YELLOW)

    if not repos:
        typer.secho("No valid tools specified.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    pre_commit_config = {"repos": repos}

    # Write .pre-commit-config.yaml
    config_file = start_dir / ".pre-commit-config.yaml"

    # Manual YAML-like output (avoid yaml dependency)
    lines = ["repos:"]
    for repo in repos:
        lines.append(f"  - repo: {repo['repo']}")
        lines.append(f"    rev: {repo['rev']}")
        lines.append("    hooks:")
        for hook in repo["hooks"]:
            lines.append(f"      - id: {hook['id']}")
            if "language_version" in hook:
                lines.append(f"        language_version: {hook['language_version']}")
            if "args" in hook:
                args_str = ", ".join(
                    [f'"{a}"' if " " in a else a for a in hook["args"]]
                )
                lines.append(f"        args: [{args_str}]")

    with open(config_file, "w") as f:
        f.write("\n".join(lines) + "\n")

    show_success(
        "Pre-commit Hooks Configured",
        [f"Created: .pre-commit-config.yaml", f"Tools: {', '.join(tool_list)}"],
        footer="Run: pip install pre-commit && pre-commit install",
    )


# ============================================================================
# Tutorial Mode
# ============================================================================


@app.command("tutorial")
def tutorial(
    topic: str = typer.Argument(None, help="Topic to learn about"),
):
    """
    Interactive tutorial mode for learning Django Include Apps.

    Topics: basics, packages, profiles, security, hooks

    Examples:
        django-include-apps tutorial
        django-include-apps tutorial basics
        django-include-apps tutorial security
    """
    tutorials = {
        "basics": {
            "title": "Getting Started with Django Include Apps",
            "steps": [
                ("Adding a package", "django-include-apps add-app djangorestframework"),
                ("Remove a package", "django-include-apps remove-app rest_framework"),
                ("View mappings", "django-include-apps view-mappings"),
                ("Status check", "django-include-apps status"),
            ],
        },
        "packages": {
            "title": "Working with Packages",
            "steps": [
                (
                    "Add multiple packages",
                    "django-include-apps add-apps djangorestframework django-cors-headers",
                ),
                (
                    "Add with version",
                    "django-include-apps add-app djangorestframework==3.14.0",
                ),
                ("Preview changes", "django-include-apps diff djangorestframework"),
                ("Sync requirements", "django-include-apps sync"),
            ],
        },
        "profiles": {
            "title": "Using Configuration Profiles",
            "steps": [
                ("Save current setup", "django-include-apps profile save my-api"),
                ("List profiles", "django-include-apps profile list"),
                ("Apply profile", "django-include-apps profile apply my-api"),
                (
                    "Export profile",
                    "django-include-apps profile export my-api > backup.json",
                ),
            ],
        },
        "security": {
            "title": "Security Configuration",
            "steps": [
                ("Run health check", "django-include-apps doctor"),
                ("Secure settings", "django-include-apps secure-settings"),
                ("View .env.example", "Check .env.example for required variables"),
                ("Backup/rollback", "django-include-apps rollback"),
            ],
        },
        "hooks": {
            "title": "Pre-commit Hooks",
            "steps": [
                ("Setup hooks", "django-include-apps setup-hooks"),
                ("Custom tools", "django-include-apps setup-hooks --tools black,mypy"),
                ("Install hooks", "pip install pre-commit && pre-commit install"),
                ("Run manually", "pre-commit run --all-files"),
            ],
        },
    }

    if topic is None:
        typer.echo()
        typer.secho("Django Include Apps Tutorial", fg=typer.colors.CYAN, bold=True)
        typer.secho("═" * 45, fg=typer.colors.CYAN)
        typer.echo("\nAvailable topics:\n")
        for key, val in tutorials.items():
            typer.secho(f"  • {key}", fg=typer.colors.GREEN)
            typer.echo(f"    {val['title']}")
        typer.echo()
        typer.secho(
            "Usage: django-include-apps tutorial <topic>", fg=typer.colors.YELLOW
        )
        typer.echo()
        return

    if topic not in tutorials:
        typer.secho(f"Unknown topic: {topic}", fg=typer.colors.RED)
        typer.echo("Available topics: " + ", ".join(tutorials.keys()))
        raise typer.Exit(code=1)

    tut = tutorials[topic]
    typer.echo()
    typer.secho(tut["title"], fg=typer.colors.CYAN, bold=True)
    typer.secho("═" * 50, fg=typer.colors.CYAN)

    for i, (step_name, command) in enumerate(tut["steps"], 1):
        typer.echo()
        typer.secho(f"Step {i}: {step_name}", fg=typer.colors.GREEN, bold=True)
        typer.secho(f"  $ {command}", fg=typer.colors.YELLOW)

    typer.echo()
    typer.secho(
        "💡 Tip: Run any command with --help for more options",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.echo()


# ============================================================================
# Docker Support
# ============================================================================


@app.command("docker-init")
def docker_init(
    start_dir: Path = typer.Option(None, "--start-dir", "-d", help="Project directory"),
    python_version: str = typer.Option("3.11", "--python", "-p", help="Python version"),
    include_nginx: bool = typer.Option(
        False, "--nginx", help="Include nginx configuration"
    ),
    include_postgres: bool = typer.Option(
        True, "--postgres", help="Include PostgreSQL"
    ),
):
    """
    Generate Docker configuration files for Django projects.

    Creates Dockerfile, docker-compose.yml, and related files.

    Examples:
        django-include-apps docker-init
        django-include-apps docker-init --python 3.12 --nginx
    """
    if start_dir is None:
        start_dir = Path.cwd()

    typer.echo()
    typer.secho("🐳 Docker Configuration Generator", fg=typer.colors.CYAN, bold=True)
    typer.secho("─" * 40, fg=typer.colors.BRIGHT_BLACK)

    # Generate Dockerfile
    dockerfile_content = f"""# Python Django Dockerfile
FROM python:{python_version}-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
"""

    # Generate docker-compose.yml
    compose_services = {
        "web": f"""  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db"""
    }

    if include_postgres:
        compose_services[
            "db"
        ] = """  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      - POSTGRES_DB=django_db
      - POSTGRES_USER=django_user
      - POSTGRES_PASSWORD=django_pass"""

    if include_nginx:
        compose_services[
            "nginx"
        ] = """  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - static_volume:/app/staticfiles
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - web"""

    compose_content = f"""version: "3.9"

services:
{chr(10).join(compose_services.values())}

volumes:
  postgres_data:
  static_volume:
"""

    # Write files
    files_created = []

    dockerfile_path = start_dir / "Dockerfile"
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    files_created.append("Dockerfile")

    compose_path = start_dir / "docker-compose.yml"
    with open(compose_path, "w") as f:
        f.write(compose_content)
    files_created.append("docker-compose.yml")

    # Create .dockerignore if not exists
    dockerignore_path = start_dir / ".dockerignore"
    if not dockerignore_path.exists():
        dockerignore_content = """__pycache__
*.py[cod]
*$py.class
*.so
.Python
.env
.venv
env/
venv/
.git
.gitignore
*.sqlite3
staticfiles/
media/
"""
        with open(dockerignore_path, "w") as f:
            f.write(dockerignore_content)
        files_created.append(".dockerignore")

    # Create nginx.conf if nginx enabled
    if include_nginx:
        nginx_path = start_dir / "nginx.conf"
        nginx_content = """upstream django {
    server web:8000;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static/ {
        alias /app/staticfiles/;
    }
}
"""
        with open(nginx_path, "w") as f:
            f.write(nginx_content)
        files_created.append("nginx.conf")

    show_success(
        "Docker Configuration Created",
        [f"Created: {', '.join(files_created)}", f"Python: {python_version}"],
        footer="Run: docker-compose up --build",
    )


if __name__ == "__main__":
    app()
