"""Request handler (e2e gate test #6 — expected BLOCKED + merge blocked)."""
import subprocess


def handle(cmd):
    return subprocess.check_output(cmd, shell=True)  # command injection


def evaluate(expr):
    return eval(expr)  # code injection
