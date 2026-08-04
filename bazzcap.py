#!/usr/bin/env python3

import sys

# Re-exec entrypoint: the frozen bundle runs its own portal/trigger helpers by
# invoking itself, since it is the only interpreter guaranteed to have dbus and
# gi available.  This must run before Qt is imported — the helper is a plain
# D-Bus client and starting a QApplication in it would be wasteful and racy.
if "--bazzcap-run-helper" in sys.argv:
    _i = sys.argv.index("--bazzcap-run-helper")
    _helper, *_args = sys.argv[_i + 1:]
    sys.argv = [_helper] + _args
    import runpy
    runpy.run_path(_helper, run_name="__main__")
    sys.exit(0)

from bazzcap.logging_utils import setup_logging, install_global_exception_handlers

setup_logging()
install_global_exception_handlers()

from bazzcap.app import BazzCapApp

def main():
    app = BazzCapApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()
