"""Template engine helper (e2e gate test #2)."""
import subprocess


def run(user_cmd):
    # Unsafe on purpose (command injection) — semgrep p/default should flag.
    return subprocess.check_output(user_cmd, shell=True)


def evaluate(expr):
    # Unsafe on purpose (code injection via eval).
    return eval(expr)
