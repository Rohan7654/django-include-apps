# django-include-apps

[![PyPI version](https://badge.fury.io/py/django-include-apps.svg)](https://badge.fury.io/py/django-include-apps)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-include-apps.svg)](https://pypi.org/project/django-include-apps/)
[![Django Versions](https://img.shields.io/badge/django-2.2%20%7C%203.0%20%7C%203.1%20%7C%203.2%20%7C%204.0%20%7C%204.1%20%7C%204.2%20%7C%205.0-blue.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/django-include-apps)](https://pepy.tech/project/django-include-apps)
[![Downloads/Month](https://static.pepy.tech/badge/django-include-apps/month)](https://pepy.tech/project/django-include-apps)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/Rohan7654/django-include-apps/graphs/commit-activity)

A powerful CLI tool to intelligently manage Django apps in your `INSTALLED_APPS` setting. Install, add, remove, and maintain Django packages with smart package mapping and automatic `requirements.txt` management!

## Features

### Core Features
- **Smart Package Mapping**: 75+ pre-configured Django package mappings (e.g., `djangorestframework` → `rest_framework`)
- **Version Specifier Support**: Install specific versions (e.g., `djangorestframework==3.14.0`, `django-filter>=2.0`)
- **Automatic Installation**: Prompts to install packages that aren't already installed
- **Django Related Package Detection**: Automatically verifies if packages are Django-related via PyPI
- **requirements.txt Management**: Automatically add/update/remove packages from requirements.txt
- **Unused App Detection**: Scans your project to find and remove unused apps
- **Protected Defaults**: Prevents removal of core default apps in INSTALLED_APPS (e.g., `django.contrib.*`)
- **Dynamic Mapping Updates**: Save custom package mappings for future use
- **Interactive Prompts**: User-friendly confirmations with None/Skip option to cancel operations
- **Flexible Control**: Skip any operation at any time with the None/Skip option
- **Shell Completion**: Auto-completion for bash, zsh, and fish shells

### Package Operations
- Add single or multiple apps
- Remove single or multiple apps  
- Detect and suggest unused apps for removal
- Batch operations with smart handling

## Installation

```bash
pip install django-include-apps
```

## Quick Start

### Add a Django Package
```bash
# Add djangorestframework (automatically maps to 'rest_framework')
django-include-apps add-app djangorestframework
```

**Sample Output:**
```
Installing package 'djangorestframework'...
Package 'djangorestframework' has been installed.
? Do you want to use the same name or a different one? Use same
Using 'rest_framework' package name as the App name to be added in INSTALLED_APPS.
App 'rest_framework' has been added to INSTALLED_APPS.
? Add 'djangorestframework==3.14.0' to requirements.txt? Yes
Added 'djangorestframework==3.14.0' to requirements.txt
```

### Add Multiple Packages
```bash
django-include-apps add-apps djangorestframework django-cors-headers django-filter
```

**Sample Output:**
```
Installing package 'djangorestframework'...
Package 'djangorestframework' has been installed.
App 'rest_framework' has been added to INSTALLED_APPS.

Installing package 'django-cors-headers'...
Package 'django-cors-headers' has been installed.
App 'corsheaders' has been added to INSTALLED_APPS.

Installing package 'django-filter'...
Package 'django-filter' has been installed.
App 'django_filters' has been added to INSTALLED_APPS.

? Add all packages to requirements.txt? Yes
Added 3 packages to requirements.txt
```

### Remove an App
```bash
django-include-apps remove-app rest_framework
```

**Sample Output:**
```
? Are you sure you want to remove 'rest_framework' from INSTALLED_APPS? Yes
App 'rest_framework' has been removed from INSTALLED_APPS.
? Remove 'djangorestframework' from requirements.txt? Yes
Removed 'djangorestframework' from requirements.txt
```

### Detect Unused Apps
```bash
# Run without parameters to scan for unused apps
django-include-apps remove-app
```

**Sample Output:**
```
Scanning project for unused apps...

Found 3 unused app(s):
  • rest_framework
  • corsheaders
  • debug_toolbar

? Select apps to remove (use space to select, enter to confirm)
  ◉ rest_framework
  ◯ corsheaders
  ◉ debug_toolbar

App 'rest_framework' has been removed from INSTALLED_APPS.
App 'debug_toolbar' has been removed from INSTALLED_APPS.

? Remove selected packages from requirements.txt? Yes
Removed 2 packages from requirements.txt
```

### Remove Multiple Apps
```bash
django-include-apps remove-apps rest_framework corsheaders django-filter
```

**Sample Output:**
```
The following apps will be removed:
  • rest_framework
  • corsheaders
  • django_filters

? Are you sure you want to remove these 3 apps from INSTALLED_APPS? Yes

App 'rest_framework' has been removed from INSTALLED_APPS.
App 'corsheaders' has been removed from INSTALLED_APPS.
App 'django_filters' has been removed from INSTALLED_APPS.
```

## Detailed Usage

### Custom Directory

Specify a custom Django project directory for any command using `--start-dir` or `-d`:

**Add single app:**
```bash
django-include-apps add-app djangorestframework --start-dir /path/to/django/project
# or
django-include-apps add-app djangorestframework -d /path/to/django/project
```

**Add multiple apps:**
```bash
django-include-apps add-apps rest_framework corsheaders -d /path/to/django/project
```

**Remove app:**
```bash
django-include-apps remove-app rest_framework -d /path/to/django/project
```

**Detect unused apps:**
```bash
django-include-apps remove-app -d /path/to/django/project
```

**Install from requirements.txt:**
```bash
django-include-apps install-requirements -r requirements.txt -d /path/to/django/project
```

**Common use cases:**
- Working with multiple Django projects
- CI/CD pipelines with specific project paths
- Monorepo setups with multiple Django apps
- Running from outside the project directory

### Package Mapping Behavior

#### Mapped Packages (Automatic)
For 75+ pre-configured packages, the tool automatically uses the correct app name:
```bash
django-include-apps add-app djangorestframework
# Automatically adds 'rest_framework' to INSTALLED_APPS
```

#### Unmapped Packages (Interactive)
For packages not in the mapping:
```bash
django-include-apps add-app my-custom-package
```

**Sample Output:**
```
Package 'my-custom-package' has been installed.
? Do you want to use the same name or a different one?
  > Use same
    Use different
    None/Skip
Package 'my-custom-package' not found in mappings.
Enter app name to add to INSTALLED_APPS: my_custom_app
App 'my_custom_app' has been added to INSTALLED_APPS.
? Save this mapping (my-custom-package → my_custom_app) for future use? Yes
Saved mapping: my-custom-package → my_custom_app
```

#### Custom App Name
Override the default mapping:
```bash
django-include-apps add-app djangorestframework
```

**Sample Output:**
```
? Do you want to use the same name or a different one?
    Use same
  > Use different
    None/Skip
Enter the app name as mentioned in the source documentation: custom_drf_name
App 'custom_drf_name' has been added to INSTALLED_APPS.
? Save this mapping for future use? Yes
Saved mapping: djangorestframework → custom_drf_name
```

#### Skip Operation
You can skip adding an app at any time:
```bash
django-include-apps add-app some-package
```

**Sample Output:**
```
? Do you want to use the same name or a different one?
    Use same
    Use different
  > None/Skip
Skipping app addition.
```

### requirements.txt Management

#### With Existing requirements.txt
```bash
django-include-apps add-app django-allauth
```

**Sample Output:**
```
Package 'django-allauth' has been installed.
App 'allauth' has been added to INSTALLED_APPS.
? Add 'django-allauth==0.54.0' to requirements.txt? Yes
Added 'django-allauth==0.54.0' to requirements.txt
```

#### Without requirements.txt
```bash
django-include-apps add-app django-debug-toolbar
```

**Sample Output:**
```
Package 'django-debug-toolbar' has been installed.
App 'debug_toolbar' has been added to INSTALLED_APPS.

? requirements.txt not found. What would you like to do?
  > Create requirements.txt with this package
    Create requirements.txt with all project packages
    Skip

Created requirements.txt with 'django-debug-toolbar==4.2.0'
```

#### Generate Full requirements.txt
```bash
django-include-apps add-app django-extensions
```

**Sample Output:**
```
? requirements.txt not found. What would you like to do?
    Create requirements.txt with this package
  > Create requirements.txt with all project packages
    Skip

Scanning INSTALLED_APPS...
Created requirements.txt with 12 packages
```

### Unused App Detection

The tool scans all `.py` files in your project to detect apps that are in `INSTALLED_APPS` but not imported anywhere:

```bash
django-include-apps remove-app
# or
django-include-apps remove-apps
```

**How it works:**
1. Reads all apps from `INSTALLED_APPS`
2. Scans all `.py` files for import statements
3. Identifies apps that are never imported
4. Suggests them for removal (excluding Django defaults)

## Supported Packages

The tool includes 75+ pre-configured Django package mappings. Here are some popular ones:

| Package Name | INSTALLED_APPS Name |
|-------------|-------------------|
| `djangorestframework` | `rest_framework` |
| `django-cors-headers` | `corsheaders` |
| `django-filter` | `django_filters` |
| `django-allauth` | `allauth` |
| `django-debug-toolbar` | `debug_toolbar` |
| `django-crispy-forms` | `crispy_forms` |
| `django-extensions` | `django_extensions` |
| `celery` | `celery` |
| `channels` | `channels` |
| `django-storages` | `storages` |
| `django-redis` | `django_redis` |
| `django-taggit` | `taggit` |
| `django-guardian` | `guardian` |
| `django-oauth-toolkit` | `oauth2_provider` |
| `django-import-export` | `import_export` |
| `django-tables2` | `django_tables2` |
| `django-phonenumber-field` | `phonenumber_field` |
| `django-countries` | `django_countries` |
| `django-imagekit` | `imagekit` |
| `django-cleanup` | `django_cleanup` |
| `django-reversion` | `reversion` |
| `django-simple-history` | `simple_history` |
| `django-ckeditor` | `ckeditor` |
| `django-constance` | `constance` |
| `django-grappelli` | `grappelli` |
| `django-jazzmin` | `jazzmin` |
| `channels-redis` | `channels_redis` |
| `daphne` | `daphne` |

**Note:** Packages like `pillow`, `psycopg2`, `gunicorn`, and `mysqlclient` are dependencies only and don't need to be added to `INSTALLED_APPS`.

[View complete list of 75+ packages](https://github.com/Rohan7654/django-include-apps/blob/main/django-include-apps/django_include_apps/package_mappings.json)

## Protected Django Apps

The following default Django apps are protected from removal:
- `django.contrib.admin`
- `django.contrib.auth`
- `django.contrib.contenttypes`
- `django.contrib.sessions`
- `django.contrib.messages`
- `django.contrib.staticfiles`
- Any app starting with `django.`

## Requirements

- Python 3.8+
- Django project
- Active virtual environment (recommended)

## Command Reference

### `add-app`
Add a single app to INSTALLED_APPS.

```bash
django-include-apps add-app <package-name> [OPTIONS]
```

**Options:**
- `--start-dir, -d`: Directory to search for settings.py (default: current directory)

**Features:**
- Checks package mappings for automatic app name detection
- Prompts for custom app names if not mapped
- Offers to save new mappings for future use
- Manages requirements.txt automatically

### `add-apps`
Add multiple apps to INSTALLED_APPS.

```bash
django-include-apps add-apps <package-name-1> <package-name-2> ... [OPTIONS]
```

**Options:**
- `--start-dir, -d`: Directory to search for settings.py (default: current directory)

**Features:**
- Batch processing with individual prompts for each package
- Smart package mapping for all packages
- Consolidated requirements.txt management

### `remove-app`
Remove a single app from INSTALLED_APPS, or detect unused apps if no name provided.

```bash
django-include-apps remove-app [app-name] [OPTIONS]
```

**Options:**
- `--start-dir, -d`: Directory to search for settings.py (default: current directory)

**Features:**
- **Without app name**: Scans project and suggests unused apps
- **With app name**: Removes specified app with confirmation
- Automatic requirements.txt cleanup
- Protection for Django default apps

### `remove-apps`
Remove multiple apps from INSTALLED_APPS, or detect unused apps if no names provided.

```bash
django-include-apps remove-apps [app-name-1] [app-name-2] ... [OPTIONS]
```

**Options:**
- `--start-dir, -d`: Directory to search for settings.py (default: current directory)

**Features:**
- **Without app names**: Scans project and suggests unused apps
- **With app names**: Batch removal with protection for Django defaults
- Automatic requirements.txt cleanup for all removed apps

### install-requirements

Install packages from requirements.txt and automatically add Django packages to INSTALLED_APPS.

```bash
django-include-apps install-requirements -r requirements.txt
# or
django-include-apps install-requirements --requirements requirements.txt [OPTIONS]
```

**Options:**
- `--requirements, -r`: Path to requirements.txt file (required)
- `--start-dir, -d`: Directory to search for settings.py (default: current directory)

**Features:**
- Installs all packages from requirements.txt
- Detects Django-related packages automatically
- Uses smart package mapping for known packages
- Interactive checkbox selection for packages to add
- Prompts for app names for unmapped packages
- Saves new mappings for future use

**Example:**
```bash
django-include-apps install-requirements -r requirements.txt
```

**Sample Output:**
```
Found 15 package(s) in requirements.txt
Installing packages from requirements.txt...
Successfully installed packages from requirements.txt

Detecting Django-related packages...
Found 5 Django package(s):
  • djangorestframework → rest_framework
  • django-cors-headers → corsheaders
  • django-filter → django_filters
  • django-allauth → allauth
  • celery (not mapped)

? Select packages to add to INSTALLED_APPS (use space to select, enter to confirm)
  ◉ djangorestframework (rest_framework)
  ◉ django-cors-headers (corsheaders)
  ◯ django-filter (django_filters)
  ◉ django-allauth (allauth)
  ◯ celery (unmapped - will prompt for app name)

Adding selected packages to INSTALLED_APPS...
✓ Added 'rest_framework' to INSTALLED_APPS
✓ Added 'corsheaders' to INSTALLED_APPS
✓ Added 'allauth' to INSTALLED_APPS

Done! 3 package(s) added to INSTALLED_APPS.
```

### view-mappings

View all package mappings in a table format.

```bash
django-include-apps view-mappings [OPTIONS]
```

**Options:**
- `--filter, -f`: Filter by package name (supports wildcards like `django-*`)
- `--null-only`: Show only dependency packages (not added to INSTALLED_APPS)
- `--apps-only`: Show only packages with app names

**Features:**
- Display all 77+ package mappings in organized table
- Filter by package name patterns
- Color-coded output (packages in cyan, apps in green)
- Shows total and filtered counts

**Examples:**
```bash
# View all mappings
django-include-apps view-mappings

# Filter Django packages
django-include-apps view-mappings --filter "django-*"

# Show only dependency packages
django-include-apps view-mappings --null-only

# Show only packages with app names
django-include-apps view-mappings --apps-only
```

**Sample Output:**
```
Package Mappings (77 total)

Package Name              INSTALLED_APPS Name         
──────────────────────────────────────────────────────
djangorestframework       rest_framework              
django-cors-headers       corsheaders                 
django-filter             django_filters              
django-environ            (not added to INSTALLED_APPS)
gunicorn                  (not added to INSTALLED_APPS)
```

### mapping

Manage package mappings via CLI commands.

#### mapping list

List all package mappings (alias for view-mappings).

```bash
django-include-apps mapping list [OPTIONS]
```

Same options as `view-mappings`.

#### mapping add

Add a new package mapping.

```bash
django-include-apps mapping add <package-name> <app-name>
django-include-apps mapping add <package-name> --null
```

**Examples:**
```bash
# Add a new mapping
django-include-apps mapping add my-custom-package my_custom_app

# Add a dependency-only package
django-include-apps mapping add redis --null
```

**Sample Output:**
```
✓ Added mapping: my-custom-package → my_custom_app
```

#### mapping update

Update an existing package mapping.

```bash
django-include-apps mapping update <package-name> <new-app-name>
django-include-apps mapping update <package-name> --null
```

**Examples:**
```bash
# Update existing mapping
django-include-apps mapping update django-cors-headers new_name

# Change to dependency-only
django-include-apps mapping update gunicorn --null
```

**Sample Output:**
```
✓ Updated mapping: django-cors-headers
  Old: corsheaders
  New: new_name
```

#### mapping remove

Remove a package mapping.

```bash
django-include-apps mapping remove <package-name> [OPTIONS]
```

**Options:**
- `--force, -f`: Skip confirmation prompt

**Example:**
```bash
# Remove with confirmation
django-include-apps mapping remove my-custom-package

# Remove without confirmation
django-include-apps mapping remove my-custom-package --force
```

**Sample Output:**
```
Current mapping: my-custom-package → my_custom_app
? Remove this mapping? Yes
✓ Removed mapping: my-custom-package
```

### completion

Generate and install shell completion scripts for bash, zsh, or fish.

```bash
django-include-apps completion [SHELL] [OPTIONS]
```

**Arguments:**
- `SHELL`: Shell type (bash, zsh, or fish)

**Options:**
- `--install`: Install completion for the specified shell

**Features:**
- Auto-completion for all commands and options
- Tab completion for package names
- Easy installation with `--install` flag
- Supports bash, zsh, and fish shells

**Examples:**
```bash
# Show available shells and instructions
django-include-apps completion

# Install completion for bash
django-include-apps completion bash --install

# Install completion for zsh
django-include-apps completion zsh --install

# Install completion for fish
django-include-apps completion fish --install

# View completion script (for manual installation)
django-include-apps completion bash
```

**Sample Output:**
```
Shell completion setup:

Bash:
  django-include-apps completion bash --install
  Or manually: django-include-apps completion bash >> ~/.bashrc

Zsh:
  django-include-apps completion zsh --install
  Or manually: django-include-apps completion zsh >> ~/.zshrc

Fish:
  django-include-apps completion fish --install
  Or manually: django-include-apps completion fish > ~/.config/fish/completions/django-include-apps.fish
```

**After Installation:**
- Bash/Zsh: Run `source ~/.bashrc` or `source ~/.zshrc`, or restart your terminal
- Fish: Restart your terminal or run `source ~/.config/fish/config.fish`

## Version Specifier Support

You can specify package versions when adding apps:

```bash
# Install specific version
django-include-apps add-app djangorestframework==3.14.0

# Install minimum version
django-include-apps add-app django-filter>=2.0

# Install compatible version
django-include-apps add-app django-cors-headers~=4.0.0

# Multiple packages with versions
django-include-apps add-apps djangorestframework==3.14.0 django-filter>=2.0
```

**How it works:**
- Extracts package name for mapping lookups
- Uses full specification (with version) for pip installation
- Saves mapping using clean package name
- Adds to requirements.txt with specified version

## Future Roadmap

### Planned Features

The following features are planned for future releases. Contributions are welcome!

#### 1. Automatic Settings Configuration
- **MIDDLEWARE Management**: Automatically add/remove middleware entries when packages require them
  - Example: `corsheaders.middleware.CorsMiddleware` for django-cors-headers
  - Example: `debug_toolbar.middleware.DebugToolbarMiddleware` for django-debug-toolbar
- **DATABASES Configuration**: Detect and configure database backends
  - PostgreSQL (psycopg2), MySQL (mysqlclient), etc.
- **TEMPLATES Configuration**: Auto-configure template backends and context processors
- **CACHING Configuration**: Setup cache backends (Redis, Memcached)
- **REST_FRAMEWORK Settings**: Auto-generate REST framework configuration blocks

#### 2. Package-Specific Settings
- Detect required settings for packages and prompt for configuration
- Example: `CORS_ALLOWED_ORIGINS` for django-cors-headers
- Example: `INTERNAL_IPS` for django-debug-toolbar
- Example: `CELERY_BROKER_URL` for Celery
- Template-based configuration snippets

#### 3. Environment Variables Management
- Create/update `.env` files with package-specific variables
- Generate `.env.example` templates
- Integrate with python-decouple or django-environ

#### 4. URL Configuration
- Detect packages that need URL patterns
- Suggest URL includes for packages like django-allauth, rest_framework, etc.
- Auto-add to `urls.py` with user confirmation

#### 5. Static Files & Media Configuration
- Configure `STATIC_ROOT`, `MEDIA_ROOT` for packages that need them
- Setup for django-storages (S3, GCS, etc.)

#### 6. Testing & Quality
- Detect test dependencies and configure test settings
- Setup coverage.py configuration
- Configure pre-commit hooks for code quality

#### 7. Docker & Deployment
- Generate Dockerfile with detected dependencies
- Create docker-compose.yml with required services (PostgreSQL, Redis, etc.)
- Generate deployment configuration (Heroku, AWS, etc.)

#### 8. Package Updates
- Check for package updates
- Update requirements.txt with latest versions
- Show changelog for updated packages

#### 9. Project Scaffolding
- Initialize new Django projects with common packages
- Template-based project setup (REST API, Full-stack, etc.)

### Contributing Ideas

Have an idea for a new feature? We'd love to hear it! Please:
1. Check existing issues to avoid duplicates
2. Open a new issue with your feature request
3. Describe the use case and expected behavior
4. Consider submitting a pull request!

## Contributing

Contributions are welcome! If you find a Django package that should be added to the mapping, please:
1. Fork the repository
2. Add the mapping to `package_mappings.json`
3. Submit a pull request

## License

MIT License - see LICENSE file for details

## Author

**ROHAN**
- Email: rohanroni2019@gmail.com
- GitHub: [@Rohan7654](https://github.com/Rohan7654)

## Contributors

Special thanks to contributors who helped improve this project:

- **Rohan Shinde** - Contributed to remove-apps functionality and feature enhancements

## Links

- **Repository**: https://github.com/Rohan7654/django-include-apps
- **PyPI**: https://pypi.org/project/django-include-apps/
- **Issues**: https://github.com/Rohan7654/django-include-apps/issues
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

## Support

If you encounter any issues or have questions, please:
1. Check the [documentation](https://github.com/Rohan7654/django-include-apps#readme)
2. Search [existing issues](https://github.com/Rohan7654/django-include-apps/issues)
3. Create a [new issue](https://github.com/Rohan7654/django-include-apps/issues/new) if needed

## Contributing

Contributions are welcome! If you find a Django package that should be added to the mapping, please:
1. Fork the repository
2. Add the mapping to `package_mappings.json`
3. Submit a pull request

If anymore features are to be added, please create an issue and I will add it to the roadmap.

