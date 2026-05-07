
import sys
from bazzcap.logging_utils import setup_logging, install_global_exception_handlers

setup_logging()
install_global_exception_handlers()

from bazzcap.app import BazzCapApp


def main():
    app = BazzCapApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
