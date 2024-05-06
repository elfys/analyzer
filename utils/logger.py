import logging
import sys


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno <= logging.INFO


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    file_handler = logging.FileHandler("logfile.log")
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    stdout_handler.addFilter(InfoFilter())
    
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    
    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)
    logger.addHandler(file_handler)
    
    logger_plt = logging.getLogger("matplotlib")
    logger_plt.setLevel(logging.INFO)
    return logger
