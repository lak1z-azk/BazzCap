#!/usr/bin/env python3

from bazzcap.app import BazzCapApp
import sys

def main():
    app = BazzCapApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()
