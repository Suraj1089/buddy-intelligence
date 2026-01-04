
import json
import logging
import sys
from typing import Any


class StructuredAdapter(logging.LoggerAdapter):
    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        if isinstance(msg, dict):
            msg = json.dumps(msg)
        return msg, kwargs

def get_logger(name: str) -> StructuredAdapter:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return StructuredAdapter(logger, {})

logger = get_logger(__name__)
