import logging


def setup_logging(level: str) -> None:
    """Plain, single-line logs. We log method/path/status/duration and exception types only -
    never request bodies, Authorization headers, passwords or tokens."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our own request log line
