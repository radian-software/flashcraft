from datetime import datetime


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"flashcraft {ts} [{level}] {msg}")


def error(msg: str) -> None:
    log("error", msg)


def warn(msg: str) -> None:
    log("warn", msg)


def info(msg: str) -> None:
    log("info", msg)


def debug(msg: str) -> None:
    log("debug", msg)
