"""Throwaway file for validating trace diff-aware SAST on a PR. Safe to delete."""
import subprocess


def handle(user_input):
    # Command injection: tainted `user_input` flows into a shell=True call.
    return subprocess.run(user_input, shell=True, capture_output=True)
