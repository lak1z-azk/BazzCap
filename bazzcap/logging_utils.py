import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

_LOG_FILE_HANDLE = None
_LOG_FILE_PATH = None


def _config_dir() -> str:
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/bazzcap")
    return os.path.expanduser("~/.config/bazzcap")


def get_log_file_path() -> str:
    return os.path.join(_config_dir(), "bazzcap.log")


def setup_logging() -> str:
    global _LOG_FILE_HANDLE, _LOG_FILE_PATH

    if _LOG_FILE_PATH:
        return _LOG_FILE_PATH

    log_path = get_log_file_path()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    has_file_handler = False
    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", "") == log_path:
            has_file_handler = True
            break

    if not has_file_handler:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(file_handler)

    try:
        import faulthandler

        _LOG_FILE_HANDLE = open(log_path, "a", encoding="utf-8")
        faulthandler.enable(_LOG_FILE_HANDLE)
    except Exception:
        pass

    _LOG_FILE_PATH = log_path
    logging.getLogger(__name__).info("Crash logging initialized at %s", log_path)
    return log_path


def install_global_exception_handlers() -> None:
    logger = logging.getLogger("bazzcap.crash")

    def _log_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _log_uncaught

    if hasattr(threading, "excepthook"):
        def _thread_excepthook(args):
            _log_uncaught(args.exc_type, args.exc_value, args.exc_traceback)

        threading.excepthook = _thread_excepthook

    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

        def _qt_message_handler(msg_type, _context, message):
            if msg_type == QtMsgType.QtDebugMsg:
                level = logging.DEBUG
            elif msg_type == QtMsgType.QtInfoMsg:
                level = logging.INFO
            elif msg_type == QtMsgType.QtWarningMsg:
                level = logging.WARNING
            elif msg_type == QtMsgType.QtCriticalMsg:
                level = logging.ERROR
            else:
                level = logging.CRITICAL
            logging.getLogger("bazzcap.qt").log(level, message)

        qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass
