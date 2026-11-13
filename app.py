#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 13 08:18:37 2026

@author: tyberns
"""

import os
os.environ.setdefault("MPLBACKEND", "Agg")  # headless server: no plot windows

import re, resource, shutil, sys, tempfile, threading, zipfile
import pandas as pd
import streamlit as st

# FullProcess uses os.getcwd() as its base directory, so pin it to the app folder
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from FullProcessFunction import FullProcess

MAX_MB = 300

# OpenCap session IDs are UUIDs. Checking the format also guarantees an upload
# can never produce a folder name that collides with your own app files.
SESSION_ID = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

# Order must match the tuple FullProcess returns
RESULT_TITLES = [
    "Gait metrics", "Joint moments", "Ground reaction forces",
    "Hip extensors", "Hip abductors", "Hip flexors", "Hamstrings",
    "Quadriceps", "Plantarflexors", "Dorsiflexors",
]


@st.cache_resource
def get_lock():
    # One heavy job at a time across all users
    return threading.Lock()


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB -> MB on Linux


def list_trials(z):
    pattern = re.compile(r"(?:^|/)OpenSimData/Kinematics/([^/]+)\.mot$")
    return sorted({m.group(1) for n in z.namelist() if (m := pattern.search(n))})


def safe_extract(z, dest):
    dest = os.path.realpath(dest)
    if sum(i.file_size for i in z.infolist()) > MAX_MB * 1024 * 1024:
        raise ValueError(f"Archive too large (limit {MAX_MB} MB uncompressed).")
    for m in z.infolist():
        target = os.path.realpath(os.path.join(dest, m.filename))
        if not target.startswith(dest + os.sep):
            raise ValueError("Invalid zip contents.")
    z.extractall(dest)


def remove_path(p):
    if os.path.islink(p):
        os.unlink(p)
    elif os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)


def run_pipeline(uploaded, trial_name):
    tmp = tempfile.mkdtemp(dir=APP_DIR)
    session_dir = link_dir = None
    try:
        with zipfile.ZipFile(uploaded) as z:
            safe_extract(z, tmp)

        # One top-level folder -> that's the session folder (name = session ID).
        # Otherwise the extracted contents are the session (ID from the zip's name).
        entries = [e for e in os.listdir(tmp) if e != "__MACOSX" and not e.startswith(".")]
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
            root = os.path.join(tmp, entries[0])
            name = entries[0]
        else:
            root = tmp
            name = os.path.splitext(uploaded.name)[0]

        session_id = re.sub(r"^OpenCapData_", "", name)
        if not SESSION_ID.match(session_id):
            raise ValueError("Couldn't read a valid session ID from the folder name. "
                             "Upload the zip exactly as downloaded from OpenCap.")

        session_dir = os.path.join(APP_DIR, session_id)                   # dynamics reads this
        link_dir = os.path.join(APP_DIR, f"OpenCapData_{session_id}")     # gait analysis reads this
        for p in (link_dir, session_dir):   # clear leftovers from any crashed earlier run
            remove_path(p)

        shutil.move(root, session_dir)
        os.symlink(session_dir, link_dir)   # both folder names point at the same data

        kin = os.path.join(session_dir, "OpenSimData", "Kinematics", f"{trial_name}.mot")
        if not os.path.isfile(kin):
            raise ValueError(f"Trial '{trial_name}' has no kinematics file in this session.")

        print(f"peak memory before: {peak_mb():.0f} MB", flush=True)
        outputs = FullProcess(session_id, trial_name)
        print(f"peak memory after: {peak_mb():.0f} MB", flush=True)

        return dict(zip(RESULT_TITLES, outputs))
    finally:
        for p in (link_dir, session_dir):   # symlink first, then the real folder
            if p:
                remove_path(p)
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------- UI ----------------
st.title("OpenCap Gait Processor")
st.write("Upload a zipped OpenCap session folder. Files are deleted after processing.")

uploaded = st.file_uploader("Zipped OpenCap session folder", type=["zip"])

trial_name = None
if uploaded:
    try:
        with zipfile.ZipFile(uploaded) as z:
            trials = list_trials(z)
    except zipfile.BadZipFile:
        st.error("That doesn't look like a valid zip file.")
        uploaded, trials = None, []
    if uploaded:
        if trials:
            trial_name = st.selectbox("Trial to process", trials)
        else:
            trial_name = st.text_input("Trial name (couldn't detect trials automatically)")

if uploaded and trial_name and st.button("Process"):
    st.session_state.pop("results", None)
    if not SAFE_NAME.match(trial_name):
        st.error("Trial name may only contain letters, numbers, dots, dashes, and underscores.")
    else:
        try:
            with st.spinner("Waiting for processor..."):
                with get_lock():
                    with st.spinner("Processing... this takes about 15-20 minutes. "
                                    "Keep this tab open and don't change anything on the page."):
                        st.session_state["results"] = run_pipeline(uploaded, trial_name)
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error("Processing failed. Check that this is a valid, complete OpenCap session.")
            st.exception(e)

if "results" in st.session_state:
    st.success("Done!")
    for name, df in st.session_state["results"].items():
        st.subheader(name)
        st.dataframe(df, use_container_width=True)
        st.divider()