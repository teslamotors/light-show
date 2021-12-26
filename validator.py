# Requires Python 3.7+
import dataclasses
import struct
import sys
import argparse
import datetime
from pathlib import Path

MEMORY_LIMIT = 681


class ValidationError(Exception):
    def __init__(self, message):
        super(ValidationError, self).__init__(f"VALIDATION ERROR: {message}")


@dataclasses.dataclass
class ValidationResults:
    frame_count: int
    step_time: int
    duration_s: int
    memory_usage: float
    command_count: int

def validate(file):
    file_name = Path(file.name).name
    if file_name != "lightshow.fseq":
        print(f"WARNING: FSEQ file should be renamed to 'lightshow.fseq' before playing in a Tesla.")

    """Calculates the memory usage of the provided .fseq file"""
    magic = file.read(4)
    start, minor, major = struct.unpack("<HBB", file.read(4))
    file.seek(10)
    channel_count, frame_count, step_time = struct.unpack("<IIB", file.read(9))
    file.seek(20)
    compression_type, = struct.unpack("<B", file.read(1))

    if (magic != b'PSEQ') or (start < 24) or (frame_count < 1) or (step_time < 15) or (minor != 0) or (major != 2):
        raise ValidationError("Unknown file format, expected FSEQ v2.0")
    if channel_count != 48:
        raise ValidationError(f"Expected 48 channels, got {channel_count}")
    if compression_type != 0:
        raise ValidationError("Expected file format to be V2 Uncompressed")
    duration_s = (frame_count * step_time / 1000)
    if duration_s > 5*60:
        raise ValidationError(f"Expected total duration to be less than 5 minutes, got {datetime.timedelta(seconds=duration_s)}")

    file.seek(start)

    prev_light = None
    prev_ramp = None
    prev_closure_1 = None
    prev_closure_2 = None
    count = 0

    for frame_i in range(frame_count):
        lights = file.read(30)
        closures = file.read(16)
        file.seek(2, 1)

        light_state = [(b > 127) for b in lights]
        ramp_state = [min((((255 - b) if (b > 127) else (b)) // 13 + 1) // 2, 3) for b in lights[:14]]
        closure_state = [((b // 32 + 1) // 2) for b in closures]

        if light_state != prev_light:
            prev_light = light_state
            count += 1
        if ramp_state != prev_ramp:
            prev_ramp = ramp_state
            count += 1
        if closure_state[:10] != prev_closure_1:
            prev_closure_1 = closure_state[:10]
            count += 1
        if closure_state[10:] != prev_closure_2:
            prev_closure_2 = closure_state[10:]
            count += 1

    memory_usage = count / MEMORY_LIMIT

    if memory_usage > 1:
        raise ValidationError(f"Sequence uses {count} commands. The maximum allowed is {MEMORY_LIMIT}.")

    return ValidationResults(frame_count, step_time, duration_s, memory_usage, count)


if __name__ == "__main__":
    # Expected usage: python3 validator.py lightshow.fseq
    parser = argparse.ArgumentParser(description="Validate .fseq file for Tesla Light Show use")
    parser.add_argument("file")
    args = parser.parse_args()

    with open(args.file, "rb") as file:
        try:
            results = validate(file)
        except ValidationError as e:
            print(e)
            sys.exit(1)

    print(f"Found {results.frame_count} frames, step time of {results.step_time} ms for a total duration of {datetime.timedelta(seconds=results.duration_s)}.")
    print(f"Used {results.memory_usage*100:.2f}% of the available memory")
