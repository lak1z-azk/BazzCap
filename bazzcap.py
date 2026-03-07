#!/usr/bin/env python3
"""BazzCap launcher script."""

from bazzcap.app import BazzCapApp
import sys

def main():
    app = BazzCapApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()
