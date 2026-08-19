#!/usr/bin/env python3
"""Inline the tone grid into the HTML template -> one self-contained file."""
import argparse, pathlib

p = argparse.ArgumentParser()
p.add_argument("--grid", default="out/grid.json")
p.add_argument("--tpl",  default="web/template.html")
p.add_argument("--out",  default="out/live.html")
a = p.parse_args()

html = pathlib.Path(a.tpl).read_text().replace("__GRID__", pathlib.Path(a.grid).read_text())
pathlib.Path(a.out).write_text(html)
print(f"{a.out}  {len(html)//1024} KB")
