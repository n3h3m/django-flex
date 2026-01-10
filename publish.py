#!/usr/bin/env python3
import os
import sys
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PYPROJECT_FILE = os.path.join(PROJECT_ROOT, "pyproject.toml")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
EGG_INFO_PATTERN = os.path.join(PROJECT_ROOT, "*.egg-info")
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")

def restart_in_venv():
    """Restart the script in the virtual environment if it exists and we're not already in it."""
    if os.path.exists(VENV_PYTHON):
        # Check if we are already running in the venv
        # sys.executable might be the venv python or not.
        # Simple check: are we running the venv python?
        if os.path.abspath(sys.executable) != os.path.abspath(VENV_PYTHON):
            print(f"==> Restarting in virtual environment: {VENV_PYTHON}")
            try:
                os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)
            except OSError as e:
                print(f"Error restarting in venv: {e}")
                sys.exit(1)

def run_command(command, shell=False):
    """Run a shell command and exit on failure."""
    print(f"==> Running: {' '.join(command) if isinstance(command, list) else command}")
    try:
        subprocess.check_call(command, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)

def get_project_info():
    """Extract package name and version from pyproject.toml."""
    name = None
    version = None
    
    with open(PYPROJECT_FILE, "r") as f:
        content = f.read()
        
    name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if name_match:
        name = name_match.group(1)
        
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if version_match:
        version = version_match.group(1)
        
    if not name or not version:
        print("Error: Could not parse name or version from pyproject.toml")
        sys.exit(1)
        
    return name, version

def version_exists_on_pypi(package_name, version):
    """Check if a version exists on PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    try:
        with urllib.request.urlopen(url) as response:
            return response.getcode() == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        print(f"Warning: Error checking PyPI ({e.code})")
        return False
    except Exception as e:
        print(f"Warning: Error checking PyPI: {e}")
        return False

def bumps_version(current_version, package_name):
    """Calculate the next version using CalVer (YY.M.PATCH)."""
    now = datetime.now()
    current_year_short = str(now.year)[-2:]
    current_month = str(now.month)
    
    # Parse current version
    parts = current_version.split('.')
    if len(parts) >= 3:
        ver_year, ver_month, ver_patch = parts[:3]
    else:
        # Fallback if version format is weird, though we expect standard semver-ish
        ver_year, ver_month, ver_patch = "0", "0", "0"

    new_version = f"{current_year_short}.{current_month}.0"
    
    # If we are in the same calendar month, we might need to increment patch
    if ver_year == current_year_short and ver_month == current_month:
        # Start checking from the current patch + 1
        # But wait, if current_version ALREADY exists, we need something higher.
        # If current_version DOES NOT exist, we can re-use it? 
        # The prompt implies auto-bumping if needed. 
        # Let's see if the CALCULATED new_version exists.
        
        # Actually, simpler logic:
        # 1. Propose YY.M.0
        # 2. If proposed exists, increment patch until it doesn't.
        pass
    
    # Let's iterate to find a free version starting from YY.M.0
    # However, we should respect the current version if it's already ahead for some reason?
    # Logic: Start at YY.M.0. If that exists, try YY.M.1, etc.
    # ALSO, if the current local version is HIGHER than what we find on PyPI (e.g. user manually set it), 
    # we should probably respect that or warn?
    # Let's stick to the user's requested logic: "auto bump ... when month changes ... become 26.2.*"
    
    candidate_patch = 0
    candidate_version = f"{current_year_short}.{current_month}.{candidate_patch}"
    
    # Optimization: If current local version matches YY.M.*, start checking from there?
    # But PyPI is the source of truth for "taken" versions.
    
    while version_exists_on_pypi(package_name, candidate_version):
        print(f"==> Version {candidate_version} exists on PyPI...")
        candidate_patch += 1
        candidate_version = f"{current_year_short}.{current_month}.{candidate_patch}"
        
    return candidate_version

def update_pyproject_file(new_version):
    """Update the version in pyproject.toml."""
    with open(PYPROJECT_FILE, "r") as f:
        content = f.read()
        
    new_content = re.sub(
        r'^(version\s*=\s*")[^"]+(")',
        f'\\g<1>{new_version}\\g<2>',
        content,
        flags=re.MULTILINE
    )
    
    with open(PYPROJECT_FILE, "w") as f:
        f.write(new_content)
        
    print(f"==> Updated pyproject.toml to version {new_version}")

def clean():
    """Remove previous build artifacts."""
    print("==> Cleaning previous builds...")
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    
    # pattern match for .egg-info is trickier with shutil, use glob or listdir
    parent_dir = os.path.dirname(EGG_INFO_PATTERN)
    if os.path.exists(parent_dir):
        for name in os.listdir(parent_dir):
            if name.endswith(".egg-info"):
                path = os.path.join(parent_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path)

def main():
    # Ensure we use the venv
    restart_in_venv()

    # Check environment variable
    pypi_token = os.environ.get("PYPI_API_TOKEN")
    if not pypi_token:
        print("Error: PYPI_API_TOKEN environment variable is not set")
        sys.exit(1)

    print("==> checks passed")

    # Get package info
    package_name, current_version = get_project_info()
    print(f"==> Package: {package_name}")
    print(f"==> Current local version: {current_version}")
    
    # Determine next version
    target_version = bumps_version(current_version, package_name)
    
    if target_version != current_version:
        print(f"==> Bumping version to {target_version}")
        update_pyproject_file(target_version)
    else:
        print(f"==> Version {target_version} is valid and free.")
        
    # Clean
    clean()
    
    # Build
    print("==> Building package...")
    run_command([sys.executable, "-m", "build"])
    
    # Publish
    print("==> Publishing to PyPI...")
    # twine upload dist/* --username __token__ --password "$PYPI_API_TOKEN"
    twine_cmd = [
        sys.executable, "-m", "twine", "upload", "dist/*",
        "--username", "__token__",
        "--password", pypi_token
    ]
    # We need to construct the command carefully because check_call with shell=False expects args list
    # The 'dist/*' wildcard won't expand if shell=False. 
    # So we should expand it ourselves or use shell=True logic carefully.
    # Better: find the files.
    
    dist_files = [os.path.join(DIST_DIR, f) for f in os.listdir(DIST_DIR)]
    if not dist_files:
        print("Error: No distribution files found.")
        sys.exit(1)
        
    final_twine_cmd = [
        sys.executable, "-m", "twine", "upload",
        "--username", "__token__",
        "--password", pypi_token
    ] + dist_files
    
    run_command(final_twine_cmd)
    
    print(f"==> Done! Package {package_name} v{target_version} published successfully.")

if __name__ == "__main__":
    main()
