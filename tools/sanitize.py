#!/usr/bin/env python3
"""Rewrite result files so they hold no machine paths: the Eco root as
<eco>, the home directory as ~, temporary directories as <tmp>.

    sanitize.py FILE...
"""
import os
import re
import sys

ECO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.expanduser("~")


def clean(text):
    text = text.replace(ECO, "<eco>")
    text = text.replace(HOME, "~")
    text = re.sub(r"/tmp/[\w.-]+", "<tmp>", text)
    return text


def main():
    for path in sys.argv[1:]:
        with open(path) as f:
            text = f.read()
        new = clean(text)
        if new != text:
            with open(path, "w") as f:
                f.write(new)


if __name__ == "__main__":
    main()
