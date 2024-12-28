# Requires Python 3.7+
import dataclasses
import struct
import sys
import datetime

class ValidationError(Exception):
    pass

@dataclasses.dataclass
class ValidationResults:
    frame_count: int
    step_time: int
    duration_s: int

def validate(file):
    """Checks format and length of the provided .fseq file"""
    magic = file.read(4)
    start, minor, major = struct.unpack("<HBB", file.read(4))
    file.seek(10)
    channel_count, frame_count, step_time = struct.unpack("<IIB", file.read(9))
    file.seek(20)
    compression_type, = struct.unpack("<B", file.read(1))

    if (magic != b'PSEQ') or (start < 24) or (frame_count < 1) or (step_time < 15):
        raise ValidationError("Unknown file format, expected FSEQ v2.0")
    if channel_count != 48 and channel_count != 200:
        raise ValidationError(f"Expected 48 or 200 channels, got {channel_count}")
    if compression_type != 0:
        raise ValidationError("Expected file format to be V2 Uncompressed")
    duration_s = (frame_count * step_time / 1000)
    if duration_s > 4*60*60:
        raise ValidationError(f"Expected total duration to be less than 4 hours, got {datetime.timedelta(seconds=duration_s)}")
    if ((minor != 0) and (minor != 2)) or (major != 2):
        print("")
        print(f"WARNING: FSEQ version is {major}.{minor}. Only version 2.0 and 2.2 have been validated.")
        print(f"If the car fails to read this file, download an older version of XLights at https://github.com/smeighan/xLights/releases")
        print(f"Please report this message at https://github.com/teslamotors/light-show/issues")
        print("")
   
    return ValidationResults(frame_count, step_time, duration_s)

if __name__ == "__main__":
    # Expected usage: python3 validator.py lightshow.fseq

    # Check if a file argument is provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = input("Please enter the path by dragging and dropping the .fseq file: ")
        print("")
        file_path = file_path.strip('"') # Remove surrounding quotes if they exist
        
    with open(file_path, "rb") as file:
        try:
            results = validate(file)
        except ValidationError as e:
            print(e)
            input("Press Enter to exit...")
            sys.exit(1)

    print(f"Found {results.frame_count} frames, step time of {results.step_time} ms for a total duration of {datetime.timedelta(seconds=results.duration_s)}.")
    input("Press Enter to exit...")
