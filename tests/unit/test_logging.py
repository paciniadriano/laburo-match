import json
import logging
from datetime import UTC, datetime

import pytest

from src.core import clock
from src.core.logging import JsonFormatter, configure_logging


def _format(message: str, **extra: object) -> dict:
    record = logging.LogRecord("laburo.test", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))


def test_line_is_json_with_clock_time_and_extra_fields():
    with clock.freeze(datetime(2026, 11, 24, 10, 0, tzinfo=UTC)):
        line = _format("screened", run_id="r1", jobs=3)

    assert line["ts"] == "2026-11-24T10:00:00+00:00"
    assert line["level"] == "INFO"
    assert line["message"] == "screened"
    assert line["run_id"] == "r1"
    assert line["jobs"] == 3


def test_emails_are_masked_in_message_and_extra():
    line = _format("contact ana@example.org now", contact="bob@corp.io")

    assert "ana@example.org" not in json.dumps(line)
    assert "bob@corp.io" not in json.dumps(line)
    assert line["message"] == "contact [email] now"


def test_exception_detail_is_logged_server_side():
    try:
        {}["secret_table"]
    except KeyError:
        record = logging.LogRecord(
            "laburo.test", logging.ERROR, __file__, 1, "boom", None, __import__("sys").exc_info()
        )
    line = json.loads(JsonFormatter().format(record))

    assert "KeyError" in line["exception"]


def test_configure_logging_writes_json_to_stdout(capsys: pytest.CaptureFixture[str]):
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers, root.level
    try:
        configure_logging("INFO")
        logging.getLogger("laburo.test").info("hello")
        assert json.loads(capsys.readouterr().out)["message"] == "hello"
    finally:
        root.handlers, root.level = saved_handlers, saved_level
