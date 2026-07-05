"""Config loader with template support (e2e gate test #3)."""
import subprocess


def load_from_command(cmd):
    # Command injection on purpose — semgrep p/default flags this.
    return subprocess.check_output(cmd, shell=True)


def render(expr):
    # Code injection on purpose (eval of untrusted input).
    return eval(expr)
