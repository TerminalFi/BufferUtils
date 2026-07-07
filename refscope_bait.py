import subprocess


def run_user_command(cmd):
    # e2e bait: shell injection pattern for the ref-scope validation
    return subprocess.run(cmd, shell=True, capture_output=True)


def load_config(blob):
    # e2e bait: eval on untrusted input
    return eval(blob)
