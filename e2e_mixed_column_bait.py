import subprocess

def run_user_expr(expr):
    return eval(expr)  # noqa

def run_shell(cmd):
    return subprocess.run(cmd, shell=True)
