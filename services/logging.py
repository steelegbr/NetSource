from logging import getLogger, Logger


def get_logger(name: str) -> Logger:
    return getLogger(name)
