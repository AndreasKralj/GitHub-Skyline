#!/bin/bash
# Batch generate GitHub skylines and 3MF files for all DevOps team members

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

TOKEN="$(cat ~/.github-skyline-pat)"
YEAR=2025
SCALE=1.2
SETTINGS="project_settings_ref.config"
STL_DIR="stl_and_scad_files"
OUTPUT_DIR="3mf_files"

# DevOps team members: github_username|display_name
USERS=(
    "ericlanderson|Eric.Anderson"
    "Jonathan-Kane|Jonathan.Kane"
    "JustinC-VU|Justin.Clary"
    "austin-vu|Austin.Gant"
    "ais4awesome4|Andy.Buchholz"
    "scottamation|Scott.Davis"
    "aastha-lamichhane|Aastha.Lamichhane"
    "joshmiller2110|Josh.Miller"
    "ak-vuhl|Andrew.Krall"
    "ckasmann|Christi.Kasmann"
    "braden-bax|Braden.Bax"
    "nicksweeneyvu|Nick.Sweeney"
    "Seth-Ek-VU|Seth.Ek"
    "tsid2004|Taqwa.Siddiqui"
    "swageblock|Doug.Wehmeyer"
    "lpaneck|Louisa.Paneck"
    "mikejuneau|Mike.Juneau"
    "NS-CloudBoi|Nick.Stein"
    "NickHarveyVu|Nick.Harvey"
    "LukeShermanVU|Luke.Sherman"
)

mkdir -p "$STL_DIR" "$OUTPUT_DIR"

for entry in "${USERS[@]}"; do
    IFS='|' read -r username display_name <<< "$entry"
    echo ""
    echo "=========================================="
    echo "Processing: $display_name ($username)"
    echo "=========================================="

    python3 "$SCRIPT_DIR/github-skyline.py" "$username" "$YEAR" \
        --token="$TOKEN" --displayname="$display_name" --scale="$SCALE"

    BASE_STL="$STL_DIR/github_${display_name}_${YEAR}_base.stl"
    BARS_STL="$STL_DIR/github_${display_name}_${YEAR}_bars.stl"
    OUTPUT_3MF="$OUTPUT_DIR/${display_name} GitHub Skyline ${YEAR}.3mf"

    if [ ! -f "$BASE_STL" ]; then
        echo "ERROR: Base STL not found for $username, skipping 3MF generation"
        continue
    fi

    if [ ! -f "$BARS_STL" ]; then
        echo "WARNING: No bars STL for $username (no contributions?), skipping 3MF"
        continue
    fi

    python3 "$SCRIPT_DIR/generate_3mf.py" \
        "$BASE_STL" "$BARS_STL" "$OUTPUT_3MF" "$display_name" "$SETTINGS"

    echo "Done: $display_name"
done

echo ""
echo "=========================================="
echo "All done! 3MF files are in: $OUTPUT_DIR/"
echo "=========================================="
ls -la "$OUTPUT_DIR/"
