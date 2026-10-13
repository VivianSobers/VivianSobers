#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
root=$(pwd)
PY=${PY:-.venv/bin/python}
times=${1:-2,7.5,13,18.5}
browser=${BROWSER:-}
if [ -z "$browser" ]; then
    for browser in /usr/bin/*-chrome; do
        [ -x "$browser" ] && break
    done
fi
mkdir -p .preview
for build in header/build.py figures/*/build.py; do
    if [ -f "$build" ]; then
        "$PY" "$build" --preview "$times"
    fi
done
for svg in .preview/*-light-*.svg .preview/*-dark-*.svg; do
    [ -f "$svg" ] || continue
    height=$("$PY" -c 'import sys, xml.etree.ElementTree as ET; print(round(float(ET.parse(sys.argv[1]).getroot().attrib["height"])))' "$svg")
    png=${svg%.svg}.png
    background=ffffffff
    case "$svg" in *-dark-*) background=0d1117ff ;; esac
    if ! "$browser" --headless=new --disable-gpu --hide-scrollbars \
        --default-background-color="$background" \
        --screenshot="$png" --window-size="1280,$height" "file://$root/$svg" >/dev/null 2>&1; then
        echo "Rendering failed: $svg" >&2
        exit 1
    fi
    [ -s "$png" ] || exit 1
    echo "Rendered $png (1280 x $height)"
done
