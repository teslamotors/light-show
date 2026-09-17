#!/usr/bin/env python3
"""Preview how a .fseq light show will actually behave on each Tesla vehicle.

The xLights project ships a single Model S / Cybertruck superset model, so the
sequencer preview always shows the Model S wiring: every channel is its own
light, and every light switches instantly.  Real vehicles differ.  On Model 3/Y
several xLights channels are OR'd onto one physical output, and several lights
that are boolean on Model S ramp instead.  A show that looks correct in the
preview can therefore look wrong on the car, which is what
https://github.com/teslamotors/light-show/issues/42 reports.

This tool reads a .fseq and reports the places where a given vehicle will not
reproduce what the preview showed, without needing the vehicle.

Usage:
    python3 tools/vehicle_preview.py lightshow.fseq
    python3 tools/vehicle_preview.py lightshow.fseq --vehicle model3
    python3 tools/vehicle_preview.py lightshow.fseq --json
    python3 tools/vehicle_preview.py lightshow.fseq --strict   # non-zero exit

Every behaviour encoded here is sourced from README.md; the section that backs
each rule is named in a `readme` note so the two stay reviewable side by side.

Requires Python 3.7+ and only the standard library, matching validator.py.
"""

import argparse
import dataclasses
import json
import struct
import sys
from typing import Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Channel layout
# --------------------------------------------------------------------------
# Channel numbers are 1-based and taken from the StartChannel values in
# xlights/tesla_xlights_show_folder.zip (xlights_rgbeffects.xml).  These are the
# names the show author sees in the xLights sequencer.

LIGHT = "light"
CLOSURE = "closure"

CHANNELS: Dict[int, Tuple[str, str]] = {
    1: ("Left Outer Main Beam", LIGHT),
    2: ("Right Outer Main Beam", LIGHT),
    3: ("Left Inner Main Beam", LIGHT),
    4: ("Right Inner Main Beam", LIGHT),
    5: ("Left Signature", LIGHT),
    6: ("Right Signature", LIGHT),
    7: ("Left Channel 4", LIGHT),
    8: ("Right Channel 4", LIGHT),
    9: ("Left Channel 5", LIGHT),
    10: ("Right Channel 5", LIGHT),
    11: ("Left Channel 6", LIGHT),
    12: ("Right Channel 6", LIGHT),
    13: ("Left Front Turn", LIGHT),
    14: ("Right Front Turn", LIGHT),
    15: ("Left Front Fog", LIGHT),
    16: ("Right Front Fog", LIGHT),
    17: ("Left Aux Park", LIGHT),
    18: ("Right Aux Park", LIGHT),
    19: ("Left Side Marker", LIGHT),
    20: ("Right Side Marker", LIGHT),
    21: ("Left Side Repeater", LIGHT),
    22: ("Right Side Repeater", LIGHT),
    23: ("Left Rear Turn", LIGHT),
    24: ("Right Rear Turn", LIGHT),
    25: ("Brake Lights", LIGHT),
    26: ("Left Tail", LIGHT),
    27: ("Right Tail", LIGHT),
    28: ("Reverse Lights", LIGHT),
    29: ("Rear Fog Lights", LIGHT),
    30: ("License Plate", LIGHT),
    31: ("Left Falcon Door", CLOSURE),
    32: ("Right Falcon Door", CLOSURE),
    33: ("Left Front Door", CLOSURE),
    34: ("Right Front Door", CLOSURE),
    35: ("Left Mirror", CLOSURE),
    36: ("Right Mirror", CLOSURE),
    37: ("Left Front Window", CLOSURE),
    38: ("Left Rear Window", CLOSURE),
    39: ("Right Front Window", CLOSURE),
    40: ("Right Rear Window", CLOSURE),
    41: ("Liftgate", CLOSURE),
    42: ("Left Front Door Handle", CLOSURE),
    43: ("Left Rear Door Handle", CLOSURE),
    44: ("Right Front Door Handle", CLOSURE),
    45: ("Right Rear Door Handle", CLOSURE),
    46: ("Charge Port", CLOSURE),
}


def channel_name(channel: int) -> str:
    entry = CHANNELS.get(channel)
    return entry[0] if entry else "Channel {}".format(channel)


# --------------------------------------------------------------------------
# Effect encoding
# --------------------------------------------------------------------------
# xLights stores an effect's brightness percentage; the vehicle reads the byte.
# The percentages below are the ones bound to the Tesla hotkeys in
# xlights_keybindings.xml, and are documented in README.md under "Ramping light
# channels" and "Definitions for closure movements".

# percent -> (action, ramp duration in ms)
RAMP_CODES: Dict[int, Tuple[str, int]] = {
    0: ("off", 0),
    10: ("off", 500),
    20: ("off", 1000),
    30: ("off", 2000),
    70: ("on", 500),
    80: ("on", 1000),
    90: ("on", 2000),
    100: ("on", 0),
}

# percent -> closure movement
CLOSURE_CODES: Dict[int, str] = {
    0: "Idle",
    25: "Open",
    50: "Dance",
    75: "Close",
    100: "Stop",
}


# README.md: "any brightness setting above 50% will set the light to ON and
# otherwise it will be OFF". 50% of a 255-wide byte is 127.5.
ON_THRESHOLD = 127

# A shared-output light has to sit solid for at least this long before it is
# worth telling the author that their blinking will not be visible.
MIN_SOLID_MS = 1000


def to_percent(value: int) -> int:
    """Convert a raw .fseq byte back to the xLights brightness percentage."""
    return int(round(value * 100.0 / 255.0))


# --------------------------------------------------------------------------
# Vehicle profiles
# --------------------------------------------------------------------------

BOOLEAN = "boolean"     # snaps between off and on
RAMPING = "ramping"     # honours the ramp codes above
FULL = "full"           # arbitrary brightness setpoint
ABSENT = "absent"       # no such light on this vehicle


@dataclasses.dataclass
class OrGroup:
    """Several xLights channels driving one physical output."""

    name: str
    channels: Tuple[int, ...]
    readme: str


@dataclasses.dataclass
class VehicleProfile:
    key: str
    label: str
    # Channel behaviour. Channels absent from this map behave as BOOLEAN.
    kinds: Dict[int, str]
    or_groups: Tuple[OrGroup, ...] = ()
    # follower channel -> channel whose effect defines the ramp duration
    ramp_leaders: Dict[int, int] = dataclasses.field(default_factory=dict)
    # channel -> the configuration in which the light is missing
    optional_hardware: Dict[int, str] = dataclasses.field(default_factory=dict)
    notes: Tuple[str, ...] = ()


def _merge(*maps: Dict[int, str]) -> Dict[int, str]:
    """Combine channel maps; later entries win. Keys are ints, so dict(**) is out."""
    merged: Dict[int, str] = {}
    for entry in maps:
        merged.update(entry)
    return merged


# Shared between Model S, X, 3 and Y: the headlight beams ramp, and the rear
# lighting is boolean.  README.md, "Light Channels with Brightness Control".
_BEAMS_RAMP = {1: RAMPING, 2: RAMPING, 3: RAMPING, 4: RAMPING}

# Side markers are only fitted in North America, and rear fog only outside it
# (plus North American Model X).  README.md, "Light channel mapping details".
_MARKER_HARDWARE = {
    19: "vehicles outside North America (side markers are a North America fitment)",
    20: "vehicles outside North America (side markers are a North America fitment)",
}

_MODEL_S = VehicleProfile(
    key="models",
    label="Model S (2021+)",
    kinds=_merge(_BEAMS_RAMP, {
        5: BOOLEAN, 6: BOOLEAN,          # Signature is boolean on S/X
        7: RAMPING, 8: RAMPING,          # Channels 4-6 ramp, individually driven
        9: RAMPING, 10: RAMPING,
        11: RAMPING, 12: RAMPING,
        13: BOOLEAN, 14: BOOLEAN,        # Front turn is boolean on S/X
        31: ABSENT, 32: ABSENT,          # no falcon doors
        33: ABSENT, 34: ABSENT,          # no powered front doors
    }),
    or_groups=(
        OrGroup("Left aux park + side marker", (17, 19), "Side Markers and Aux Park"),
        OrGroup("Right aux park + side marker", (18, 20), "Side Markers and Aux Park"),
    ),
    # Channel 4 is the ramp leader on every platform.
    ramp_leaders={9: 7, 11: 7, 10: 8, 12: 8},
    optional_hardware=_merge(_MARKER_HARDWARE, {
        29: "North America vehicles (rear fog is a non-North America fitment)",
    }),
)

_MODEL_X = dataclasses.replace(
    _MODEL_S,
    key="modelx",
    label="Model X (2021+)",
    kinds=_merge(_MODEL_S.kinds, {
        31: BOOLEAN, 32: BOOLEAN,        # falcon doors
        33: BOOLEAN, 34: BOOLEAN,        # powered front doors
        42: ABSENT, 43: ABSENT,          # no powered door handles
        44: ABSENT, 45: ABSENT,
    }),
    # Rear fog is fitted to Model X in North America too.
    optional_hardware=_merge(_MARKER_HARDWARE),
    notes=(
        "Aux park and side markers are assumed to share the Model S per-side "
        "pairing; README.md does not state Model X separately.",
    ),
)

_MODEL_3 = VehicleProfile(
    key="model3",
    label="Model 3",
    kinds=_merge(_BEAMS_RAMP, {
        5: RAMPING, 6: RAMPING,          # Signature ramps on 3/Y
        7: RAMPING, 8: RAMPING,          # Channels 4-6, but see or_groups
        9: RAMPING, 10: RAMPING,
        11: RAMPING, 12: RAMPING,
        13: RAMPING, 14: RAMPING,        # Front turn ramps on 3/Y
        31: ABSENT, 32: ABSENT,
        33: ABSENT, 34: ABSENT,
        42: ABSENT, 43: ABSENT,
        44: ABSENT, 45: ABSENT,
    }),
    or_groups=(
        OrGroup("Left Channels 4-6", (7, 9, 11), "Ramping Channels 4-6"),
        OrGroup("Right Channels 4-6", (8, 10, 12), "Ramping Channels 4-6"),
        OrGroup(
            "Aux park + side markers (all four)",
            (17, 18, 19, 20),
            "Side Markers and Aux Park",
        ),
    ),
    ramp_leaders={9: 7, 11: 7, 10: 8, 12: 8},
    optional_hardware=_merge(_MARKER_HARDWARE, {
        15: "Model 3 Standard Range + (no front fog fitted)",
        16: "Model 3 Standard Range + (no front fog fitted)",
        17: "Model 3 Standard Range + (no aux park fitted)",
        18: "Model 3 Standard Range + (no aux park fitted)",
        29: "North America vehicles (rear fog is a non-North America fitment)",
        41: "vehicles without a power liftgate",
    }),
    notes=(
        "On Model 3 built before October 2020 the left tail, right tail and "
        "license plate lights operate together, and the License Plate channel "
        "has no effect at all.",
    ),
)

_MODEL_Y = dataclasses.replace(
    _MODEL_3,
    key="modely",
    label="Model Y",
    # Front fog, aux park and a power liftgate are fitted across the Model Y
    # range, so only the region-dependent lights stay optional.
    optional_hardware=_merge(_MARKER_HARDWARE, {
        29: "North America vehicles (rear fog is a non-North America fitment)",
    }),
    notes=(),
)

_CYBERTRUCK = VehicleProfile(
    key="cybertruck",
    label="Cybertruck",
    kinds=_merge(_BEAMS_RAMP, {
        5: ABSENT, 6: ABSENT,            # no signature
        7: ABSENT, 8: ABSENT,            # no channels 4-6
        9: ABSENT, 10: ABSENT,
        11: ABSENT, 12: ABSENT,
        13: RAMPING, 14: RAMPING,        # front turn ramps
        19: RAMPING, 20: RAMPING,        # front side markers ramp
        23: FULL, 24: FULL,              # rear turn
        25: FULL,                        # brake
        31: ABSENT, 32: ABSENT,
        33: ABSENT, 34: ABSENT,
        42: ABSENT, 43: ABSENT,
        44: ABSENT, 45: ABSENT,
    }),
    notes=(
        "Channel 41 drives the powered frunk rather than a liftgate.",
        "Left/Right Tail drive the reverse lights, and Left/Right Side "
        "Repeater drive the rear side markers.",
    ),
)

VEHICLES: Dict[str, VehicleProfile] = {
    p.key: p for p in (_MODEL_S, _MODEL_X, _MODEL_3, _MODEL_Y, _CYBERTRUCK)
}


def kind_of(profile: VehicleProfile, channel: int) -> str:
    return profile.kinds.get(channel, BOOLEAN)


# --------------------------------------------------------------------------
# .fseq reading
# --------------------------------------------------------------------------


class ShowError(Exception):
    pass


@dataclasses.dataclass
class Show:
    channel_count: int
    frame_count: int
    step_time_ms: int
    data: bytes

    @property
    def duration_ms(self) -> int:
        return self.frame_count * self.step_time_ms

    def series(self, channel: int) -> bytes:
        """All frames for one 1-based channel, as raw bytes."""
        return self.data[channel - 1::self.channel_count]


def read_fseq(path: str) -> Show:
    """Parse a V2 uncompressed .fseq, the format the vehicle accepts."""
    with open(path, "rb") as handle:
        header = handle.read(24)
        if len(header) < 24 or header[:4] != b"PSEQ":
            raise ShowError("Unknown file format, expected FSEQ v2.0")
        offset, = struct.unpack("<H", header[4:6])
        channel_count, frame_count, step_time = struct.unpack("<IIB", header[10:19])
        compression, = struct.unpack("<B", header[20:21])
        if compression != 0:
            raise ShowError("Expected file format to be V2 Uncompressed")
        if channel_count not in (48, 200):
            raise ShowError(
                "Expected 48 or 200 channels, got {}".format(channel_count))
        if frame_count < 1 or step_time < 15:
            raise ShowError("Unknown file format, expected FSEQ v2.0")
        handle.seek(offset)
        data = handle.read(channel_count * frame_count)
    if len(data) < channel_count * frame_count:
        raise ShowError(
            "File is truncated: expected {} bytes of frame data, got {}".format(
                channel_count * frame_count, len(data)))
    return Show(channel_count, frame_count, step_time, data)


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

ERROR = "error"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclasses.dataclass
class Finding:
    severity: str
    code: str
    summary: str
    detail: str
    channels: Tuple[int, ...] = ()
    first_at_ms: Optional[int] = None
    occurrences: int = 1

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "summary": self.summary,
            "detail": self.detail,
            "channels": [
                {"channel": c, "name": channel_name(c)} for c in self.channels
            ],
            "first_at_ms": self.first_at_ms,
            "occurrences": self.occurrences,
        }


@dataclasses.dataclass
class Run:
    """A stretch of frames holding one constant value."""

    value: int
    start_frame: int
    frames: int

    @property
    def percent(self) -> int:
        return to_percent(self.value)


def runs_of(series: Sequence[int]) -> List[Run]:
    out: List[Run] = []
    if not series:
        return out
    current = Run(series[0], 0, 1)
    for index in range(1, len(series)):
        value = series[index]
        if value == current.value:
            current.frames += 1
        else:
            out.append(current)
            current = Run(value, index, 1)
    out.append(current)
    return out


def _ms(frames: int, step_time_ms: int) -> int:
    return frames * step_time_ms


def _timestamp(frame: int, step_time_ms: int) -> int:
    return frame * step_time_ms


def _check_ramp_reachability(
    show: Show, profile: VehicleProfile, findings: List[Finding]
) -> None:
    """Ramping lights need an effect longer than the ramp to reach full output.

    On Model S the front turn signals and signature lights are boolean, so a
    two-frame effect reads as a crisp flash in the xLights preview.  On Model 3
    the same channels ramp, and that two-frame effect only gets a few percent
    of the way to full brightness - which is why the flash at the start of the
    show in issue #42 was barely visible on the car.
    """
    for channel in sorted(CHANNELS):
        if CHANNELS[channel][1] != LIGHT:
            continue
        if kind_of(profile, channel) != RAMPING:
            continue
        # The sequencer preview always models a Model S. A channel that is
        # boolean there but ramping here is a difference the author cannot see.
        preview_is_instant = kind_of(_MODEL_S, channel) == BOOLEAN

        short: List[Tuple[Run, str, int, int]] = []
        for run in runs_of(show.series(channel)):
            code = RAMP_CODES.get(run.percent)
            if code is None:
                continue
            action, ramp_ms = code
            if ramp_ms == 0:
                continue  # instant effects have nothing to truncate
            held_ms = _ms(run.frames, show.step_time_ms)
            if held_ms < ramp_ms + 50:
                short.append((run, action, ramp_ms, held_ms))
        if not short:
            continue

        # Report against the effect that gets furthest from its setpoint.
        run, action, ramp_ms, held_ms = min(short, key=lambda s: s[3] / s[2])
        reach = int(round(100.0 * held_ms / ramp_ms))
        # Only an effect that dies well short of its setpoint looks wrong; one
        # that gets most of the way there is a rounding detail, not a defect.
        if reach < 50:
            severity = ERROR if preview_is_instant else WARNING
        else:
            severity = INFO

        if preview_is_instant:
            preview_note = (
                "{name} is boolean on Model S, so the preview renders these "
                "effects as an instant switch. On {label} the same effect "
                "ramps instead.".format(
                    name=channel_name(channel), label=profile.label)
            )
        else:
            preview_note = (
                "{name} ramps on {label}, and these effects end before the "
                "ramp they ask for has finished.".format(
                    name=channel_name(channel), label=profile.label)
            )

        findings.append(Finding(
            severity=severity,
            code="ramp-too-short",
            summary="{name}: {count} ramping effect(s) end before the ramp "
                    "completes on {label}".format(
                        name=channel_name(channel), count=len(short),
                        label=profile.label),
            detail=(
                "{preview} The shortest is a 'turn {action}; {ramp} ms' effect "
                "held for only {held} ms, so the light gets about {reach}% of "
                "the way to its setpoint before the effect ends. Hold the "
                "effect for at least {need} ms to reach the setpoint, or use "
                "an instant effect (0% or 100%) so it looks the same on every "
                "vehicle. See README.md, \"Ramping light channels\"."
            ).format(
                preview=preview_note,
                action=action,
                ramp=ramp_ms,
                held=held_ms,
                reach=reach,
                need=ramp_ms + 50,
            ),
            channels=(channel,),
            first_at_ms=_timestamp(run.start_frame, show.step_time_ms),
            occurrences=len(short),
        ))


def _or_union(show: Show, channels: Sequence[int]) -> List[int]:
    """Per-frame maximum across the channels sharing one physical output."""
    serieses = [show.series(c) for c in channels]
    if len(serieses) == 1:
        return list(serieses[0])
    return [max(values) for values in zip(*serieses)]


def _longest_on_span(union: Sequence[int]) -> Tuple[int, int]:
    """Length and start frame of the longest stretch where the output is lit."""
    longest = longest_start = 0
    current = start = 0
    for frame, value in enumerate(union):
        if value > ON_THRESHOLD:
            if current == 0:
                start = frame
            current += 1
            if current > longest:
                longest, longest_start = current, start
        else:
            current = 0
    return longest, longest_start


def _check_or_groups(
    show: Show, profile: VehicleProfile, findings: List[Finding]
) -> None:
    """Channels wired to one output cannot show the independent preview.

    Two separate problems fall out of this. The channels may be driven with
    different patterns, in which case the preview shows separate lights where
    the car has one; and the OR'd result may never go off, in which case a
    sequence that flashes in the preview sits solid on the car.
    """
    for group in profile.or_groups:
        members = [c for c in group.channels if c <= show.channel_count]
        if len(members) < 2:
            continue
        serieses = {c: show.series(c) for c in members}
        used = [c for c in members if any(serieses[c])]
        if not used:
            continue  # group unused by this show

        # 1. Do the members disagree? Compare on/off state frame by frame.
        # Only meaningful once the show drives more than one of them: a group
        # whose other channels are empty has nothing to collapse together.
        disagreements = 0
        first_disagreement = None
        for frame, values in enumerate(zip(*(serieses[c] for c in members))):
            on = [v > ON_THRESHOLD for v in values]
            if any(on) and not all(on):
                disagreements += 1
                if first_disagreement is None:
                    first_disagreement = frame
        if disagreements and len(used) > 1:
            findings.append(Finding(
                severity=WARNING,
                code="or-group-collapse",
                summary="{} share one output on {}, but this show drives "
                        "them separately".format(group.name, profile.label),
                detail=(
                    "The sequencer animates these {count} channels as {count} "
                    "separate lights. On {label} they are wired to one output, "
                    "so for {frames} frames ({ms} ms) the preview shows only "
                    "part of the group lit while the car lights the whole "
                    "shared lamp. Whichever of these channels you sequence, "
                    "the light appears in the same place on the car. See "
                    "README.md, \"{readme}\"."
                ).format(
                    count=len(members),
                    label=profile.label,
                    frames=disagreements,
                    ms=_ms(disagreements, show.step_time_ms),
                    readme=group.readme,
                ),
                channels=tuple(members),
                first_at_ms=_timestamp(first_disagreement, show.step_time_ms),
                occurrences=disagreements,
            ))

        # 2. Does the OR'd output ever get a chance to go off?
        # A group only glows unexpectedly when *every* member has some off time
        # inside the span yet their union has none - the case README.md warns
        # about with its "ord_channel_not_ok" example. If any member is simply
        # held on across the span then the solid output is what was asked for.
        union = _or_union(show, members)
        longest, longest_start = _longest_on_span(union)
        solid_ms = _ms(longest, show.step_time_ms)
        if solid_ms < MIN_SOLID_MS:
            continue
        span = slice(longest_start, longest_start + longest)
        states = [[v > ON_THRESHOLD for v in serieses[c][span]] for c in members]
        every_member_rests = all(not all(state) for state in states)
        someone_blinks = any(any(state) and not all(state) for state in states)
        if not (every_member_rests and someone_blinks):
            continue
        findings.append(Finding(
            severity=ERROR,
            code="or-group-never-off",
            summary="{} stays lit for {} ms on {} even though every channel "
                    "in it goes off".format(
                        group.name, solid_ms, profile.label),
            detail=(
                "These channels share one output on {label}, so the lamp is on "
                "whenever any of them is on. Each channel does go off during "
                "this stretch, but never at the same time as the others, so "
                "the blinking visible in the preview becomes a single {ms} ms "
                "glow on the car. Leave a gap that is blank on every channel "
                "in the group to make the light actually flash. See README.md, "
                "\"Light channel mapping recommendations\"."
            ).format(label=profile.label, ms=solid_ms),
            channels=tuple(members),
            first_at_ms=_timestamp(longest_start, show.step_time_ms),
            occurrences=1,
        ))


def _check_ramp_leaders(
    show: Show, profile: VehicleProfile, findings: List[Finding]
) -> None:
    """Channels 5 and 6 take their ramp duration from Channel 4.

    If Channel 4 has no effect at the moment Channel 5 or 6 starts ramping, the
    duration is whatever Channel 4 last defined, which is rarely what the
    author saw in the preview.
    """
    for follower, leader in sorted(profile.ramp_leaders.items()):
        if max(follower, leader) > show.channel_count:
            continue
        follower_series = show.series(follower)
        leader_series = show.series(leader)
        offenders = 0
        first = None
        for run in runs_of(follower_series):
            code = RAMP_CODES.get(run.percent)
            if code is None or code[1] == 0:
                continue  # instant effects do not need a duration
            if leader_series[run.start_frame] == 0:
                offenders += 1
                if first is None:
                    first = run.start_frame
        if offenders:
            findings.append(Finding(
                severity=WARNING,
                code="ramp-leader-missing",
                summary="{} ramps {} time(s) while {} has no effect to define "
                        "the duration".format(
                            channel_name(follower), offenders,
                            channel_name(leader)),
                detail=(
                    "On every vehicle the ramp duration for Channels 4-6 comes "
                    "from the Channel 4 effect, never from Channel 5 or 6. With "
                    "{leader} empty, these ramps run for whatever duration "
                    "{leader} last specified. Place a matching ramping effect "
                    "on {leader} - a 'turn off' ramp works even when you do not "
                    "want {leader} lit. See README.md, \"Ramping Channels 4-6\"."
                ).format(leader=channel_name(leader)),
                channels=(follower, leader),
                first_at_ms=_timestamp(first, show.step_time_ms),
                occurrences=offenders,
            ))


def _check_absent_channels(
    show: Show, profile: VehicleProfile, findings: List[Finding]
) -> None:
    """Channels the vehicle has no light for, or only has in some builds."""
    for channel in sorted(CHANNELS):
        if channel > show.channel_count:
            continue
        series = show.series(channel)
        if not any(series):
            continue
        first_on = next(i for i, v in enumerate(series) if v)
        if kind_of(profile, channel) == ABSENT:
            findings.append(Finding(
                severity=INFO,
                code="channel-not-present",
                summary="{} is not fitted to {}".format(
                    channel_name(channel), profile.label),
                detail=(
                    "This show drives the channel, but {label} has no such "
                    "light or closure and no other output is substituted for "
                    "it. The commands are ignored on this vehicle."
                ).format(label=profile.label),
                channels=(channel,),
                first_at_ms=_timestamp(first_on, show.step_time_ms),
            ))
        elif channel in profile.optional_hardware:
            findings.append(Finding(
                severity=INFO,
                code="channel-optional-hardware",
                summary="{} is missing on some {} builds".format(
                    channel_name(channel), profile.label),
                detail=(
                    "This channel does nothing on {missing}. Avoid relying on "
                    "it for beats that need to land on every car."
                ).format(missing=profile.optional_hardware[channel]),
                channels=(channel,),
                first_at_ms=_timestamp(first_on, show.step_time_ms),
            ))


def _check_boolean_ramps(
    show: Show, profile: VehicleProfile, findings: List[Finding]
) -> None:
    """Ramp codes placed on channels that cannot ramp on this vehicle."""
    for channel in sorted(CHANNELS):
        if channel > show.channel_count or CHANNELS[channel][1] != LIGHT:
            continue
        if kind_of(profile, channel) != BOOLEAN:
            continue
        ramped = 0
        first = None
        for run in runs_of(show.series(channel)):
            code = RAMP_CODES.get(run.percent)
            if code is not None and code[1] != 0:
                ramped += 1
                if first is None:
                    first = run.start_frame
        if ramped:
            findings.append(Finding(
                severity=INFO,
                code="ramp-ignored",
                summary="{} cannot ramp on {}; {} ramping effect(s) snap "
                        "instead".format(
                            channel_name(channel), profile.label, ramped),
                detail=(
                    "Brightness above 50% switches the light fully on and "
                    "anything below switches it off, so these effects look "
                    "instant here even though they ramp on other vehicles."
                ),
                channels=(channel,),
                first_at_ms=_timestamp(first, show.step_time_ms),
                occurrences=ramped,
            ))


def analyze(show: Show, profile: VehicleProfile) -> List[Finding]:
    """Return everything about this show that will surprise the author."""
    findings: List[Finding] = []
    _check_or_groups(show, profile, findings)
    _check_ramp_reachability(show, profile, findings)
    _check_ramp_leaders(show, profile, findings)
    _check_boolean_ramps(show, profile, findings)
    _check_absent_channels(show, profile, findings)
    findings.sort(key=lambda f: (
        _SEVERITY_ORDER[f.severity],
        f.first_at_ms if f.first_at_ms is not None else 0,
    ))
    return findings


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def _format_time(ms: Optional[int]) -> str:
    if ms is None:
        return "-"
    minutes, rest = divmod(ms, 60000)
    seconds, millis = divmod(rest, 1000)
    return "{:d}:{:02d}.{:03d}".format(minutes, seconds, millis)


def _wrap(text: str, width: int, indent: str) -> str:
    words = text.split()
    lines: List[str] = []
    current = indent
    for word in words:
        if len(current) + len(word) + 1 > width and current.strip():
            lines.append(current.rstrip())
            current = indent
        current += word + " "
    if current.strip():
        lines.append(current.rstrip())
    return "\n".join(lines)


_MARKERS = {ERROR: "ERROR  ", WARNING: "WARNING", INFO: "INFO   "}


def render_report(show: Show, results: Dict[str, List[Finding]], verbose: bool) -> str:
    out: List[str] = []
    out.append("{} frames, {} ms per frame, total duration {}.".format(
        show.frame_count, show.step_time_ms, _format_time(show.duration_ms)))
    out.append("")
    for key, findings in results.items():
        profile = VEHICLES[key]
        errors = sum(1 for f in findings if f.severity == ERROR)
        warnings = sum(1 for f in findings if f.severity == WARNING)
        infos = len(findings) - errors - warnings
        out.append("=" * 72)
        out.append("{}  -  {} error(s), {} warning(s), {} note(s)".format(
            profile.label, errors, warnings, infos))
        out.append("=" * 72)
        if not findings:
            out.append("  This show renders the same way the xLights preview "
                       "shows it.")
        for finding in findings:
            if finding.severity == INFO and not verbose:
                continue
            out.append("")
            out.append("  [{}] {} at {}".format(
                _MARKERS[finding.severity], finding.code,
                _format_time(finding.first_at_ms)))
            out.append(_wrap(finding.summary, 76, "    "))
            out.append(_wrap(finding.detail, 76, "      "))
            if finding.channels:
                out.append("      channels: " + ", ".join(
                    "{} ({})".format(channel_name(c), c) for c in finding.channels))
        if infos and not verbose:
            out.append("")
            out.append("  {} vehicle-configuration note(s) hidden; re-run with "
                       "-v to see them.".format(infos))
        for note in profile.notes:
            out.append("")
            out.append(_wrap("Note: " + note, 76, "  "))
        out.append("")
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview how a .fseq light show behaves on each Tesla "
                    "vehicle, and flag where it will differ from the xLights "
                    "Model S preview.")
    parser.add_argument("fseq", nargs="?", help="path to the .fseq show file")
    parser.add_argument(
        "--vehicle", action="append", choices=sorted(VEHICLES),
        help="limit the report to one vehicle (repeatable; default: all)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON instead of text")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="include vehicle-configuration notes")
    parser.add_argument(
        "--strict", action="store_true",
        help="exit non-zero if any error or warning is reported")
    args = parser.parse_args(argv)

    path = args.fseq
    if not path:
        path = input(
            "Please enter the path by dragging and dropping the .fseq file: ")
        print("")
        path = path.strip('"').strip("'").strip(" ")

    try:
        show = read_fseq(path)
    except (ShowError, OSError) as error:
        print(error, file=sys.stderr)
        return 2

    keys = args.vehicle or sorted(VEHICLES)
    results = {key: analyze(show, VEHICLES[key]) for key in keys}

    if args.json:
        print(json.dumps({
            "file": path,
            "frame_count": show.frame_count,
            "step_time_ms": show.step_time_ms,
            "duration_ms": show.duration_ms,
            "vehicles": {
                key: {
                    "label": VEHICLES[key].label,
                    "findings": [f.as_dict() for f in findings],
                }
                for key, findings in results.items()
            },
        }, indent=2))
    else:
        print(render_report(show, results, args.verbose))

    if args.strict and any(
        f.severity in (ERROR, WARNING)
        for findings in results.values() for f in findings
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
