#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 13 14:44:58 2026

@author: tyberns
"""

import os, re, shutil, sys, tempfile, zipfile
os.environ.setdefault("MPLBACKEND", "Agg")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
from FullProcessFunction import FullProcess

TITLES = ["Gait metrics", "Joint moments", "Ground reaction forces",
          "Hip extensors", "Hip abductors", "Hip flexors", "Hamstrings",
          "Quadriceps", "Plantarflexors", "Dorsiflexors"]

zip_path, trial = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(dir=APP_DIR)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(tmp)

entries = [e for e in os.listdir(tmp) if e != "__MACOSX" and not e.startswith(".")]
if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
    root, name = os.path.join(tmp, entries[0]), entries[0]
else:
    root, name = tmp, os.path.splitext(os.path.basename(zip_path))[0]
session_id = re.sub(r"^OpenCapData_", "", name)

session_dir = os.path.join(APP_DIR, session_id)
link_dir = os.path.join(APP_DIR, f"OpenCapData_{session_id}")
shutil.move(root, session_dir)
os.symlink(session_dir, link_dir)

outputs = FullProcess(session_id, trial)

os.makedirs("results", exist_ok=True)
for title, df in zip(TITLES, outputs):
    df.to_csv(os.path.join("results", title.replace(" ", "_") + ".csv"))
print("DONE")