"""Execution helper (e2e gate test #4 — expected BLOCKED)."""
import subprocess


def shell(cmd):
    return subprocess.check_output(cmd, shell=True)  # command injection


def dyn(expr):
    return eval(expr)  # code injection
