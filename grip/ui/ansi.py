import re

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')


def strip_ansi(text):
    return ansi_escape.sub('', text)
