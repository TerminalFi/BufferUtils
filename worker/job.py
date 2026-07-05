"""Job worker (e2e gate test #7 — expected BLOCKED + merge blocked)."""
import subprocess


def execute(cmd):
    return subprocess.check_output(cmd, shell=True)  # command injection


def calc(expr):
    return eval(expr)  # code injection
