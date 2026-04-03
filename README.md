# GitHub Skyline — 3D-Printable Contribution History

Generate a 3D-printable STL skyline from any GitHub user's contribution history.

Adapted from [gitlab-skyline](https://gitlab.com/felixgomez/gitlab-skyline) by Félix Gómez.

## How It Works

1. Fetches a full year of contribution data via the **GitHub GraphQL API** (single request)
2. Generates an OpenSCAD model with contribution bars, username, and year engraved on the base
3. Renders the model to an STL file ready for 3D printing

## Requirements

- **Python 3.14+**
- **OpenSCAD** — install from https://www.openscad.org/downloads.html
- **GitHub Personal Access Token** with `read:user` scope

Verify OpenSCAD is installed:

```
openscad --version
```

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```
usage: github-skyline [-h] --token TOKEN [--displayname DISPLAYNAME] username [year]

Create a 3D-printable STL skyline from GitHub contributions

positional arguments:
  username              GitHub username (without @)
  year                  Year of contributions to fetch (default: last year)

optional arguments:
  -h, --help            show this help message and exit
  --token TOKEN         GitHub Personal Access Token (needs read:user scope)
  --displayname NAME    Display name to engrave on the model (default: username)
```

### Examples

```bash
# Generate skyline for user "octocat" for 2024
python github-skyline octocat 2024 --token ghp_xxxxxxxxxxxx

# Use a display name on the model
python github-skyline octocat 2024 --token ghp_xxxxxxxxxxxx --displayname "The Octocat"
```

### Batch Generation for a Team

```bash
#!/bin/bash
TOKEN="ghp_xxxxxxxxxxxx"
YEAR=2024
for user in engineer1 engineer2 engineer3; do
  python github-skyline "$user" "$YEAR" --token "$TOKEN"
done
```

## Output

- `github_<username>_<year>.scad` — OpenSCAD source
- `github_<username>_<year>.stl` — 3D-printable STL file

## Mesh Optimization

If the STL has geometry errors, use [MeshLab](https://www.meshlab.net/) to repair them before printing.

## Tips for 3D Printing

- Print with the base flat on the build plate
- 0.2mm layer height works well for the contribution bars
- PLA is fine; consider using your team/company brand colors
