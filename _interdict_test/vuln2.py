"""Throwaway file to validate trace diff-aware SAST on a fresh PR. Delete after."""
import subprocess


def run(user_input):
    return subprocess.run(user_input, shell=True, capture_output=True)  # shell injection
