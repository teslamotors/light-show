# Requires Python 3.7+
from __future__ import annotations
import dataclasses
import struct
import sys
import argparse
import datetime
from typing import BinaryIO, List, Tuple
from pathlib import Path

# Constants
MEMORY_LIMIT = 3500
MAGIC_BYTES = b'PSEQ'
MIN_START_OFFSET = 24
MIN_STEP_TIME = 15
MAX_DURATION_SECONDS = 5 * 60
VALID_CHANNEL_COUNTS = {48, 200}
SUPPORTED_VERSIONS = {(2, 0), (2, 2)}

@dataclasses.dataclass
class FileHeader:
    """Represents the header structure of an FSEQ file."""
    major_version: int
    minor_version: int
    start_offset: int
    channel_count: int
    frame_count: int
    step_time: int
    compression_type: int

    @classmethod
    def from_file(cls, file: BinaryIO) -> FileHeader:
        """Parse file header from binary file."""
        magic = file.read(4)
        if magic != MAGIC_BYTES:
            raise ValidationError(f"Invalid magic bytes: expected {MAGIC_BYTES}, got {magic}")
        
        start, minor, major = struct.unpack("<HBB", file.read(4))
        file.seek(10)
        channel_count, frame_count, step_time = struct.unpack("<IIB", file.read(9))
        file.seek(20)
        compression_type, = struct.unpack("<B", file.read(1))
        
        return cls(
            major_version=major,
            minor_version=minor,
            start_offset=start,
            channel_count=channel_count,
            frame_count=frame_count,
            step_time=step_time,
            compression_type=compression_type
        )

@dataclasses.dataclass
class Frame:
    """Represents a single frame of light show data."""
    light_state: List[bool]
    ramp_state: List[int]
    closure_state: List[int]

    @classmethod
    def from_bytes(cls, lights: bytes, closures: bytes) -> Frame:
        """Create a Frame instance from raw bytes."""
        light_state = [(b > 127) for b in lights]
        ramp_state = [min((((255 - b) if (b > 127) else b) // 13 + 1) // 2, 3) for b in lights[:14]]
        closure_state = [((b // 32 + 1) // 2) for b in closures]
        return cls(light_state, ramp_state, closure_state)

@dataclasses.dataclass
class ValidationResults:
    """Results of file validation."""
    frame_count: int
    step_time: int
    duration_s: int
    memory_usage: float

    def is_valid(self) -> bool:
        """Check if validation results indicate a valid file."""
        return self.memory_usage <= 1

    def format_results(self) -> str:
        """Format validation results as human-readable string."""
        return (
            f"Found {self.frame_count} frames, step time of {self.step_time} ms "
            f"for a total duration of {datetime.timedelta(seconds=self.duration_s)}.\n"
            f"Used {self.memory_usage*100:.2f}% of the available memory"
        )

class ValidationError(Exception):
    """Raised when file validation fails."""
    pass

def validate_header(header: FileHeader) -> None:
    """Validate file header values."""
    if header.start_offset < MIN_START_OFFSET:
        raise ValidationError(f"Start offset too small: {header.start_offset}")
    
    if header.frame_count < 1:
        raise ValidationError("Frame count must be positive")
        
    if header.step_time < MIN_STEP_TIME:
        raise ValidationError(f"Step time too small: {header.step_time}")
        
    if header.channel_count not in VALID_CHANNEL_COUNTS:
        raise ValidationError(f"Invalid channel count: {header.channel_count}")
        
    if header.compression_type != 0:
        raise ValidationError("Only uncompressed V2 format is supported")
        
    duration_s = (header.frame_count * header.step_time / 1000)
    if duration_s > MAX_DURATION_SECONDS:
        raise ValidationError(
            f"Duration exceeds limit: {datetime.timedelta(seconds=duration_s)} "
            f"(max: {datetime.timedelta(seconds=MAX_DURATION_SECONDS)})"
        )

def check_version_compatibility(header: FileHeader) -> None:
    """Check file version compatibility and print warnings if needed."""
    version = (header.major_version, header.minor_version)
    if version not in SUPPORTED_VERSIONS:
        print(
            f"\nWARNING: FSEQ version is {header.major_version}.{header.minor_version}. "
            "Only version 2.0 and 2.2 have been validated.\n"
            "If the car fails to read this file, download an older version of XLights "
            "at https://github.com/smeighan/xLights/releases\n"
            "Please report this message at https://github.com/teslamotors/light-show/issues\n"
        )

def validate(file: BinaryIO) -> ValidationResults:
    """Validate an FSEQ file and calculate memory usage."""
    header = FileHeader.from_file(file)
    validate_header(header)
    check_version_compatibility(header)
    
    file.seek(header.start_offset)
    state_changes = 0
    prev_frame = None
    
    for _ in range(header.frame_count):
        lights = file.read(30)
        closures = file.read(16)
        file.seek(header.channel_count - 46, 1)  # Skip remaining channels
        
        current_frame = Frame.from_bytes(lights, closures)
        
        if prev_frame is None or any([
            current_frame.light_state != prev_frame.light_state,
            current_frame.ramp_state != prev_frame.ramp_state,
            current_frame.closure_state[:10] != prev_frame.closure_state[:10],
            current_frame.closure_state[10:] != prev_frame.closure_state[10:]
        ]):
            state_changes += 1
        
        prev_frame = current_frame
    
    duration_s = (header.frame_count * header.step_time / 1000)
    return ValidationResults(
        frame_count=header.frame_count,
        step_time=header.step_time,
        duration_s=duration_s,
        memory_usage=state_changes / MEMORY_LIMIT
    )

def main() -> None:
    """Main entry point for the validator script."""
    parser = argparse.ArgumentParser(description="Validate .fseq file for Tesla Light Show use")
    parser.add_argument("file", type=Path, help="Path to the FSEQ file to validate")
    args = parser.parse_args()
    
    try:
        with open(args.file, "rb") as file:
            results = validate(file)
        print(results.format_results())
        sys.exit(0 if results.is_valid() else 1)
    except (ValidationError, IOError) as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
