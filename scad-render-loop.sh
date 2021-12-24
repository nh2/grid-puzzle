#! /usr/bin/env sh
inotifywait -q -m -e close_write grid-renderer-scad.py |
while read -r filename event; do
  python grid-renderer-scad.py
done
