#!/usr/bin/env python3
"""Maintain the positional "layer" model groups in the xLights show folder.

The show folder is distributed as a binary .zip, which makes review and
regression-checking of its contents impossible from a diff alone. This tool
closes that gap:

  fingerprint  Record every model's channel assignment in xlights/channel_map.json.
  apply        Write the groups described by xlights/layer_groups.json into the
               show folder zip. Idempotent.
  verify       Assert the zip matches both files. Run this in CI.

Only <modelGroups> and <views> are ever touched. Model groups are a sequencer
construct that reference existing models by name and own no channels, so they
cannot move a channel -- and `verify` proves it by re-checking the fingerprint.

Requires Python 3.7+. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path
from xml.sax.saxutils import quoteattr

REPO_ROOT = Path(__file__).resolve().parent.parent
SHOW_ZIP = REPO_ROOT / "xlights" / "tesla_xlights_show_folder.zip"
SPEC_PATH = REPO_ROOT / "xlights" / "layer_groups.json"
FINGERPRINT_PATH = REPO_ROOT / "xlights" / "channel_map.json"

RGBEFFECTS_ENTRY = "tesla_xlights_show_folder/xlights_rgbeffects.xml"

# Attributes that decide which physical channel a model drives. If any of these
# change for an existing model, previously exported .fseq files stop lining up
# with the sequence that produced them.
CHANNEL_ATTRS = ("DisplayAs", "StringType", "StartChannel", "parm1", "parm2", "parm3")

# Cybertruck preview models deliberately duplicate Model S channels so both
# vehicles can be shown in the 3D layout. They are excluded from every shipped
# group; including one would drive the same channel from two timeline rows.
# Which models these are is declared in layer_groups.json, because not all of
# them follow the "CT " naming convention.

INDENT = "    "


class CheckError(Exception):
    """A verification step failed."""


# --------------------------------------------------------------------------
# zip / xml plumbing
# --------------------------------------------------------------------------


def read_rgbeffects(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(RGBEFFECTS_ENTRY).decode("utf-8")


def _dos_datetime(date_time) -> tuple:
    year, month, day, hour, minute, second = date_time
    return (
        (hour << 11) | (minute << 5) | (second // 2),
        ((year - 1980) << 9) | (month << 5) | day,
    )


def write_rgbeffects(zip_path: Path, new_text: str) -> None:
    """Rewrite the zip with a new rgbeffects.xml, leaving every other entry alone.

    Untouched entries are copied as raw compressed streams rather than being
    decompressed and re-deflated. Python's deflate is weaker than whatever built
    the original archive -- a round trip through zipfile.writestr() inflates the
    two .obj meshes by about 1 MB -- and a one-file XML edit has no business
    growing the archive at all. Copying the streams also means every untouched
    entry stays byte-identical, not merely equal once decompressed.

    Only the flat, non-encrypted, non-zip64 layout the show folder actually uses
    is supported; anything else raises rather than silently producing a bad zip.
    """
    source = zip_path.read_bytes()

    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()

    local_header = struct.Struct("<I5H3I2H")
    central_header = struct.Struct("<I6H3I5H2I")
    end_record = struct.Struct("<I4H2IH")

    out = bytearray()
    central = bytearray()
    replaced = False

    for info in infos:
        if info.flag_bits & 0x9:
            raise CheckError(
                f"{info.filename!r} uses encryption or a data descriptor, "
                f"which this tool does not handle"
            )

        # Read the local header to find the raw data and the local extra field,
        # which can differ from the copy held in the central directory.
        fields = local_header.unpack_from(source, info.header_offset)
        if fields[0] != 0x04034B50:
            raise CheckError(f"bad local header for {info.filename!r}")
        name_len, extra_len = fields[9], fields[10]
        data_start = info.header_offset + local_header.size + name_len + extra_len
        local_extra = source[data_start - extra_len:data_start]

        crc, compress_size, file_size = info.CRC, info.compress_size, info.file_size
        data = source[data_start:data_start + compress_size]

        if info.filename == RGBEFFECTS_ENTRY:
            raw = new_text.encode("utf-8")
            crc, file_size = zlib.crc32(raw) & 0xFFFFFFFF, len(raw)
            if info.compress_type == zipfile.ZIP_STORED:
                data = raw
            else:
                compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
                data = compressor.compress(raw) + compressor.flush()
            compress_size = len(data)
            replaced = True

        name = info.filename.encode("utf-8")
        dos_time, dos_date = _dos_datetime(info.date_time)
        offset = len(out)

        out += local_header.pack(
            0x04034B50, info.extract_version, info.flag_bits, info.compress_type,
            dos_time, dos_date, crc, compress_size, file_size,
            len(name), len(local_extra),
        )
        out += name + local_extra + data

        central += central_header.pack(
            0x02014B50, info.create_version | (info.create_system << 8),
            info.extract_version, info.flag_bits, info.compress_type,
            dos_time, dos_date, crc, compress_size, file_size,
            len(name), len(info.extra), len(info.comment), 0,
            info.internal_attr, info.external_attr, offset,
        )
        central += name + info.extra + info.comment

    if not replaced:
        raise CheckError(f"{RGBEFFECTS_ENTRY} not found in {zip_path.name}")

    central_offset = len(out)
    out += central
    out += end_record.pack(0x06054B50, 0, 0, len(infos), len(infos),
                           len(central), central_offset, 0)

    tmp_path = zip_path.with_suffix(".zip.tmp")
    tmp_path.write_bytes(bytes(out))
    with zipfile.ZipFile(tmp_path) as check:      # refuse to ship a broken archive
        if check.testzip() is not None:
            raise CheckError(f"rewritten {zip_path.name} failed its own CRC check")
    tmp_path.replace(zip_path)


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


def parse(text: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise CheckError(f"{RGBEFFECTS_ENTRY} is not well-formed XML: {exc}") from exc


def models_of(element: ET.Element) -> list:
    return [name for name in (element.get("models") or "").split(",") if name]


def is_preview_model(name: str, spec: dict) -> bool:
    preview = spec["preview_models"]
    return name.startswith(preview["prefix"]) or name in preview["also"]


def preview_models(root: ET.Element, spec: dict) -> set:
    return {m.get("name") for m in root.find("models")
            if is_preview_model(m.get("name"), spec)}


# --------------------------------------------------------------------------
# fingerprint
# --------------------------------------------------------------------------


def build_fingerprint(text: str) -> dict:
    root = parse(text)
    models = {}
    for model in root.find("models"):
        models[model.get("name")] = {attr: model.get(attr) for attr in CHANNEL_ATTRS}
    return {
        "$comment": (
            "Channel assignment of every model in the xLights show folder. "
            "tools/xlights_layers.py verify fails if the show folder zip ever "
            "stops matching this file, which would silently break .fseq files "
            "exported from earlier versions of the project. Regenerate with "
            "`python3 tools/xlights_layers.py fingerprint` only as part of a "
            "change that intends to remap channels."
        ),
        "entry": RGBEFFECTS_ENTRY,
        "attributes": list(CHANNEL_ATTRS),
        "models": dict(sorted(models.items())),
    }


def cmd_fingerprint(_args) -> int:
    fingerprint = build_fingerprint(read_rgbeffects(SHOW_ZIP))
    FINGERPRINT_PATH.write_text(json.dumps(fingerprint, indent=2) + "\n")
    print(f"Wrote {FINGERPRINT_PATH.relative_to(REPO_ROOT)} "
          f"({len(fingerprint['models'])} models)")
    return 0


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------


def render_group(group: dict) -> str:
    return (
        f'{INDENT}<modelGroup selected="0" name={quoteattr(group["name"])} '
        f'LayoutGroup="Default" models={quoteattr(",".join(group["models"]))} '
        f'GridSize="400" XCentreOffset="0" YCentreOffset="0" '
        f'DefaultCamera="2D" layout="minimalGrid" TagColour="black"/>'
    )


def render_view(spec: dict) -> str:
    return (
        f'{INDENT}<view name={quoteattr(spec["view_name"])} '
        f'models={quoteattr(",".join(spec["view"]["models"]))}/>'
    )


def strip_existing(text: str, spec: dict) -> str:
    """Drop any layer groups / view we previously wrote, so apply is idempotent."""
    prefix = re.escape(spec["group_prefix"])
    patterns = [
        rf'^[ \t]*<modelGroup\b[^>]*\bname="{prefix}[^"]*"[^>]*/>[ \t]*\r?\n',
        rf'^[ \t]*<view\b[^>]*\bname="{re.escape(spec["view_name"])}"[^>]*/>[ \t]*\r?\n',
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)
    return text


def insert_before(text: str, closing_tag: str, block: str) -> str:
    match = re.search(rf'^([ \t]*){re.escape(closing_tag)}', text, flags=re.MULTILINE)
    if match is None:
        raise CheckError(f"Could not find {closing_tag} in {RGBEFFECTS_ENTRY}")
    return text[: match.start()] + block + "\n" + text[match.start():]


def apply_spec(text: str, spec: dict) -> str:
    text = strip_existing(text, spec)
    text = insert_before(text, "</modelGroups>",
                         "\n".join(render_group(g) for g in spec["groups"]))
    text = insert_before(text, "</views>", render_view(spec))
    return text


def cmd_apply(_args) -> int:
    spec = load_spec()
    before = read_rgbeffects(SHOW_ZIP)
    after = apply_spec(before, spec)
    parse(after)  # fail before touching the zip if we produced invalid XML
    if after == before:
        print("Show folder already up to date.")
        return 0
    write_rgbeffects(SHOW_ZIP, after)
    print(f"Applied {len(spec['groups'])} layer groups and the "
          f"{spec['view_name']!r} view to {SHOW_ZIP.relative_to(REPO_ROOT)}")
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------


def check_channel_map(text: str, failures: list) -> None:
    if not FINGERPRINT_PATH.exists():
        failures.append(f"{FINGERPRINT_PATH.name} is missing; run `fingerprint`")
        return
    expected = json.loads(FINGERPRINT_PATH.read_text())["models"]
    actual = build_fingerprint(text)["models"]

    for name in sorted(set(expected) - set(actual)):
        failures.append(f"model {name!r} was removed; .fseq files would shift")
    for name in sorted(set(expected) & set(actual)):
        if expected[name] != actual[name]:
            failures.append(
                f"model {name!r} channel assignment changed: "
                f"{expected[name]} -> {actual[name]}"
            )
    # New models are allowed as long as they do not displace an existing one,
    # which the equality check above already guarantees.


def check_spec_applied(root: ET.Element, spec: dict, failures: list) -> None:
    groups = {g.get("name"): g for g in root.find("modelGroups")}
    for wanted in spec["groups"]:
        actual = groups.get(wanted["name"])
        if actual is None:
            failures.append(f"group {wanted['name']!r} is missing from the show folder")
        elif models_of(actual) != wanted["models"]:
            failures.append(
                f"group {wanted['name']!r} does not match the spec: "
                f"{models_of(actual)} != {wanted['models']}"
            )

    views = {v.get("name"): v for v in root.find("views")}
    view = views.get(spec["view_name"])
    if view is None:
        failures.append(f"view {spec['view_name']!r} is missing from the show folder")
    elif models_of(view) != spec["view"]["models"]:
        failures.append(
            f"view {spec['view_name']!r} does not match the spec: "
            f"{models_of(view)} != {spec['view']['models']}"
        )


def check_references(root: ET.Element, failures: list) -> None:
    model_names = {m.get("name") for m in root.find("models")}
    groups = {g.get("name"): models_of(g) for g in root.find("modelGroups")}
    known = model_names | set(groups)

    for group_name, members in groups.items():
        for member in members:
            if member not in known:
                failures.append(
                    f"group {group_name!r} references unknown model {member!r}"
                )
    for view in root.find("views"):
        for member in models_of(view):
            if member not in known:
                failures.append(
                    f"view {view.get('name')!r} references unknown model {member!r}"
                )


def check_no_cycles(root: ET.Element, failures: list) -> None:
    groups = {g.get("name"): models_of(g) for g in root.find("modelGroups")}
    DONE, ACTIVE = 2, 1
    state = {}

    def walk(name, trail):
        if state.get(name) == ACTIVE:
            failures.append("group cycle: " + " -> ".join(trail + [name]))
            return
        if state.get(name) == DONE or name not in groups:
            return
        state[name] = ACTIVE
        for member in groups[name]:
            walk(member, trail + [name])
        state[name] = DONE

    for name in groups:
        walk(name, [])


def flatten(groups: dict, name: str) -> set:
    """Resolve a group name down to the set of leaf models it drives."""
    if name not in groups:
        return {name}
    leaves = set()
    for member in groups[name]:
        leaves |= flatten(groups, member)
    return leaves


def check_partitions(root: ET.Element, spec: dict, failures: list) -> None:
    groups = {g.get("name"): models_of(g) for g in root.find("modelGroups")}
    for invariant in spec.get("partition_invariants", []):
        whole = invariant["whole"]
        if whole not in groups:
            failures.append(f"partition invariant references unknown group {whole!r}")
            continue
        expected = flatten(groups, whole)
        actual = set()
        for part in invariant["parts"]:
            leaves = flatten(groups, part)
            overlap = actual & leaves
            if overlap:
                failures.append(
                    f"parts of {whole!r} overlap on {sorted(overlap)}"
                )
            actual |= leaves
        if actual != expected:
            failures.append(
                f"{invariant['parts']} is not a partition of {whole!r}; "
                f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
            )


def check_view_rows_disjoint(root: ET.Element, spec: dict, failures: list) -> None:
    groups = {g.get("name"): models_of(g) for g in root.find("modelGroups")}
    seen = {}
    for row in spec["view"]["models"]:
        for leaf in sorted(flatten(groups, row)):
            if leaf in seen:
                failures.append(
                    f"view {spec['view_name']!r} rows {seen[leaf]!r} and {row!r} "
                    f"both drive {leaf!r}"
                )
            else:
                seen[leaf] = row


def check_no_preview_models(root: ET.Element, spec: dict, failures: list) -> None:
    groups = {g.get("name"): models_of(g) for g in root.find("modelGroups")}
    for group in spec["groups"]:
        for leaf in sorted(flatten(groups, group["name"])):
            if is_preview_model(leaf, spec):
                failures.append(
                    f"group {group['name']!r} pulls in preview model {leaf!r}, "
                    f"which duplicates an existing channel"
                )


def check_preview_models_are_duplicates(root: ET.Element, spec: dict,
                                       failures: list) -> None:
    """Every declared preview model must shadow a real model's StartChannel.

    This keeps the exclusion list honest: if a future show folder renames or
    drops one of these, the list stops matching reality and we say so rather
    than silently excluding a model that carries channels of its own.
    """
    by_start = {}
    for model in root.find("models"):
        by_start.setdefault(model.get("StartChannel"), []).append(model.get("name"))

    declared = preview_models(root, spec)
    for name in sorted(declared):
        start = next(m.get("StartChannel") for m in root.find("models")
                     if m.get("name") == name)
        shadowed = [other for other in by_start.get(start, [])
                    if other != name and other not in declared]
        if not shadowed:
            failures.append(
                f"{name!r} is declared a preview model but no other model "
                f"starts at {start!r}; it may carry channels of its own"
            )

    for name in spec["preview_models"]["also"]:
        if name not in {m.get("name") for m in root.find("models")}:
            failures.append(f"preview model {name!r} is no longer in the show folder")


def cmd_verify(_args) -> int:
    failures: list = []
    try:
        text = read_rgbeffects(SHOW_ZIP)
        root = parse(text)
    except (CheckError, KeyError, zipfile.BadZipFile) as exc:
        print(f"FAIL  could not read the show folder: {exc}", file=sys.stderr)
        return 1

    spec = load_spec()
    checks = [
        ("channel assignments unchanged (.fseq compatibility)",
         lambda f: check_channel_map(text, f)),
        ("show folder matches layer_groups.json",
         lambda f: check_spec_applied(root, spec, f)),
        ("every group and view reference resolves",
         lambda f: check_references(root, f)),
        ("no group contains itself",
         lambda f: check_no_cycles(root, f)),
        ("declared preview models really are channel duplicates",
         lambda f: check_preview_models_are_duplicates(root, spec, f)),
        ("layer groups avoid duplicate preview models",
         lambda f: check_no_preview_models(root, spec, f)),
        ("layer groups partition the existing Front/Rear groups",
         lambda f: check_partitions(root, spec, f)),
        ("Layer View rows never drive the same model twice",
         lambda f: check_view_rows_disjoint(root, spec, f)),
    ]

    for label, check in checks:
        found: list = []
        check(found)
        print(f"{'FAIL' if found else 'ok  '}  {label}")
        for problem in found:
            print(f"        - {problem}")
        failures.extend(found)

    if failures:
        print(f"\n{len(failures)} problem(s) found.", file=sys.stderr)
        return 1
    print("\nShow folder verified.")
    return 0


# --------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fingerprint", help="record model channel assignments").set_defaults(
        func=cmd_fingerprint)
    sub.add_parser("apply", help="write the layer groups into the show folder").set_defaults(
        func=cmd_apply)
    sub.add_parser("verify", help="check the show folder (use in CI)").set_defaults(
        func=cmd_verify)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
