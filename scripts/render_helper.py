"""Helper for rendering user-supplied templates. (e2e gate test file)"""
import subprocess


def run_user_command(user_input):
    # Deliberately unsafe pattern for the e2e gate test: shell=True with
    # user-controlled input (command injection).
    return subprocess.check_output(user_input, shell=True)


def render_expression(expr):
    # Deliberately unsafe pattern: eval of user-controlled input.
    return eval(expr)
