#!/usr/bin/env python3
"""Regenerate the inlined _PORTAL_HELPER_SOURCE copy in bazzcap/capture.py.

capture.py carries a verbatim copy of _portal_helper.py so that a build which
drops the bundled data file still has a working Wayland screenshot path.  Run
this after editing _portal_helper.py.

  python3 scripts/sync_embedded_helper.py          # rewrite the inlined copy
  python3 scripts/sync_embedded_helper.py --check  # exit 1 if out of sync
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "bazzcap", "_portal_helper.py")
CAPTURE = os.path.join(ROOT, "bazzcap", "capture.py")

MARKER = "_PORTAL_HELPER_SOURCE = ("


def render(src: str) -> str:
    lines = [MARKER]
    for line in src.splitlines(keepends=True):
        lines.append("    " + repr(line))
    lines.append(")")
    return "\n".join(lines) + "\n"


def main() -> int:
    check = "--check" in sys.argv
    src = open(HELPER).read()
    capture = open(CAPTURE).read()

    start = capture.find(MARKER)
    if start == -1:
        print("ERROR: _PORTAL_HELPER_SOURCE block not found in capture.py",
              file=sys.stderr)
        return 1

    desired = render(src)
    current = capture[start:]

    if current == desired:
        if check:
            print("embedded portal helper is in sync")
        return 0

    if check:
        print("ERROR: embedded portal helper is out of sync with "
              "_portal_helper.py.\nRun: python3 scripts/sync_embedded_helper.py",
              file=sys.stderr)
        return 1

    open(CAPTURE, "w").write(capture[:start] + desired)
    print("updated embedded portal helper in capture.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
