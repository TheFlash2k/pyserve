import logging
import sys

class Logger(object):

    """Logger factory for PyServe.

    Attributes:
        name: Name of the logger
        level: Level of the logger

    Methods:
        get_logger: Returns a logger object
        set_level: Changes the level on an existing logger

    Classes:
        Formatter: Logging Formatter that colors the level name
    """

    class Formatter(logging.Formatter):

        """Logging Formatter that colors the level name"""

        grey = "\x1b[38;20m"
        yellow = "\x1b[33;20m"
        blue = "\x1b[34;20m"
        red = "\x1b[31;20m"
        green = "\x1b[32;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"
        format = "%(asctime)s %(levelname)s %(message)s"

        FORMATS = {
            logging.DEBUG: f"[{green}{format.split()[1]}{reset}] {format.split()[2]}",
            logging.INFO: f"[{blue}{format.split()[1]}{reset}] {format.split()[2]}",
            logging.WARNING: f"[{yellow}{format.split()[1]}{reset}] {format.split()[2]}",
            logging.ERROR: f"[{red}{format.split()[1]}{reset}] {format.split()[2]}",
            logging.CRITICAL: f"[{bold_red}{format.split()[1]}{reset}] {format.split()[2]}",
        }

        def format(self, record: logging.LogRecord) -> str:
            """Format the log record.

            Args:
                record: Log record to be formatted

            Returns:
                Formatted log record
            """
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)

    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
        "quiet": logging.CRITICAL,
    }

    @staticmethod
    def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
        """Returns a logger object.

        Args:
            name: Name of the logger
            level: Level of the logger

        Returns:
            A logger object.
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(Logger.Formatter())
            logger.addHandler(handler)
        logger.propagate = False
        return logger

    @staticmethod
    def set_level(level) -> None:
        """Changes the level of the shared PyServe logger.

        Args:
            level: Either a logging constant or one of the names in LEVELS
        """
        if isinstance(level, str):
            level = Logger.LEVELS.get(level.strip().lower(), logging.INFO)
        logger.setLevel(level)

logger = Logger.get_logger("pyserve", level=logging.INFO)
