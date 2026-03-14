import logging
from typing import Any, Dict

import orjson

_LOGGING_CONFIGURED = False


def configure_logging(level: str) -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO), format="%(message)s"
    )
    _LOGGING_CONFIGURED = True


def build_log_payload(event: str, **fields: Any) -> Dict[str, Any]:
    payload = {"event": event}
    payload.update(fields)
    return payload


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = build_log_payload(event, **fields)
    logger.log(level, orjson.dumps(payload, option=orjson.OPT_SORT_KEYS).decode())
