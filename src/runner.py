"""Task runner (e2e gate test #5 — expected BLOCKED)."""
import subprocess


def run_task(cmd):
    return subprocess.check_output(cmd, shell=True)  # command injection


def compute(expr):
    return eval(expr)  # code injection
