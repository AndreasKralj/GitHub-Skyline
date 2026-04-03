# GitHub Skyline — 3D-Printable Contribution History

Generate a 3D-printable STL skyline from any GitHub user's contribution history.

Adapted from [gitlab-skyline](https://gitlab.com/felixgomez/gitlab-skyline) by Félix Gómez.

## How It Works

1. Fetches a full year of contribution data via the **GitHub GraphQL API** (single request)
2. Generates an OpenSCAD model with contribution bars, username, and year engraved on the base
3. (Optional) Renders the model to an STL file ready for 3D printing if OpenSCAD is installed

## Requirements

- **Python 3.14+**
- **GitHub Personal Access Token** with `read:user` scope
- **OpenSCAD** (optional, for STL generation... currently the stable release is not signed on macos)
- **Public GitHub profile** - The target user's profile must be public to access contribution data

The token can be provided via `--token` argument or stored in `~/.github_token` file (which is used by default).

### Making Your Profile Public

If you're generating a skyline for your own profile, ensure it's not private:

1. In the upper-right corner of any page on GitHub, click your profile picture, then click Settings
2. Navigate to the "Public profile" section, and scroll down to "Contributions & Activity"
3. **Uncheck** the checkbox next to "Make profile private and hide activity"
4. Click Update preferences

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```
usage: github-skyline.py [-h] [--token TOKEN] [--displayname DISPLAYNAME] username [year]

Create a 3D-printable STL skyline from GitHub contributions

positional arguments:
  username              GitHub username (without @)
  year                  Year of contributions to fetch (default: last year)

optional arguments:
  -h, --help            show this help message and exit
  --token TOKEN         GitHub Personal Access Token (needs read:user scope).
                        Defaults to reading from ~/.github_token if not provided.
  --displayname NAME    Display name to engrave on the model (default: username)
```

### Examples

```bash
# Store your token in ~/.github_token (one-time setup)
echo "ghp_xxxxxxxxxxxx" > ~/.github_token

# Generate skyline for user "octocat" for 2024 (uses token from ~/.github_token)
python github-skyline.py octocat 2024

# Or provide token directly via command line
python github-skyline.py octocat 2024 --token ghp_xxxxxxxxxxxx

# Use a display name on the model
python github-skyline.py octocat 2024 --displayname "The Octocat"
```

### Batch Generation for a Team

```bash
#!/bin/bash
# Ensure ~/.github_token exists with your PAT
YEAR=2024
for user in engineer1 engineer2 engineer3; do
  python github-skyline.py "$user" "$YEAR"
done
```

## Output

- `github_<username>_<year>.scad` — OpenSCAD source (always generated)
- `github_<username>_<year>.stl` — 3D-printable STL file (generated only if OpenSCAD is installed)

Note: If OpenSCAD is not installed, the script will generate the SCAD file and print instructions for manual STL conversion.

## Mesh Optimization

If the STL has geometry errors, use [MeshLab](https://www.meshlab.net/) to repair them before printing.

## Tips for 3D Printing

- Print with the base flat on the build plate
- 0.2mm layer height works well for the contribution bars
- PLA is fine; consider using your team/company brand colors
