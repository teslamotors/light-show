# Requires Python 3.7+
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from datetime import timedelta
from logging import (
    ERROR,
    INFO,
    WARNING,
    Formatter,
    LogRecord,
    StreamHandler,
    getLogger,
)
from pathlib import Path
from typing import BinaryIO


MIN_HEADER_SIZE = 24
MIN_STEP_TIME_MS = 15
MIN_FRAME_COUNT = 1

SUPPORTED_CHANNELS = {48, 200}

MAX_DURATION_SECONDS = 4 * 60 * 60

SUPPORTED_VERSIONS = {
    (2, 0),
    (2, 2),
}

COMPRESSION_NONE = 0


COLOR_MODE = sys.stdout.isatty() and sys.platform != "win32"


class ColorFormatter(Formatter):
    COLOR_CODES = {
        INFO: "\033[32m",  # Green
        WARNING: "\033[33m",  # Yellow
        ERROR: "\033[31m",  # Red
    }
    RESET_CODE = "\033[0m"

    def format(self, record: LogRecord) -> str:
        message = super().format(record)

        if not COLOR_MODE:
            return message

        color_code = self.COLOR_CODES.get(record.levelno, "")
        return f"{color_code}{message}{self.RESET_CODE}"


logger = getLogger("fseq_validator")
logger.setLevel(INFO)
handler = StreamHandler()
formatter = ColorFormatter("{message}", style="{")
handler.setFormatter(formatter)
handler.setLevel(INFO)
logger.addHandler(handler)


class ValidationError(Exception):
    pass


@dataclass
class ValidationResults:
    frame_count: int
    step_time: int
    duration_s: float


def validate(stream: BinaryIO):
    """Checks format and length of the provided .fseq file

    Arguments
    ---------
    stream : BinaryIO
        Opened binary stream of the .fseq file to validate
    """
    magic = stream.read(4)

    if magic != b"PSEQ":
        raise ValidationError("Unknown file format, expected FSEQ v2.0")

    start, minor, major = struct.unpack("<HBB", stream.read(4))

    if start < MIN_HEADER_SIZE:
        raise ValidationError(
            "Expected header size to be at least {}, got {}".format(
                MIN_HEADER_SIZE,
                start,
            )
        )

    stream.seek(10)

    channel_count, frame_count, step_time = struct.unpack(
        "<IIB",
        stream.read(9),
    )

    if frame_count < MIN_FRAME_COUNT:
        raise ValidationError(
            "Expected at least {} frame, got {}".format(
                MIN_FRAME_COUNT,
                frame_count,
            )
        )

    if step_time < MIN_STEP_TIME_MS:
        raise ValidationError(
            "Expected step time to be at least {} ms, got {} ms".format(
                MIN_STEP_TIME_MS,
                step_time,
            )
        )

    if channel_count not in SUPPORTED_CHANNELS:
        raise ValidationError(
            "Expected channel count to be one of {}, got {}".format(
                SUPPORTED_CHANNELS,
                channel_count,
            )
        )

    stream.seek(20)
    (compression_type,) = struct.unpack("<B", stream.read(1))

    if compression_type != COMPRESSION_NONE:
        raise ValidationError("Expected file format to be V2 Uncompressed")

    duration_s = frame_count * step_time / 1000

    if duration_s > MAX_DURATION_SECONDS:
        raise ValidationError(
            "Expected duration to be at most {}, got {}".format(
                timedelta(seconds=MAX_DURATION_SECONDS),
                timedelta(seconds=duration_s),
            )
        )

    if (major, minor) not in SUPPORTED_VERSIONS:
        logger.warning(
            "WARNING: FSEQ version is %d.%d. Only versions %s are supported.",
            major,
            minor,
            ", ".join(f"{ma}.{mi}" for ma, mi in SUPPORTED_VERSIONS),
        )
        logger.warning(
            "If the car fails to read this file,"
            "download an older version of XLights at "
            "https://github.com/smeighan/xLights/releases"
        )
        logger.warning(
            "Please report this message at "
            "https://github.com/teslamotors/light-show/issues"
        )

    return ValidationResults(frame_count, step_time, duration_s)


if __name__ == "__main__":
    # Expected usage: python3 validator.py lightshow.fseq

    # Check if a file argument is provided

    parser = argparse.ArgumentParser(
        prog="Tesla Light Show Validator",
        description="Validate Tesla Light Show .fseq files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the .fseq file",
        type=Path,
    )
    args = parser.parse_args()
    path = args.file

    if path is None:

        if not sys.stdin.isatty():

            data = sys.stdin.read().strip()

        else:
            logger.warning("No file provided as an argument.")

            try:
                data = (
                    input(
                        "Enter the path to the .fseq file "
                        "(or drag and drop it here): ",
                    )
                    .strip('"')
                    .strip()
                )
            except EOFError:
                logger.error("No input provided.")
                sys.exit(1)

        if not data:
            logger.error("No file path provided.")
            sys.exit(1)

        path = Path(data)

    if not path.exists():
        logger.error("File not found: %s", path)
        sys.exit(1)

    if not path.is_file():
        logger.error("Not a valid file: %s", path)
        sys.exit(1)

    try:
        with path.open("rb") as f:
            results = validate(f)
    except ValidationError as e:
        logger.error("Validation failed: %s", e)
        sys.exit(1)
    else:
        logger.info(
            "Found %d frames, step time of %d ms for a total duration of %s.",
            results.frame_count,
            results.step_time,
            timedelta(seconds=results.duration_s),
        )
