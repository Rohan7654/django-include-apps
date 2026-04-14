# django-include-apps

[![PyPI version](https://badge.fury.io/py/django-include-apps.svg)](https://badge.fury.io/py/django-include-apps)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-include-apps.svg)](https://pypi.org/project/django-include-apps/)
[![Django Versions](https://img.shields.io/badge/django-2.2%20%7C%203.0%20%7C%203.1%20%7C%203.2%20%7C%204.0%20%7C%204.1%20%7C%204.2%20%7C%205.0-blue.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/django-include-apps)](https://pepy.tech/project/django-include-apps)
[![Downloads/Month](https://static.pepy.tech/badge/django-include-apps/month)](https://pepy.tech/project/django-include-apps)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/Rohan7654/django-include-apps/graphs/commit-activity)

A powerful CLI tool to intelligently manage Django apps in your `INSTALLED_APPS` setting. Install, add, remove, and maintain Django packages with smart package mapping and automatic `requirements.txt` management.

## Features

- **Smart Package Mapping** — 85+ pre-configured mappings (e.g., `djangorestframework` → `rest_framework`)
- **Extended Configs** — Auto-apply middleware, settings, URL patterns, and imports per package
- **Auto Migrations** — Prompt to run `python manage.py migrate` when adding/removing packages that need it
- **Version Specifiers** — Install exact versions (`djangorestframework==3.14.0`, `django-filter>=2.0`)
- **Unused App Detection** — Scan your project and remove apps not imported anywhere
- **requirements.txt Sync** — Automatically add, update, and remove packages
- **Backup & Rollback** — Auto-backup `settings.py` with one-command restore
- **Security** — Move secrets to `.env` with `secure-settings`
- **Health Checks** — Run `doctor` to audit your configuration
- **Interactive Prompts** — Confirmations, multi-select, and skip options throughout
- **Shell Completion** — Tab-completion for bash, zsh, and fish

## Installation

```bash
pip install django-include-apps
```

## Quick Start

### Add a Package

```bash
django-include-apps add-app djangorestframework
```

```
 IMPORTANT: Configurations applied are based on the latest package documentation.

✅ djangorestframework installed via pip
✅ Added 'rest_framework' to INSTALLED_APPS

Configuration for: djangorestframework
  • URL Pattern: path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
  • Settings:
      REST_FRAMEWORK = {
          "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
          "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
          "PAGE_SIZE": 10,
          ...
      }

? Found additional configuration for package 'djangorestframework' (Space to toggle):
  [x] URL Patterns
  [x] Required Settings
? Proceed? Yes, apply changes

✅ Added URL pattern 'api-auth/'
✅ Added REST_FRAMEWORK settings
✅ Added djangorestframework==3.15.2 to requirements.txt
```

### Add Multiple Packages

```bash
django-include-apps add-app djangorestframework django-cors-headers django-filter
```

### Remove an App

```bash
# Remove a specific app
django-include-apps remove-app rest_framework

# Or scan for unused apps (interactive)
django-include-apps remove-app
```

### Install from requirements.txt

```bash
django-include-apps install-requirements -r requirements.txt
```

Installs all packages, detects Django-related ones, and offers to add them to `INSTALLED_APPS` with extended configuration.

### Custom Project Directory

```bash
django-include-apps add-app djangorestframework -d /path/to/django/project
```

All commands accept `--start-dir` / `-d` to target a specific project.

## Commands Overview

| Command                | Description                                        |
| ---------------------- | -------------------------------------------------- |
| `add-app`              | Add one or more apps to `INSTALLED_APPS`           |
| `remove-app`           | Remove apps or scan for unused ones                |
| `install-requirements` | Install from `requirements.txt` and configure apps |
| `status`               | Show project configuration overview                |
| `doctor`               | Run health checks on your project                  |
| `show-config`          | Display extended config for a package              |
| `view-mappings`        | Browse all 85+ package mappings                    |
| `diff`                 | Preview changes before applying (dry run)          |
| `sync`                 | Compare `INSTALLED_APPS` ↔ `requirements.txt`      |
| `update-configs`       | Check for updated package configurations           |
| `graph`                | Visualize package dependencies                     |
| `profile`              | Save/apply/export configuration profiles           |
| `init-env`             | Create a virtual environment                       |
| `secure-settings`      | Move secrets to `.env`                             |
| `rollback`             | Restore `settings.py` from backup                  |
| `setup-hooks`          | Set up pre-commit hooks                            |
| `docker-init`          | Generate Docker configuration                      |
| `tutorial`             | Interactive learning guide                         |
| `completion`           | Shell auto-completion setup                        |
| `mapping`              | Manage custom package mappings                     |

📖 **[Full Command Reference →](https://github.com/Rohan7654/django-include-apps/blob/main/django-include-apps/COMMANDS.md)** — Every command with all flags, variants, and sample output.

## Supported Packages

85+ pre-configured Django packages with smart mapping:

| Package                | INSTALLED_APPS Name |
| ---------------------- | ------------------- |
| `djangorestframework`  | `rest_framework`    |
| `django-cors-headers`  | `corsheaders`       |
| `django-filter`        | `django_filters`    |
| `django-allauth`       | `allauth`           |
| `django-debug-toolbar` | `debug_toolbar`     |
| `django-crispy-forms`  | `crispy_forms`      |
| `django-extensions`    | `django_extensions` |
| `channels`             | `channels`          |
| `celery`               | `celery`            |
| `django-storages`      | `storages`          |

> **Note:** Packages like `pillow`, `psycopg2`, `gunicorn`, and `mysqlclient` are dependency-only and aren't added to `INSTALLED_APPS`.

> **Disclaimer on configurations:** The automatic configuration settings provided by `django-include-apps` (for `MIDDLEWARE`, `urls.py`, etc.) are based on the standard and latest documentation of the respective packages at the time of mapping. 

Use `django-include-apps view-mappings` to see the complete list. Unmapped packages are handled interactively with an option to save for future use.

## Protected Django Apps

Core Django apps (`django.contrib.*`) are automatically protected from removal:

`admin` · `auth` · `contenttypes` · `sessions` · `messages` · `staticfiles`

## Requirements

- Python 3.8+
- Django project with `settings.py`
- Virtual environment (recommended)

## Example Project

A ready-to-use demo project is included to try every command hands-on:

```bash
cd django-include-apps/examples/demo_project
django-include-apps add-app djangorestframework
django-include-apps status
```

📂 **[See the demo project →](https://github.com/Rohan7654/django-include-apps/tree/main/django-include-apps/examples/)**

## Contributing

Contributions are welcome! To add a new package mapping:

1. Fork the repository
2. Add the mapping to `package_configs.json`
3. Submit a pull request

Have a feature idea? [Open an issue](https://github.com/Rohan7654/django-include-apps/issues/new).

## License

MIT License — see [LICENSE](https://github.com/Rohan7654/django-include-apps/blob/main/LICENSE) for details.

## Author

**ROHAN** — [GitHub](https://github.com/Rohan7654) · [Email](mailto:rohanroni2019@gmail.com)

### Contributors

- **Rohan Shirude** — remove-app functionality and feature enhancements

## Links

- **Repository**: https://github.com/Rohan7654/django-include-apps
- **PyPI**: https://pypi.org/project/django-include-apps/
- **Issues**: https://github.com/Rohan7654/django-include-apps/issues
- **Changelog**: [CHANGELOG.md](https://github.com/Rohan7654/django-include-apps/blob/main/CHANGELOG.md)
- **Demo Project**: [examples/](https://github.com/Rohan7654/django-include-apps/tree/main/django-include-apps/examples/)
