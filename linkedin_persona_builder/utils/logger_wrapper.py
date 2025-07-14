"""
Logger wrapper to handle keyword arguments in logging calls
"""
import logging
from typing import Any

class LoggerWrapper:
    """Wrapper to handle keyword arguments in logger calls"""
    
    def __init__(self, logger):
        self._logger = logger
    
    def info(self, msg, **kwargs):
        """Info with keyword argument support"""
        if kwargs:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            self._logger.info(f"{msg} | {extra_info}")
        else:
            self._logger.info(msg)
    
    def error(self, msg, **kwargs):
        """Error with keyword argument support"""
        if kwargs:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            self._logger.error(f"{msg} | {extra_info}")
        else:
            self._logger.error(msg)
    
    def warning(self, msg, **kwargs):
        """Warning with keyword argument support"""
        if kwargs:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            self._logger.warning(f"{msg} | {extra_info}")
        else:
            self._logger.warning(msg)
    
    def debug(self, msg, **kwargs):
        """Debug with keyword argument support"""
        if kwargs:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            self._logger.debug(f"{msg} | {extra_info}")
        else:
            self._logger.debug(msg)

def wrap_logger(logger_name: str = None):
    """Create a wrapped logger that handles keyword arguments"""
    if logger_name:
        base_logger = logging.getLogger(logger_name)
    else:
        base_logger = logging.getLogger()
    
    return LoggerWrapper(base_logger)
