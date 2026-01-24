import os
import re
import subprocess
import sys
import json
import requests
from pathlib import Path
import inquirer
import typer
from typing import List, Set, Optional
from importlib.metadata import PackageNotFoundError, version

app = typer.Typer()

# Get version from package metadata
try:
    __version__ = version("django-include-apps")
except PackageNotFoundError:
    __version__ = "1.0.0"

def version_callback(value: bool):
    """Show version and exit"""
    if value:
        typer.echo(f"django-include-apps version {__version__}")
        raise typer.Exit()

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
    pattern = r'^([a-zA-Z0-9\-_.]+)(==|>=|<=|>|<|~=|!=)(.+)$'
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
        typer.secho(f"Error checking package '{package}' on PyPI: {e}", fg=typer.colors.RED)
        return False

def is_default_django_app(app_name: str) -> bool:
    """Check if an app is a default Django app (starts with 'django.')"""
    return app_name.startswith('django.')

# ============================================================================
# Package Mapping Functions
# ============================================================================

def load_package_mappings() -> dict:
    """Load package-to-app-name mappings from JSON file"""
    mapping_file = Path(__file__).parent / "package_mappings.json"
    if mapping_file.exists():
        try:
            with open(mapping_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            typer.secho("Error loading package mappings. Using empty mappings.", fg=typer.colors.YELLOW)
            return {}
    return {}

def update_package_mappings(package_name: str, app_name: str):
    """Add a new package-to-app mapping to the JSON file"""
    mapping_file = Path(__file__).parent / "package_mappings.json"
    mappings = load_package_mappings()
    
    # Check if mapping already exists
    if package_name in mappings:
        current_value = mappings[package_name]
        
        # If same value, no need to update
        if current_value == app_name:
            typer.secho(f"Mapping already exists with same value: {package_name} → {app_name}", fg=typer.colors.CYAN)
            return
        
        # Ask for confirmation to update
        typer.secho(f"\nMapping already exists: {package_name} → {current_value}", fg=typer.colors.YELLOW)
        questions = [
            inquirer.Confirm(
                'update',
                message=f"Update mapping to '{app_name}'?",
                default=False
            )
        ]
        answers = inquirer.prompt(questions)
        
        if not answers or not answers['update']:
            typer.secho("Keeping existing mapping.", fg=typer.colors.CYAN)
            return
        
        typer.secho(f"Updating: {package_name} → {app_name}", fg=typer.colors.BLUE)
    
    # Add new mapping
    mappings[package_name] = app_name
    
    # Sort mappings alphabetically for better readability
    sorted_mappings = dict(sorted(mappings.items()))
    
    # Write back to file
    try:
        with open(mapping_file, 'w') as f:
            json.dump(sorted_mappings, f, indent=4)
        typer.secho(f"Saved mapping: {package_name} → {app_name}", fg=typer.colors.GREEN)
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
        with open(req_file, 'r') as f:
            lines = f.readlines()
        
        # Check if package already exists
        package_found = False
        new_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith(package_name + '==') or line_stripped == package_name:
                # Update version
                new_lines.append(f"{package_name}=={package_version}\n")
                package_found = True
            else:
                new_lines.append(line)
        
        if not package_found:
            new_lines.append(f"{package_name}=={package_version}\n")
        
        with open(req_file, 'w') as f:
            f.writelines(new_lines)
    else:
        # Create new requirements.txt
        with open(req_file, 'w') as f:
            f.write(f"{package_name}=={package_version}\n")

def remove_from_requirements(req_file: Path, package_name: str):
    """Remove a package from requirements.txt"""
    if not req_file.exists():
        return
    
    with open(req_file, 'r') as f:
        lines = f.readlines()
    
    new_lines = [line for line in lines if not line.strip().startswith(package_name)]
    
    with open(req_file, 'w') as f:
        f.writelines(new_lines)

def generate_requirements_from_project(start_dir: Path, settings_file: Path, mappings: dict) -> List[str]:
    """Scan project and generate list of required packages based on INSTALLED_APPS"""
    # Read INSTALLED_APPS
    with open(settings_file, 'r') as f:
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
        dirs[:] = [d for d in dirs if d not in ['venv', 'env', '.venv', 'node_modules', '__pycache__', '.git', 'migrations']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    return python_files

def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file"""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Match: import package, from package import ...
            import_pattern = re.compile(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', re.MULTILINE)
            for match in import_pattern.finditer(content):
                module = match.group(1).split('.')[0]  # Get root module
                imports.add(module)
    except Exception:
        # Silently skip files that can't be read
        pass
    return imports

def detect_unused_apps(settings_file: Path, start_dir: Path, mappings: dict) -> List[str]:
    """Detect apps in INSTALLED_APPS that are not imported anywhere in the project"""
    # Read INSTALLED_APPS
    with open(settings_file, 'r') as f:
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
        app_root = app.split('.')[0]
        
        # Also check if it's a mapped package (e.g., rest_framework -> djangorestframework)
        package_name = reverse_mappings.get(app, app)
        package_root = package_name.split('.')[0].replace('-', '_')
        
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
        with open(req_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Skip git URLs and editable installs
                if line.startswith(('git+', 'hg+', 'svn+', 'bzr+', '-e', '--editable')):
                    continue
                
                # Remove inline comments
                if '#' in line:
                    line = line.split('#')[0].strip()
                
                # Extract package name (remove version specifiers and extras)
                # Handle: package==1.0.0, package>=1.0, package[extra]==1.0
                package_name = re.split(r'[=<>!~\[]', line)[0].strip()
                
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
        typer.secho(f"Installing packages from {req_file.name}...", fg=typer.colors.BLUE)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            typer.secho(f"Successfully installed packages from {req_file.name}", fg=typer.colors.GREEN)
            return True
        else:
            typer.secho(f"Error installing packages: {result.stderr}", fg=typer.colors.RED)
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
            
            django_packages.append({
                'package_name': package,
                'app_name': app_name,
                'is_django': True,
                'is_mapped': app_name is not None
            })
    
    return django_packages

# ============================================================================
# INSTALLED_APPS Management Functions
# ============================================================================

def append_to_installed_apps(file_path: Path, new_app: str):
    """Add a single app to INSTALLED_APPS"""
    with open(file_path, 'r') as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho("The specified INSTALLED_APPS list was not found in the file.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    start, apps_list, end = match.groups()
    
    if f"'{new_app}'" in apps_list:
        typer.secho(f"The app '{new_app}' already exists and will not be added to INSTALLED_APPS.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    new_apps_list = apps_list + f"\n\t'{new_app}',"
    new_content = content[:match.start(2)] + new_apps_list + content[match.end(2):]

    with open(file_path, 'w') as file:
        file.write(new_content)

    typer.secho(f"App '{new_app}' has been added to INSTALLED_APPS.", fg=typer.colors.GREEN)

def append_to_installed_apps_multi(file_path: Path, new_app: str):
    """Add an app to INSTALLED_APPS (multi-app version that doesn't exit on error)"""
    with open(file_path, 'r') as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho("The specified INSTALLED_APPS list was not found in the file.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    start, apps_list, end = match.groups()
    
    if f"'{new_app}'" not in apps_list:
        new_apps_list = apps_list + f"\n\t'{new_app}',"
        new_content = content[:match.start(2)] + new_apps_list + content[match.end(2):]

        with open(file_path, 'w') as file:
            file.write(new_content)

        typer.secho(f"App '{new_app}' has been added to INSTALLED_APPS.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"App '{new_app}' has already been added to INSTALLED_APPS. Skipping!", fg=typer.colors.BRIGHT_BLUE)

def remove_from_installed_apps(file_path: Path, app_to_remove: str):
    """Remove a single app from INSTALLED_APPS in settings.py"""
    with open(file_path, 'r') as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho("The specified INSTALLED_APPS list was not found in the file.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    start, apps_list, end = match.groups()
    
    # Check if app exists in the list (handle both single and double quotes)
    if f"'{app_to_remove}'" not in apps_list and f'"{app_to_remove}"' not in apps_list:
        typer.secho(f"The app '{app_to_remove}' was not found in INSTALLED_APPS.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    # Remove the app entry (handles both quote styles and trailing comma)
    app_pattern = re.compile(
        rf"\s*['\"]({re.escape(app_to_remove)})['\"],?\s*\n?",
        re.MULTILINE
    )
    
    new_apps_list = app_pattern.sub('', apps_list)
    new_content = content[:match.start(2)] + new_apps_list + content[match.end(2):]

    with open(file_path, 'w') as file:
        file.write(new_content)

    typer.secho(f"App '{app_to_remove}' has been removed from INSTALLED_APPS.", fg=typer.colors.GREEN)

def remove_from_installed_apps_multi(file_path: Path, app_to_remove: str):
    """Remove an app from INSTALLED_APPS (multi-app version that doesn't exit on error)"""
    with open(file_path, 'r') as file:
        content = file.read()

    pattern = re.compile(r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\s*])", re.DOTALL)
    match = pattern.search(content)

    if not match:
        typer.secho("The specified INSTALLED_APPS list was not found in the file.", fg=typer.colors.RED)
        return

    start, apps_list, end = match.groups()
    
    # Check if app exists in the list
    if f"'{app_to_remove}'" not in apps_list and f'"{app_to_remove}"' not in apps_list:
        typer.secho(f"App '{app_to_remove}' was not found in INSTALLED_APPS. Skipping!", fg=typer.colors.BRIGHT_BLUE)
        return

    # Remove the app entry
    app_pattern = re.compile(
        rf"\s*['\"]({re.escape(app_to_remove)})['\"],?\s*\n?",
        re.MULTILINE
    )
    
    new_apps_list = app_pattern.sub('', apps_list)
    new_content = content[:match.start(2)] + new_apps_list + content[match.end(2):]

    with open(file_path, 'w') as file:
        file.write(new_content)

    typer.secho(f"App '{app_to_remove}' has been removed from INSTALLED_APPS.", fg=typer.colors.GREEN)

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
            inquirer.Confirm('add_to_req',
                message=f"Add '{package_name}=={pkg_version}' to requirements.txt?",
                default=True
            )
        ]
        answers = inquirer.prompt(questions)
        
        if answers and answers['add_to_req']:
            add_to_requirements(req_file_path, package_name, pkg_version)
            typer.secho(f"Added '{package_name}=={pkg_version}' to requirements.txt", fg=typer.colors.GREEN)
    else:
        # requirements.txt doesn't exist
        questions = [
            inquirer.List('req_action',
                message="requirements.txt not found. What would you like to do?",
                choices=[
                    'Create requirements.txt with this package',
                    'Create requirements.txt with all project packages',
                    'None/Skip'
                ]
            )
        ]
        answers = inquirer.prompt(questions)
        
        if not answers:
            return
        
        if answers['req_action'] == 'None/Skip':
            return
        elif answers['req_action'] == 'Create requirements.txt with this package':
            req_file_path = start_dir / "requirements.txt"
            add_to_requirements(req_file_path, package_name, pkg_version)
            typer.secho(f"Created requirements.txt with '{package_name}=={pkg_version}'", fg=typer.colors.GREEN)
        
        elif answers['req_action'] == 'Create requirements.txt with all project packages':
            req_file_path = start_dir / "requirements.txt"
            settings_file_path = find_settings_file(start_dir)
            if settings_file_path:
                mappings = load_package_mappings()
                packages = generate_requirements_from_project(start_dir, settings_file_path, mappings)
                
                with open(req_file_path, 'w') as f:
                    f.write('\n'.join(packages) + '\n')
                
                typer.secho(f"Created requirements.txt with {len(packages)} packages", fg=typer.colors.GREEN)

def handle_requirements_after_remove(start_dir: Path, app_name: str):
    """Handle requirements.txt management after removing an app"""
    req_file_path = find_requirements_file(start_dir)
    
    if not req_file_path:
        return
    
    # Check if package is in requirements.txt
    with open(req_file_path, 'r') as f:
        content = f.read()
    
    # Get package name from reverse mapping
    mappings = load_package_mappings()
    reverse_mappings = {v: k for k, v in mappings.items() if v is not None}
    package_name = reverse_mappings.get(app_name, app_name)
    
    if package_name in content:
        questions = [
            inquirer.Confirm('remove_from_req',
                message=f"Remove '{package_name}' from requirements.txt?",
                default=True
            )
        ]
        answers = inquirer.prompt(questions)
        
        if answers and answers['remove_from_req']:
            remove_from_requirements(req_file_path, package_name)
            typer.secho(f"Removed '{package_name}' from requirements.txt", fg=typer.colors.GREEN)

# ============================================================================
# CLI Commands
# ============================================================================

@app.command()
def add_app(
    new_app: str = typer.Argument(..., help="The new app to add to INSTALLED_APPS (supports version specifiers like package==1.0.0)"),
    start_dir: Path = typer.Option(None, "--start-dir", "-d", help="The directory to search for settings.py. Defaults to current directory."),
    version_flag: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Show version and exit")
):
    """
    Add a new app to the INSTALLED_APPS list in settings.py if it's related to Django or already installed.
    Uses smart package mapping to automatically determine the correct app name.
    
    Supports version specifiers:
        django-include-apps add-app djangorestframework==3.14.0
        django-include-apps add-app django-filter>=2.0
    """
    start_dir = start_dir or Path.cwd()
    
    # Parse package specification to extract name and version
    package_name, version_spec = parse_package_spec(new_app)
    package_to_install = new_app  # Use full spec for installation
    
    typer.secho(f"Package: {package_name}", fg=typer.colors.CYAN)
    if version_spec:
        typer.secho(f"Version: {version_spec}", fg=typer.colors.CYAN)
    
    # Check if package is installed
    if not is_package_installed(package_name):
        install_confirm = inquirer.prompt([
            inquirer.Confirm("confirm", message=f"Package '{package_name}' is not installed. Do you want to install it?", default=True)
        ])
        if install_confirm and install_confirm["confirm"]:
            typer.secho(f"Installing package '{package_to_install}'...", fg=typer.colors.BLUE)
            install_package(package_to_install)
            typer.secho(f"Package '{package_name}' has been installed.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"Skipping installation of '{package_name}'.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
    else:
        typer.secho(f"Package '{package_name}' is already installed.", fg=typer.colors.BRIGHT_YELLOW)
        
    # Check if Django-related (use clean package name)
    if not is_django_related(package_name):
        typer.secho(f"The package '{package_name}' is not related to Django and will not be added to INSTALLED_APPS.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    typer.secho(f"Searching for settings.py in {start_dir}", fg=typer.colors.BLUE)
    
    # Load package mappings (use clean package name)
    mappings = load_package_mappings()
    mapped_app_name = get_app_name_from_mapping(package_name, mappings)
    
    # Ask user for app name choice
    confirmation = [
        inquirer.List(
            "choice",
            message="Do you want to use the same name or a different one?",
            choices=['Use same', 'Use different', 'None/Skip'],
        ),
    ]
    answers = inquirer.prompt(confirmation)
    
    if not answers or answers["choice"] == "None/Skip":
        typer.secho("Skipping app addition.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    
    app_name_to_add = None
    save_mapping = False
    
    if answers["choice"] == "Use different":
        # User wants custom name
        packagename_question = [
            inquirer.Text('package_name', message="Enter the app name as mentioned in the source documentation")
        ]
        second_answers = inquirer.prompt(packagename_question)
        if second_answers and second_answers["package_name"]:
            app_name_to_add = second_answers["package_name"]
            
            # Ask if they want to save this mapping
            if mapped_app_name is None:  # Only ask if not already mapped
                save_q = [inquirer.Confirm('save', message=f"Save this mapping ({package_name} → {app_name_to_add}) for future use?", default=True)]
                save_ans = inquirer.prompt(save_q)
                if save_ans and save_ans['save']:
                    save_mapping = True
    else:
        # Use same - check mapping first
        if mapped_app_name:
            app_name_to_add = mapped_app_name
            typer.secho(f"Using mapped app name '{mapped_app_name}' for package '{package_name}'.", fg=typer.colors.BRIGHT_CYAN)
        else:
            # Not in mapping - prompt user
            typer.secho(f"Package '{package_name}' not found in mappings.", fg=typer.colors.YELLOW)
            prompt_q = [
                inquirer.Text('app_name', message=f"Enter app name to add to INSTALLED_APPS:")
            ]
            prompt_ans = inquirer.prompt(prompt_q)
            if prompt_ans and prompt_ans["app_name"]:
                app_name_to_add = prompt_ans["app_name"]
                
                # Ask if they want to save this mapping
                save_q = [inquirer.Confirm('save', message=f"Save this mapping ({package_name} → {app_name_to_add}) for future use?", default=True)]
                save_ans = inquirer.prompt(save_q)
                if save_ans and save_ans['save']:
                    save_mapping = True
    
    if not app_name_to_add:
        typer.secho("No app name provided. Exiting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Find settings.py
    settings_file_path = find_settings_file(start_dir)
    if not settings_file_path:
        typer.secho("settings.py not found in the specified directory or its subdirectories.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Add to INSTALLED_APPS
    append_to_installed_apps(settings_file_path, app_name_to_add)
    
    # Save mapping if requested (use clean package name)
    if save_mapping:
        update_package_mappings(package_name, app_name_to_add)
    
    # Handle requirements.txt (use full package spec with version)
    handle_requirements_after_add(start_dir, package_to_install)

@app.command()
def add_apps(
    package_names: List[str],
    start_dir: Path = typer.Option(None, "--start-dir", "-d", help="The directory to search for settings.py. Defaults to current directory."),
    version_flag: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Show version and exit")
):
    """
    Add multiple apps to INSTALLED_APPS in settings.py.
    Supports version specifiers for each package.
    Uses smart package mapping to automatically determine the correct app names.
    """
    start_dir = start_dir or Path.cwd()
    settings_file_path = find_settings_file(start_dir)
    
    if not settings_file_path:
        typer.secho("settings.py not found in the specified directory or its subdirectories.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Load mappings once
    mappings = load_package_mappings()
    
    for package_spec in package_names:
        # Parse package specification
        package_name, version_spec = parse_package_spec(package_spec)
        package_to_install = package_spec  # Use full spec for installation
        
        typer.secho(f"\n{'='*60}", fg=typer.colors.CYAN)
        typer.secho(f"Processing: {package_name}", fg=typer.colors.CYAN)
        if version_spec:
            typer.secho(f"Version: {version_spec}", fg=typer.colors.CYAN)
        typer.secho(f"{'='*60}", fg=typer.colors.CYAN)
        
        # Check if installed (use clean package name)
        installed = is_package_installed(package_name)
        if not installed:
            install = [inquirer.Confirm("confirm", message=f"{package_name} is not installed. Do you want to install it?")]
            install_confirm = inquirer.prompt(install)
            if install_confirm and install_confirm["confirm"]:
                typer.secho(f"Installing package '{package_to_install}'...", fg=typer.colors.BLUE)
                install_package(package_to_install)
                typer.secho(f"Package '{package_name}' has been installed.", fg=typer.colors.GREEN)
            else:
                typer.secho(f"Skipping installation of '{package_name}'.", fg=typer.colors.YELLOW)
                continue
        else:
            typer.secho(f"Package '{package_name}' is already installed.", fg=typer.colors.BRIGHT_YELLOW)
            
        # Check if Django-related (use clean package name)
        if not is_django_related(package_name):
            typer.secho(f"The package '{package_name}' is not related to Django. Skipping!", fg=typer.colors.RED)
            continue
        
        # Get mapped app name (use clean package name)
        mapped_app_name = get_app_name_from_mapping(package_name, mappings)
        
        # Ask user for choice
        confirmation = [
            inquirer.List(
                "choice",
                message="Do you want to use the same name or a different one?",
                choices=['Use same', 'Use different', 'None/Skip'],
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
                inquirer.Text('package_name', message="Enter the app name as mentioned in the source documentation")
            ]
            second_answers = inquirer.prompt(packagename_question)
            if second_answers and second_answers["package_name"]:
                app_name_to_add = second_answers["package_name"]
                
                if mapped_app_name is None:
                    save_q = [inquirer.Confirm('save', message=f"Save this mapping ({package_name} → {app_name_to_add}) for future use?", default=True)]
                    save_ans = inquirer.prompt(save_q)
                    if save_ans and save_ans['save']:
                        save_mapping = True
        else:
            if mapped_app_name:
                app_name_to_add = mapped_app_name
                typer.secho(f"Using mapped app name '{mapped_app_name}' for package '{package_name}'.", fg=typer.colors.BRIGHT_CYAN)
            else:
                typer.secho(f"Package '{package_name}' not found in mappings.", fg=typer.colors.YELLOW)
                prompt_q = [
                    inquirer.Text('app_name', message=f"Enter app name to add to INSTALLED_APPS:")
                ]
                prompt_ans = inquirer.prompt(prompt_q)
                if prompt_ans and prompt_ans["app_name"]:
                    app_name_to_add = prompt_ans["app_name"]
                    
                    save_q = [inquirer.Confirm('save', message=f"Save this mapping ({package_name} → {app_name_to_add}) for future use?", default=True)]
                    save_ans = inquirer.prompt(save_q)
                    if save_ans and save_ans['save']:
                        save_mapping = True
        
        if not app_name_to_add:
            typer.secho(f"No app name provided for '{package_name}'. Skipping!", fg=typer.colors.YELLOW)
            continue
        
        # Add to INSTALLED_APPS
        append_to_installed_apps_multi(settings_file_path, app_name_to_add)
        
        # Save mapping if requested
        if save_mapping:
            update_package_mappings(package_name, app_name_to_add)
        
        # Handle requirements.txt
        handle_requirements_after_add(start_dir, package_name)

@app.command()
def remove_app(app_name: Optional[str] = typer.Argument(None, help="The app to remove from INSTALLED_APPS"),
               start_dir: Path = typer.Option(None, "--start-dir", "-d", help="The directory to search for settings.py. Defaults to current directory.")):
    """
    Remove an app from the INSTALLED_APPS list in settings.py.
    If no app is specified, scans project and suggests unused apps for removal.
    Default Django apps (starting with 'django.') are protected from removal.
    """
    start_dir = start_dir or Path.cwd()
    settings_file_path = find_settings_file(start_dir)

    if not settings_file_path:
        typer.secho("settings.py not found in the specified directory or its subdirectories.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # If no app specified, detect unused apps
    if app_name is None:
        typer.secho("Scanning project for unused apps...", fg=typer.colors.BLUE)
        mappings = load_package_mappings()
        unused_apps = detect_unused_apps(settings_file_path, start_dir, mappings)
        
        if not unused_apps:
            typer.secho("No unused apps detected!", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        
        typer.secho(f"\nFound {len(unused_apps)} unused app(s):", fg=typer.colors.YELLOW)
        for app in unused_apps:
            typer.secho(f"  • {app}", fg=typer.colors.YELLOW)
        
        # Ask user to select apps to remove
        questions = [
            inquirer.Checkbox('apps_to_remove',
                message="Select apps to remove (use space to select, enter to confirm)",
                choices=unused_apps,
            ),
        ]
        answers = inquirer.prompt(questions)
        
        if not answers or not answers['apps_to_remove']:
            typer.secho("No apps selected for removal.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
        
        # Remove selected apps
        for app in answers['apps_to_remove']:
            remove_from_installed_apps_multi(settings_file_path, app)
            handle_requirements_after_remove(start_dir, app)
        
        return

    # Check if it's a default Django app
    if is_default_django_app(app_name):
        typer.secho(f"Cannot remove default Django app '{app_name}'. Default Django apps are protected.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Confirm with user before removing
    confirmation = [
        inquirer.Confirm("confirm", message=f"Are you sure you want to remove '{app_name}' from INSTALLED_APPS?")
    ]
    confirm_answer = inquirer.prompt(confirmation)
    
    if not confirm_answer or not confirm_answer["confirm"]:
        typer.secho(f"Removal of '{app_name}' cancelled.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    typer.secho(f"Searching for settings.py in {start_dir}", fg=typer.colors.BLUE)
    remove_from_installed_apps(settings_file_path, app_name)
    
    # Handle requirements.txt
    handle_requirements_after_remove(start_dir, app_name)

@app.command()
def remove_apps(app_names: Optional[List[str]] = typer.Argument(None, help="Apps to remove from INSTALLED_APPS"),
                start_dir: Path = typer.Option(None, "--start-dir", "-d", help="The directory to search for settings.py. Defaults to current directory.")):
    """
    Remove one or more apps from INSTALLED_APPS in settings.py.
    If no apps specified, scans project and suggests unused apps for removal.
    Default Django apps (starting with 'django.') are protected from removal.
    """
    start_dir = start_dir or Path.cwd()
    settings_file_path = find_settings_file(start_dir)
    
    if not settings_file_path:
        typer.secho("settings.py not found in the specified directory or its subdirectories.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # If no apps specified, detect unused apps (same as remove_app)
    if not app_names:
        typer.secho("Scanning project for unused apps...", fg=typer.colors.BLUE)
        mappings = load_package_mappings()
        unused_apps = detect_unused_apps(settings_file_path, start_dir, mappings)
        
        if not unused_apps:
            typer.secho("No unused apps detected!", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        
        typer.secho(f"\nFound {len(unused_apps)} unused app(s):", fg=typer.colors.YELLOW)
        for app in unused_apps:
            typer.secho(f"  • {app}", fg=typer.colors.YELLOW)
        
        # Ask user to select apps to remove
        questions = [
            inquirer.Checkbox('apps_to_remove',
                message="Select apps to remove (use space to select, enter to confirm)",
                choices=unused_apps,
            ),
        ]
        answers = inquirer.prompt(questions)
        
        if not answers or not answers['apps_to_remove']:
            typer.secho("No apps selected for removal.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
        
        # Remove selected apps
        for app in answers['apps_to_remove']:
            remove_from_installed_apps_multi(settings_file_path, app)
            handle_requirements_after_remove(start_dir, app)
        
        return

    # Filter out protected Django apps
    apps_to_remove = []
    protected_apps = []
    
    for app_name in app_names:
        if is_default_django_app(app_name):
            protected_apps.append(app_name)
        else:
            apps_to_remove.append(app_name)
    
    # Warn about protected apps
    if protected_apps:
        typer.secho(f"\nThe following default Django apps are protected and will NOT be removed:", fg=typer.colors.YELLOW)
        for app in protected_apps:
            typer.secho(f"  • {app}", fg=typer.colors.YELLOW)
    
    # Check if there are any apps to remove
    if not apps_to_remove:
        typer.secho("\nNo apps to remove after filtering protected Django apps.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Show apps that will be removed
    typer.secho(f"\nThe following apps will be removed:", fg=typer.colors.CYAN)
    for app in apps_to_remove:
        typer.secho(f"  • {app}", fg=typer.colors.CYAN)
    
    # Batch confirmation
    confirmation = [
        inquirer.Confirm("confirm", message=f"\nAre you sure you want to remove these {len(apps_to_remove)} apps from INSTALLED_APPS?")
    ]
    confirm_answer = inquirer.prompt(confirmation)
    
    if not confirm_answer or not confirm_answer["confirm"]:
        typer.secho("Removal cancelled.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    
    typer.secho(f"\nSearching for settings.py in {start_dir}", fg=typer.colors.BLUE)
    
    # Remove each app
    for app_name in apps_to_remove:
        remove_from_installed_apps_multi(settings_file_path, app_name)
        handle_requirements_after_remove(start_dir, app_name)

@app.command()
def install_requirements(
    requirements_file: Path = typer.Option(..., "--requirements", "-r", help="Path to requirements.txt file"),
    start_dir: Path = typer.Option(None, "--start-dir", "-d", help="Directory to search for settings.py. Defaults to current directory.")
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
        typer.secho(f"Error: Requirements file '{requirements_file}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Find settings.py
    settings_file_path = find_settings_file(start_dir)
    if not settings_file_path:
        typer.secho("settings.py not found in the specified directory or its subdirectories.", fg=typer.colors.RED)
        typer.secho("Packages will be installed but not added to INSTALLED_APPS.", fg=typer.colors.YELLOW)
        
        # Ask if user wants to continue
        questions = [
            inquirer.Confirm('continue', message="Continue with installation only?", default=True)
        ]
        answers = inquirer.prompt(questions)
        
        if not answers or not answers['continue']:
            raise typer.Exit(code=0)
        
        # Install packages only
        install_from_requirements_file(requirements_file)
        raise typer.Exit(code=0)
    
    # Parse requirements file
    packages = parse_requirements_file(requirements_file)
    
    if not packages:
        typer.secho("No packages found in requirements file.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    
    typer.secho(f"Found {len(packages)} package(s) in {requirements_file.name}", fg=typer.colors.CYAN)
    
    # Install packages
    if not install_from_requirements_file(requirements_file):
        typer.secho("Installation failed. Exiting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Load package mappings
    mappings = load_package_mappings()
    
    # Detect Django packages
    django_packages = detect_django_packages_from_list(packages, mappings)
    
    if not django_packages:
        typer.secho("\\nNo Django-related packages detected.", fg=typer.colors.YELLOW)
        typer.secho("All packages have been installed successfully.", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)
    
    # Show detected Django packages
    typer.secho(f"\\nFound {len(django_packages)} Django package(s):", fg=typer.colors.GREEN)
    for pkg in django_packages:
        if pkg['is_mapped']:
            typer.secho(f"  • {pkg['package_name']} → {pkg['app_name']}", fg=typer.colors.CYAN)
        else:
            typer.secho(f"  • {pkg['package_name']} (not mapped)", fg=typer.colors.YELLOW)
    
    # Create choices for checkbox selection
    choices = []
    for pkg in django_packages:
        if pkg['is_mapped']:
            label = f"{pkg['package_name']} ({pkg['app_name']})"
        else:
            label = f"{pkg['package_name']} (unmapped - will prompt for app name)"
        choices.append(label)
    
    # Prompt user to select packages
    questions = [
        inquirer.Checkbox(
            'selected_packages',
            message="Select packages to add to INSTALLED_APPS (use space to select, enter to confirm)",
            choices=choices,
            default=choices  # Pre-select all by default
        ),
    ]
    answers = inquirer.prompt(questions)
    
    if not answers or not answers['selected_packages']:
        typer.secho("\\nNo packages selected. Installation complete.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    
    # Process selected packages
    typer.secho("\\nAdding selected packages to INSTALLED_APPS...", fg=typer.colors.BLUE)
    
    added_count = 0
    for i, pkg in enumerate(django_packages):
        if choices[i] in answers['selected_packages']:
            app_name = pkg['app_name']
            
            # If not mapped, prompt for app name
            if not pkg['is_mapped']:
                prompt_q = [
                    inquirer.Text(
                        'app_name',
                        message=f"Enter app name for '{pkg['package_name']}' to add to INSTALLED_APPS"
                    )
                ]
                prompt_ans = inquirer.prompt(prompt_q)
                
                if prompt_ans and prompt_ans['app_name']:
                    app_name = prompt_ans['app_name']
                    
                    # Ask if they want to save this mapping
                    save_q = [
                        inquirer.Confirm(
                            'save',
                            message=f"Save this mapping ({pkg['package_name']} → {app_name}) for future use?",
                            default=True
                        )
                    ]
                    save_ans = inquirer.prompt(save_q)
                    if save_ans and save_ans['save']:
                        update_package_mappings(pkg['package_name'], app_name)
                else:
                    typer.secho(f"Skipping '{pkg['package_name']}' (no app name provided)", fg=typer.colors.YELLOW)
                    continue
            
            # Add to INSTALLED_APPS
            try:
                append_to_installed_apps_multi(settings_file_path, app_name)
                added_count += 1
            except Exception as e:
                typer.secho(f"Error adding '{app_name}': {e}", fg=typer.colors.RED)
    
    # Summary
    typer.secho(f"\\nDone! {added_count} package(s) added to INSTALLED_APPS.", fg=typer.colors.GREEN)

@app.command()
def view_mappings(
    filter_pattern: str = typer.Option(None, "--filter", "-f", help="Filter by package name (supports wildcards like django-*)"),
    null_only: bool = typer.Option(False, "--null-only", help="Show only dependency packages (not added to INSTALLED_APPS)"),
    apps_only: bool = typer.Option(False, "--apps-only", help="Show only packages with app names")
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
        typer.secho(f"\nPackage Mappings ({filtered_count} of {total_count} total)\n", fg=typer.colors.CYAN, bold=True)
    else:
        typer.secho(f"\nPackage Mappings ({total_count} total)\n", fg=typer.colors.CYAN, bold=True)
    
    # Calculate column widths
    max_pkg_len = max(len(pkg) for pkg in filtered_mappings.keys())
    max_app_len = max(len(str(app) if app else "(not added to INSTALLED_APPS)") for app in filtered_mappings.values())
    
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
        app_display = app if app else typer.style("(not added to INSTALLED_APPS)", fg=typer.colors.YELLOW)
        pkg_display = typer.style(pkg, fg=typer.colors.CYAN)
        
        if app:
            app_display = typer.style(app, fg=typer.colors.GREEN)
        
        typer.echo(f"{pkg_display:<{pkg_width}}  {app_display}")
    
    typer.echo()  # Empty line at end

# Create mapping subcommand group
mapping_app = typer.Typer(help="Manage package mappings")
app.add_typer(mapping_app, name="mapping")

@mapping_app.command("list")
def mapping_list(
    filter_pattern: str = typer.Option(None, "--filter", "-f", help="Filter by package name"),
    null_only: bool = typer.Option(False, "--null-only", help="Show only dependency packages"),
    apps_only: bool = typer.Option(False, "--apps-only", help="Show only packages with app names")
):
    """List all package mappings (alias for view-mappings)"""
    view_mappings(filter_pattern, null_only, apps_only)

@mapping_app.command("add")
def mapping_add(
    package_name: str = typer.Argument(..., help="Package name (e.g., django-cors-headers)"),
    app_name: str = typer.Argument(None, help="App name for INSTALLED_APPS (e.g., corsheaders)"),
    null: bool = typer.Option(False, "--null", help="Mark as dependency-only package (not added to INSTALLED_APPS)")
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
        typer.secho("Error: app_name is required unless --null is specified", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    mapping_file = Path(__file__).parent / "package_mappings.json"
    mappings = load_package_mappings()
    
    # Check if mapping already exists
    if package_name in mappings:
        current_value = mappings[package_name]
        typer.secho(f"Mapping already exists: {package_name} → {current_value}", fg=typer.colors.YELLOW)
        typer.secho("Use 'mapping update' to modify existing mappings.", fg=typer.colors.CYAN)
        raise typer.Exit(code=1)
    
    # Add new mapping
    mappings[package_name] = app_name
    sorted_mappings = dict(sorted(mappings.items()))
    
    try:
        with open(mapping_file, 'w') as f:
            json.dump(sorted_mappings, f, indent=4)
        
        if app_name:
            typer.secho(f"✓ Added mapping: {package_name} → {app_name}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"✓ Added mapping: {package_name} → (not added to INSTALLED_APPS)", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

@mapping_app.command("update")
def mapping_update(
    package_name: str = typer.Argument(..., help="Package name to update"),
    app_name: str = typer.Argument(None, help="New app name for INSTALLED_APPS"),
    null: bool = typer.Option(False, "--null", help="Mark as dependency-only package")
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
        typer.secho("Error: app_name is required unless --null is specified", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    mapping_file = Path(__file__).parent / "package_mappings.json"
    mappings = load_package_mappings()
    
    # Check if mapping exists
    if package_name not in mappings:
        typer.secho(f"Mapping not found: {package_name}", fg=typer.colors.RED)
        typer.secho("Use 'mapping add' to create new mappings.", fg=typer.colors.CYAN)
        raise typer.Exit(code=1)
    
    current_value = mappings[package_name]
    
    # Update mapping
    mappings[package_name] = app_name
    sorted_mappings = dict(sorted(mappings.items()))
    
    try:
        with open(mapping_file, 'w') as f:
            json.dump(sorted_mappings, f, indent=4)
        
        typer.secho(f"✓ Updated mapping: {package_name}", fg=typer.colors.GREEN)
        typer.secho(f"  Old: {current_value}", fg=typer.colors.YELLOW)
        typer.secho(f"  New: {app_name if app_name else '(not added to INSTALLED_APPS)'}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

@mapping_app.command("remove")
def mapping_remove(
    package_name: str = typer.Argument(..., help="Package name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
):
    """
    Remove a package mapping.
    
    Example:
        django-include-apps mapping remove my-custom-package
    """
    mapping_file = Path(__file__).parent / "package_mappings.json"
    mappings = load_package_mappings()
    
    # Check if mapping exists
    if package_name not in mappings:
        typer.secho(f"Mapping not found: {package_name}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    current_value = mappings[package_name]
    
    # Ask for confirmation unless --force
    if not force:
        typer.secho(f"\nCurrent mapping: {package_name} → {current_value}", fg=typer.colors.YELLOW)
        questions = [
            inquirer.Confirm(
                'remove',
                message=f"Remove this mapping?",
                default=False
            )
        ]
        answers = inquirer.prompt(questions)
        
        if not answers or not answers['remove']:
            typer.secho("Cancelled.", fg=typer.colors.CYAN)
            return
    
    # Remove mapping
    del mappings[package_name]
    sorted_mappings = dict(sorted(mappings.items()))
    
    try:
        with open(mapping_file, 'w') as f:
            json.dump(sorted_mappings, f, indent=4)
        
        typer.secho(f"✓ Removed mapping: {package_name}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error saving mapping: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

@app.command()
def completion(
    shell: str = typer.Argument(None, help="Shell type: bash, zsh, or fish"),
    install: bool = typer.Option(False, "--install", help="Install completion for the specified shell")
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
        typer.echo("  Or manually: django-include-apps completion fish > ~/.config/fish/completions/django-include-apps.fish\n")
        return
    
    shell = shell.lower()
    
    if shell not in ['bash', 'zsh', 'fish']:
        typer.secho(f"Unsupported shell: {shell}. Supported shells: bash, zsh, fish", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Generate completion script using typer's built-in support
    completion_script = typer.completion.get_completion_script(
        prog_name="django-include-apps",
        complete_var="_DJANGO_INCLUDE_APPS_COMPLETE",
        shell=shell
    )
    
    if install:
        import platform
        home = Path.home()
        
        if shell == 'bash':
            rc_file = home / '.bashrc'
            marker = "# django-include-apps completion"
            
            if rc_file.exists():
                content = rc_file.read_text()
                if marker in content:
                    typer.secho("Completion already installed in ~/.bashrc", fg=typer.colors.YELLOW)
                    return
            
            with open(rc_file, 'a') as f:
                f.write(f"\n{marker}\n")
                f.write(completion_script)
                f.write("\n")
            
            typer.secho(f"✓ Completion installed to {rc_file}", fg=typer.colors.GREEN)
            typer.secho("Run 'source ~/.bashrc' or restart your terminal", fg=typer.colors.CYAN)
            
        elif shell == 'zsh':
            rc_file = home / '.zshrc'
            marker = "# django-include-apps completion"
            
            if rc_file.exists():
                content = rc_file.read_text()
                if marker in content:
                    typer.secho("Completion already installed in ~/.zshrc", fg=typer.colors.YELLOW)
                    return
            
            with open(rc_file, 'a') as f:
                f.write(f"\n{marker}\n")
                f.write(completion_script)
                f.write("\n")
            
            typer.secho(f"✓ Completion installed to {rc_file}", fg=typer.colors.GREEN)
            typer.secho("Run 'source ~/.zshrc' or restart your terminal", fg=typer.colors.CYAN)
            
        elif shell == 'fish':
            fish_dir = home / '.config' / 'fish' / 'completions'
            fish_dir.mkdir(parents=True, exist_ok=True)
            fish_file = fish_dir / 'django-include-apps.fish'
            
            with open(fish_file, 'w') as f:
                f.write(completion_script)
            
            typer.secho(f"✓ Completion installed to {fish_file}", fg=typer.colors.GREEN)
            typer.secho("Restart your terminal or run 'source ~/.config/fish/config.fish'", fg=typer.colors.CYAN)
    else:
        # Just print the completion script
        typer.echo(completion_script)

if __name__ == "__main__":
    app()
