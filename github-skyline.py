#!/usr/bin/env python3

import argparse
import datetime
import math
import os
import shutil
import subprocess
import time
from calendar import monthrange
from collections import defaultdict

import requests
from solid2 import *

__author__ = "Adapted from gitlab-skyline by Félix Gómez"


def _graphql_post(token, query, variables=None):
    """Execute a GraphQL query against the GitHub API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {"query": query}
    if variables:
        body["variables"] = variables
    resp = requests.post("https://api.github.com/graphql", json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def _rest_get_paginated(url, params, headers, max_pages=50):
    """Paginate a REST API list endpoint."""
    all_items = []
    for page in range(1, max_pages + 1):
        resp = requests.get(url, params={**params, "per_page": 100, "page": page}, headers=headers)
        if resp.status_code == 409:
            break
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset - int(time.time()), 5)
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_items.extend(batch)
        if len(batch) < 100:
            break
    return all_items


def get_contributions(username, token, year):
    """Fetch contribution data using a combination of GraphQL and REST APIs.

    Strategy:
    1. Try the GraphQL contributionCalendar first (works if org allows it)
    2. Otherwise, use GraphQL to identify repos with contributions, then REST to
       get commit dates from those repos, plus GraphQL for PRs/issues/reviews.
    """

    rest_headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    year_start = f"{year}-01-01T00:00:00Z"
    year_end = f"{year}-12-31T23:59:59Z"

    # --- Attempt 1: GraphQL contribution calendar (fastest, exact match) ---
    print("  Trying GraphQL contribution calendar...")
    try:
        data = _graphql_post(token, """
            query($username: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $username) {
                contributionsCollection(from: $from, to: $to) {
                  contributionCalendar {
                    totalContributions
                    weeks {
                      contributionDays { contributionCount date weekday }
                    }
                  }
                }
              }
            }
        """, {"username": username, "from": year_start, "to": year_end})

        calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
        total = calendar["totalContributions"]
        if total > 1:
            print(f"  Calendar returned {total} contributions.")
            matrix = []
            for week in calendar["weeks"]:
                for day in week["contributionDays"]:
                    dt = datetime.datetime.strptime(day["date"], "%Y-%m-%d")
                    matrix.append([int(dt.strftime("%j")), day["weekday"], day["contributionCount"]])
            return matrix
        print(f"  Calendar returned only {total} (org may restrict this data).")
    except Exception as e:
        print(f"  Calendar query failed: {e}")

    # --- Attempt 2: Combined GraphQL + REST approach ---
    print("  Using combined GraphQL + REST approach...")
    daily_counts = defaultdict(int)

    # Step 1: GraphQL — get list of repos with commit contributions
    print("  Identifying repos with contributions...")
    data = _graphql_post(token, """
        query($username: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $username) {
            contributionsCollection(from: $from, to: $to) {
              commitContributionsByRepository {
                repository { nameWithOwner }
                contributions { totalCount }
              }
              pullRequestContributions(first: 100) {
                nodes { pullRequest { createdAt } }
              }
              issueContributions(first: 100) {
                nodes { issue { createdAt } }
              }
              pullRequestReviewContributions(first: 100) {
                nodes { pullRequestReview { createdAt } }
                totalCount
              }
            }
          }
        }
    """, {"username": username, "from": year_start, "to": year_end})

    coll = data["user"]["contributionsCollection"]

    # Step 2: REST — get commit dates from each contributing repo
    contrib_repos = coll["commitContributionsByRepository"]
    print(f"  Found {len(contrib_repos)} repos with commits.")
    commit_total = 0
    seen_shas = set()
    for entry in contrib_repos:
        repo_name = entry["repository"]["nameWithOwner"]
        expected = entry["contributions"]["totalCount"]
        commits = _rest_get_paginated(
            f"https://api.github.com/repos/{repo_name}/commits",
            {"author": username, "since": year_start, "until": f"{year + 1}-01-01T00:00:00Z"},
            rest_headers,
        )
        repo_count = 0
        for c in commits:
            sha = c["sha"]
            if sha in seen_shas:
                continue
            seen_shas.add(sha)
            d = c["commit"]["author"]["date"][:10]
            daily_counts[d] += 1
            repo_count += 1
        commit_total += repo_count
        print(f"    {repo_name}: {repo_count} commits (API expected {expected})")

    print(f"  Total commits: {commit_total}")

    # Step 3: PRs opened
    pr_nodes = coll["pullRequestContributions"]["nodes"]
    pr_count = 0
    for node in pr_nodes:
        pr = node.get("pullRequest")
        if pr:
            d = pr["createdAt"][:10]
            if d.startswith(str(year)):
                daily_counts[d] += 1
                pr_count += 1
    print(f"  PRs opened: {pr_count}")

    # Step 4: Issues opened
    issue_nodes = coll["issueContributions"]["nodes"]
    issue_count = 0
    for node in issue_nodes:
        issue = node.get("issue")
        if issue:
            d = issue["createdAt"][:10]
            if d.startswith(str(year)):
                daily_counts[d] += 1
                issue_count += 1
    print(f"  Issues opened: {issue_count}")

    # Step 5: PR reviews
    review_nodes = coll["pullRequestReviewContributions"]["nodes"]
    review_total_available = coll["pullRequestReviewContributions"]["totalCount"]
    review_count = 0
    for node in review_nodes:
        rev = node.get("pullRequestReview")
        if rev:
            d = rev["createdAt"][:10]
            if d.startswith(str(year)):
                daily_counts[d] += 1
                review_count += 1
    print(f"  PR reviews: {review_count}" + (f" (of {review_total_available} total)" if review_total_available > len(review_nodes) else ""))

    grand_total = commit_total + pr_count + issue_count + review_count
    print(f"  Grand total: {grand_total}")

    # Build contribution matrix for every day of the year
    contribution_matrix = []
    for month in range(1, 13):
        for day in range(1, monthrange(year, month)[1] + 1):
            dt = datetime.date(year, month, day)
            day_of_year = int(dt.strftime("%j"))
            weekday = dt.isoweekday() % 7  # 0=Sun, 1=Mon, ..., 6=Sat
            count = daily_counts.get(dt.strftime("%Y-%m-%d"), 0)
            contribution_matrix.append([day_of_year, weekday, count])

    return contribution_matrix


def parse_contribution_matrix(contribution_matrix):
    day_offset = sorted(contribution_matrix, key=lambda x: x[0])[0][1]
    max_contributions_by_day = sorted(contribution_matrix, key=lambda x: x[2], reverse=True)[0][2]
    ordered_contribution_matrix = sorted(contribution_matrix, key=lambda x: x[0])
    year_contribution_list = [row.pop(2) for row in ordered_contribution_matrix]

    for i in range(day_offset):
        year_contribution_list.insert(0, 0)

    return [year_contribution_list, max_contributions_by_day]


def generate_skyline_stl(username, year, contribution_matrix, scale_factor=1.0):
    year_contribution_list, max_contributions_by_day = parse_contribution_matrix(contribution_matrix)

    if max_contributions_by_day == 0:
        print(f"No contributions found for {username} in {year}.")
        return

    base_top_width = 23 * scale_factor
    base_width = 30 * scale_factor
    base_length = 150 * scale_factor
    base_height = 10 * scale_factor
    max_length_contributionbar = 20 * scale_factor
    bar_base_dimension = 2.5 * scale_factor

    base_top_offset = (base_width - base_top_width) / 2
    face_angle = math.degrees(math.atan(base_height / base_top_offset))

    base_points = [
        [0, 0, 0],
        [base_length, 0, 0],
        [base_length, base_width, 0],
        [0, base_width, 0],
        [base_top_offset, base_top_offset, base_height],
        [base_length - base_top_offset, base_top_offset, base_height],
        [base_length - base_top_offset, base_width - base_top_offset, base_height],
        [base_top_offset, base_width - base_top_offset, base_height]
    ]

    base_faces = [
        [0, 1, 2, 3],  # bottom
        [4, 5, 1, 0],  # front
        [7, 6, 5, 4],  # top
        [5, 6, 2, 1],  # right
        [6, 7, 3, 2],  # back
        [7, 4, 0, 3]   # left
    ]

    base_scad = polyhedron(points=base_points, faces=base_faces)

    year_scad = rotate([face_angle, 0, 0])(
        translate([base_length - base_length / 5, base_height / 2 - base_top_offset / 2 - 1 * scale_factor, -1.5 * scale_factor])(
            linear_extrude(height=2 * scale_factor)(
                text(str(year), 6 * scale_factor)
            )
        )
    )

    user_scad = rotate([face_angle, 0, 0])(
        translate([base_length / 4, base_height / 2 - base_top_offset / 2, -1.5 * scale_factor])(
            linear_extrude(height=2 * scale_factor)(
                text("@" + username, 5 * scale_factor)
            )
        )
    )

    logo_scad = rotate([face_angle, 0, 0])(
        translate([base_length / 8, base_height / 2 - base_top_offset / 2 - 1.5 * scale_factor, -1 * scale_factor])(
            linear_extrude(height=2 * scale_factor)(
                scale([0.04 * scale_factor, 0.04 * scale_factor, 0.04 * scale_factor])(
                    import_(os.path.dirname(os.path.realpath(__file__)) + os.path.sep + "github.svg")
                )
            )
        )
    )

    bars = None

    week_number = 1
    for i in range(len(year_contribution_list)):

        day_number = i % 7
        if day_number == 0:
            week_number += 1

        if year_contribution_list[i] == 0:
            continue

        bar = translate(
            [base_top_offset + 2.5 * scale_factor + (week_number - 1) * bar_base_dimension,
             base_top_offset + 2.5 * scale_factor + day_number * bar_base_dimension, base_height])(
            cube([bar_base_dimension, bar_base_dimension,
                  year_contribution_list[i] * max_length_contributionbar / max_contributions_by_day])
        )

        if bars is None:
            bars = bar
        else:
            bars += bar

    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'stl_and_scad_files')
    os.makedirs(output_dir, exist_ok=True)

    scad_contributions_filename = os.path.join(output_dir, 'github_' + username + '_' + str(year))
    scad_base_object = base_scad - logo_scad + user_scad + year_scad
    scad_skyline_object = scad_base_object

    if bars is not None:
        scad_skyline_object += bars

    openscad_bin = shutil.which('openscad')
    if openscad_bin is None:
        # macOS Homebrew cask common paths
        mac_paths = [
            '/opt/homebrew/bin/openscad',
            '/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD',
        ]
        for p in mac_paths:
            if os.path.isfile(p):
                openscad_bin = p
                break

    if openscad_bin is None:
        print(f"WARNING: openscad not found on PATH. SCAD file written to {scad_contributions_filename}.scad")
        print("Install OpenSCAD and run manually:")
        print(f"  openscad -o {scad_contributions_filename}.stl {scad_contributions_filename}.scad")
        return

    # Combined STL
    scad_skyline_object.save_as_scad(scad_contributions_filename + '.scad')
    subprocess.run([openscad_bin, '-o', scad_contributions_filename + '.stl', scad_contributions_filename + '.scad'],
                   capture_output=True)
    print('Generated STL file ' + scad_contributions_filename + '.stl')

    # Base-only STL (for multicolor printing)
    scad_base_object.save_as_scad(scad_contributions_filename + '_base.scad')
    subprocess.run([openscad_bin, '-o', scad_contributions_filename + '_base.stl', scad_contributions_filename + '_base.scad'],
                   capture_output=True)
    print('Generated STL file ' + scad_contributions_filename + '_base.stl')

    # Bars-only STL (for multicolor printing)
    if bars is not None:
        bars.save_as_scad(scad_contributions_filename + '_bars.scad')
        subprocess.run([openscad_bin, '-o', scad_contributions_filename + '_bars.stl', scad_contributions_filename + '_bars.scad'],
                       capture_output=True)
        print('Generated STL file ' + scad_contributions_filename + '_bars.stl')


def main():
    parser = argparse.ArgumentParser(
        prog="github-skyline",
        description='Create a 3D-printable STL skyline from GitHub contributions',
        epilog='Enjoy!'
    )
    parser.add_argument('username', type=str, help='GitHub username (without @)')
    parser.add_argument('year', type=int, nargs="?", default=datetime.datetime.now().year - 1,
                        help='Year of contributions to fetch (default: last year)')
    parser.add_argument('--token', type=str, default=None,
                        help='GitHub Personal Access Token (needs read:user scope). '
                             'Defaults to reading from ~/.github_token if not provided.')
    parser.add_argument('--displayname', type=str, default=None,
                        help='Display name to engrave on the model (default: username)')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Scale factor for the entire model (default: 1.0, e.g. 1.2 for 20% larger)')

    args = parser.parse_args()

    username = args.username
    year = args.year
    displayname = args.displayname if args.displayname else username

    # Read token from --token arg or ~/.github_token file
    if args.token:
        token = args.token
    else:
        token_file = os.path.expanduser('~/.github_token')
        if os.path.isfile(token_file):
            with open(token_file, 'r') as f:
                token = f.read().strip()
            if not token:
                parser.error(f"Token file {token_file} is empty. Provide --token or add a token to the file.")
        else:
            parser.error(f"No --token provided and {token_file} not found. Create the file with your PAT or use --token.")

    print(f"Fetching {year} contributions for {username} from GitHub...")

    contribution_matrix = get_contributions(username, token, year)

    print(f"Found {sum(c[2] for c in contribution_matrix)} total contributions across {len(contribution_matrix)} days.")
    print("Generating STL...")

    generate_skyline_stl(displayname, year, contribution_matrix, args.scale)


if __name__ == '__main__':
    main()
