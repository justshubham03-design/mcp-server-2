import logging
import re
import sys

def get_sanitized_logger(name: str) -> logging.Logger:
    """Returns a logger configured to write to stderr (preserving stdio stdout for JSON-RPC) with credential sanitization."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def sanitize_log_message(msg: str) -> str:
    """Masks tokens, secrets, and authorization headers from logs."""
    msg = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', r'\1[REDACTED_TOKEN]', msg)
    msg = re.sub(r'(client_secret=)[A-Za-z0-9_\-\.]+', r'\1[REDACTED_SECRET]', msg)
    msg = re.sub(r'(refresh_token=)[A-Za-z0-9_\-\.]+', r'\1[REDACTED_REFRESH_TOKEN]', msg)
    return msg
