"""Tests for tools/vehicle_preview.py.

The scenarios named "issue 42" reproduce the two mismatches reported in
https://github.com/teslamotors/light-show/issues/42 and assert that the tool
explains each one on Model 3 while staying quiet on Model S, which is the
vehicle the xLights preview models.
"""

import io
import os
import struct
import sys
import tempfile
import unittest
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import vehicle_preview as vp  # noqa: E402


HEADER_BYTES = 32


def build_fseq_bytes(frames, channel_count=48, step_time=20,
                     magic=b"PSEQ", compression=0, major=2, minor=0,
                     payload=None):
    """Assemble a V2 uncompressed .fseq image for tests."""
    header = bytearray(HEADER_BYTES)
    header[0:4] = magic
    struct.pack_into("<H", header, 4, HEADER_BYTES)
    header[6] = minor
    header[7] = major
    struct.pack_into("<IIB", header, 10, channel_count, frames, step_time)
    header[20] = compression
    body = payload if payload is not None else bytes(channel_count * frames)
    return bytes(header) + body


def make_show(frame_count, events, channel_count=48, step_time=20):
    """Build a Show directly.

    `events` maps a 1-based channel to a list of (start_frame, length, value).
    """
    data = bytearray(frame_count * channel_count)
    for channel, spans in events.items():
        for start, length, value in spans:
            for frame in range(start, start + length):
                data[frame * channel_count + (channel - 1)] = value
    return vp.Show(channel_count, frame_count, step_time, bytes(data))


def codes(findings):
    return [f.code for f in findings]


def find(findings, code, channel=None):
    """Return the findings with this code, optionally touching a channel."""
    return [
        f for f in findings
        if f.code == code and (channel is None or channel in f.channels)
    ]


# Brightness bytes for the effects documented in README.md.
ON_INSTANT = 255        # 100%, "Turn on; Instant"
ON_500 = 178            # 70%,  "Turn on; 500 ms"
ON_2000 = 229           # 90%,  "Turn on; 2000 ms"
OFF_500 = 25            # 10%,  "Turn off; 500 ms"

LEFT_FRONT_TURN = 13
RIGHT_FRONT_TURN = 14
LEFT_CH4, LEFT_CH5, LEFT_CH6 = 7, 9, 11
RIGHT_CH4, RIGHT_CH5, RIGHT_CH6 = 8, 10, 12
LEFT_AUX_PARK, LEFT_SIDE_MARKER = 17, 19
LEFT_SIGNATURE = 5


class EffectEncodingTests(unittest.TestCase):
    def test_ramp_codes_round_trip_from_bytes(self):
        # Every documented effect percentage must survive the byte round trip,
        # otherwise the tool would silently misread real shows.
        for percent in vp.RAMP_CODES:
            raw = int(round(percent * 255.0 / 100.0))
            self.assertEqual(vp.to_percent(raw), percent,
                             "percent {} did not round trip".format(percent))

    def test_closure_codes_round_trip_from_bytes(self):
        for percent in vp.CLOSURE_CODES:
            raw = int(round(percent * 255.0 / 100.0))
            self.assertEqual(vp.to_percent(raw), percent)

    def test_on_threshold_matches_the_documented_50_percent_rule(self):
        self.assertFalse(127 > vp.ON_THRESHOLD)   # 49.8% is off
        self.assertTrue(128 > vp.ON_THRESHOLD)    # 50.2% is on


class ChannelMapTests(unittest.TestCase):
    def test_channel_numbers_are_contiguous_from_one(self):
        self.assertEqual(sorted(vp.CHANNELS), list(range(1, 47)))

    def test_channel_names_are_unique(self):
        names = [name for name, _ in vp.CHANNELS.values()]
        self.assertEqual(len(names), len(set(names)))

    def test_every_profile_only_names_known_channels(self):
        for profile in vp.VEHICLES.values():
            for channel in profile.kinds:
                self.assertIn(channel, vp.CHANNELS, profile.key)
            for group in profile.or_groups:
                for channel in group.channels:
                    self.assertIn(channel, vp.CHANNELS, profile.key)
            for follower, leader in profile.ramp_leaders.items():
                self.assertIn(follower, vp.CHANNELS, profile.key)
                self.assertIn(leader, vp.CHANNELS, profile.key)

    def test_ramp_leaders_all_point_at_a_channel_4(self):
        # README.md: Channel 4 defines the ramp duration for Channels 4-6.
        for profile in vp.VEHICLES.values():
            for leader in profile.ramp_leaders.values():
                self.assertIn(leader, (LEFT_CH4, RIGHT_CH4), profile.key)


class ReadFseqTests(unittest.TestCase):
    def _write(self, blob):
        handle = tempfile.NamedTemporaryFile(suffix=".fseq", delete=False)
        handle.write(blob)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_reads_a_well_formed_file(self):
        path = self._write(build_fseq_bytes(frames=10))
        show = vp.read_fseq(path)
        self.assertEqual(show.channel_count, 48)
        self.assertEqual(show.frame_count, 10)
        self.assertEqual(show.step_time_ms, 20)
        self.assertEqual(show.duration_ms, 200)

    def test_series_returns_one_channel_across_frames(self):
        show = make_show(4, {LEFT_FRONT_TURN: [(1, 2, ON_INSTANT)]})
        self.assertEqual(list(show.series(LEFT_FRONT_TURN)), [0, 255, 255, 0])

    def test_rejects_foreign_file(self):
        path = self._write(b"NOTAFSEQ" + bytes(64))
        with self.assertRaises(vp.ShowError):
            vp.read_fseq(path)

    def test_rejects_compressed_file(self):
        path = self._write(build_fseq_bytes(frames=4, compression=1))
        with self.assertRaises(vp.ShowError):
            vp.read_fseq(path)

    def test_rejects_unexpected_channel_count(self):
        path = self._write(build_fseq_bytes(frames=4, channel_count=64))
        with self.assertRaises(vp.ShowError):
            vp.read_fseq(path)

    def test_rejects_truncated_frame_data(self):
        blob = build_fseq_bytes(frames=10)
        path = self._write(blob[:HEADER_BYTES + 48 * 3])
        with self.assertRaises(vp.ShowError):
            vp.read_fseq(path)


class RunsTests(unittest.TestCase):
    def test_splits_a_series_into_constant_runs(self):
        runs = vp.runs_of([0, 0, 255, 255, 255, 0])
        self.assertEqual(
            [(r.value, r.start_frame, r.frames) for r in runs],
            [(0, 0, 2), (255, 2, 3), (0, 5, 1)],
        )

    def test_empty_series_has_no_runs(self):
        self.assertEqual(vp.runs_of([]), [])


class OrGroupTests(unittest.TestCase):
    def test_issue_42_channels_4_to_6_collapse_on_model_3(self):
        # The reporter sequenced Right Channel 4/5/6 independently and saw a
        # single lamp light up next to the turn signal.
        show = make_show(60, {
            RIGHT_CH4: [(0, 10, ON_INSTANT)],
            RIGHT_CH5: [(20, 10, ON_INSTANT)],
            RIGHT_CH6: [(40, 10, ON_INSTANT)],
        })
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        collapse = find(findings, "or-group-collapse", RIGHT_CH5)
        self.assertEqual(len(collapse), 1)
        self.assertIn("one output", collapse[0].detail)
        self.assertEqual(collapse[0].first_at_ms, 0)

    def test_issue_42_channels_4_to_6_are_independent_on_model_s(self):
        # Same sequence, no collapse reported: Model S drives each separately,
        # which is exactly why the preview looked right to the reporter.
        show = make_show(60, {
            RIGHT_CH4: [(0, 10, ON_INSTANT)],
            RIGHT_CH5: [(20, 10, ON_INSTANT)],
            RIGHT_CH6: [(40, 10, ON_INSTANT)],
        })
        findings = vp.analyze(show, vp.VEHICLES["models"])
        self.assertEqual(find(findings, "or-group-collapse", RIGHT_CH5), [])

    def test_model_3_merges_all_four_aux_park_and_side_marker_channels(self):
        show = make_show(40, {
            LEFT_AUX_PARK: [(0, 10, ON_INSTANT)],
            LEFT_SIDE_MARKER: [(20, 10, ON_INSTANT)],
        })
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        collapse = find(findings, "or-group-collapse", LEFT_AUX_PARK)
        self.assertEqual(len(collapse), 1)
        # All four channels share the single Model 3/Y output.
        self.assertEqual(collapse[0].channels, (17, 18, 19, 20))

    def test_interleaved_blinking_is_reported_as_a_solid_glow(self):
        # Channel 4 and 5 alternate with no shared gap, so the shared lamp
        # never goes out - README.md's "ord_channel_not_ok" case.
        spans_a = [(start, 10, ON_INSTANT) for start in range(0, 200, 20)]
        spans_b = [(start, 10, ON_INSTANT) for start in range(10, 200, 20)]
        show = make_show(200, {LEFT_CH4: spans_a, LEFT_CH5: spans_b})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        solid = find(findings, "or-group-never-off", LEFT_CH4)
        self.assertEqual(len(solid), 1)
        self.assertEqual(solid[0].severity, vp.ERROR)

    def test_a_deliberately_solid_light_is_not_reported(self):
        # One member held on for the whole span: the continuous output is what
        # the author asked for, so this must not be flagged.
        show = make_show(200, {
            LEFT_CH4: [(0, 200, ON_INSTANT)],
            LEFT_CH5: [(50, 10, ON_INSTANT)],
        })
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(find(findings, "or-group-never-off"), [])

    def test_a_group_with_only_one_channel_used_does_not_collapse(self):
        # Nothing collapses when the rest of the group is empty: the single
        # channel simply drives the shared lamp on its own.
        show = make_show(60, {RIGHT_CH4: [(0, 10, ON_INSTANT)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(find(findings, "or-group-collapse"), [])

    def test_two_channels_in_a_group_still_collapse(self):
        show = make_show(60, {
            RIGHT_CH4: [(0, 10, ON_INSTANT)],
            RIGHT_CH6: [(20, 10, ON_INSTANT)],
        })
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(len(find(findings, "or-group-collapse", RIGHT_CH4)), 1)

    def test_unused_group_produces_no_findings(self):
        show = make_show(50, {})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(find(findings, "or-group-collapse"), [])
        self.assertEqual(find(findings, "or-group-never-off"), [])


class RampTests(unittest.TestCase):
    def test_issue_42_short_turn_signal_flash_is_an_error_on_model_3(self):
        # A two-frame "Turn on; 500 ms" flash: a crisp blink in the Model S
        # preview, almost invisible on a Model 3 where the channel ramps.
        show = make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        short = find(findings, "ramp-too-short", LEFT_FRONT_TURN)
        self.assertEqual(len(short), 1)
        self.assertEqual(short[0].severity, vp.ERROR)
        self.assertIn("boolean on Model S", short[0].detail)

    def test_issue_42_short_turn_signal_flash_is_fine_on_model_s(self):
        show = make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]})
        findings = vp.analyze(show, vp.VEHICLES["models"])
        self.assertEqual(find(findings, "ramp-too-short", LEFT_FRONT_TURN), [])
        # Model S reports the ignored ramp as a note instead.
        self.assertEqual(
            len(find(findings, "ramp-ignored", LEFT_FRONT_TURN)), 1)

    def test_signature_ramps_on_model_3_but_not_on_model_s(self):
        self.assertEqual(
            vp.kind_of(vp.VEHICLES["model3"], LEFT_SIGNATURE), vp.RAMPING)
        self.assertEqual(
            vp.kind_of(vp.VEHICLES["models"], LEFT_SIGNATURE), vp.BOOLEAN)

    def test_a_ramp_that_almost_completes_is_only_a_note(self):
        # 90% of the way to the setpoint is a rounding detail, not a defect.
        show = make_show(200, {LEFT_FRONT_TURN: [(0, 22, ON_500)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        short = find(findings, "ramp-too-short", LEFT_FRONT_TURN)
        self.assertEqual(len(short), 1)
        self.assertEqual(short[0].severity, vp.INFO)

    def test_a_ramp_with_room_to_complete_is_not_reported(self):
        show = make_show(200, {LEFT_FRONT_TURN: [(0, 40, ON_500)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(find(findings, "ramp-too-short", LEFT_FRONT_TURN), [])

    def test_instant_effects_never_report_a_truncated_ramp(self):
        show = make_show(50, {LEFT_FRONT_TURN: [(0, 1, ON_INSTANT)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(find(findings, "ramp-too-short", LEFT_FRONT_TURN), [])

    def test_channel_5_ramping_without_channel_4_is_reported(self):
        # README.md: Channel 4 alone defines the ramp duration for 4-6.
        show = make_show(200, {LEFT_CH5: [(0, 150, ON_2000)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        leader = find(findings, "ramp-leader-missing", LEFT_CH5)
        self.assertEqual(len(leader), 1)
        self.assertEqual(leader[0].channels, (LEFT_CH5, LEFT_CH4))

    def test_channel_5_ramping_with_channel_4_present_is_accepted(self):
        show = make_show(200, {
            LEFT_CH4: [(0, 150, OFF_500)],
            LEFT_CH5: [(0, 150, ON_2000)],
        })
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        self.assertEqual(find(findings, "ramp-leader-missing", LEFT_CH5), [])

    def test_ramp_leader_rule_applies_to_model_s_too(self):
        show = make_show(200, {LEFT_CH5: [(0, 150, ON_2000)]})
        findings = vp.analyze(show, vp.VEHICLES["models"])
        self.assertEqual(
            len(find(findings, "ramp-leader-missing", LEFT_CH5)), 1)


class HardwareTests(unittest.TestCase):
    def test_cybertruck_has_no_signature_lights(self):
        show = make_show(20, {LEFT_SIGNATURE: [(0, 10, ON_INSTANT)]})
        findings = vp.analyze(show, vp.VEHICLES["cybertruck"])
        absent = find(findings, "channel-not-present", LEFT_SIGNATURE)
        self.assertEqual(len(absent), 1)
        self.assertEqual(absent[0].severity, vp.INFO)

    def test_front_fog_is_optional_hardware_on_model_3(self):
        show = make_show(20, {15: [(0, 10, ON_INSTANT)]})
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        optional = find(findings, "channel-optional-hardware", 15)
        self.assertEqual(len(optional), 1)
        self.assertIn("Standard Range", optional[0].detail)

    def test_front_fog_is_standard_on_model_y(self):
        show = make_show(20, {15: [(0, 10, ON_INSTANT)]})
        findings = vp.analyze(show, vp.VEHICLES["modely"])
        self.assertEqual(find(findings, "channel-optional-hardware", 15), [])

    def test_untouched_channels_are_never_reported(self):
        show = make_show(20, {})
        for key in vp.VEHICLES:
            findings = vp.analyze(show, vp.VEHICLES[key])
            self.assertEqual(findings, [], key)


class ReportingTests(unittest.TestCase):
    def test_findings_are_ordered_by_severity(self):
        show = make_show(200, {
            LEFT_CH4: [(start, 10, ON_INSTANT) for start in range(0, 200, 20)],
            LEFT_CH5: [(start, 10, ON_INSTANT) for start in range(10, 200, 20)],
            LEFT_SIGNATURE: [(0, 2, ON_500)],
            15: [(0, 5, ON_INSTANT)],
        })
        findings = vp.analyze(show, vp.VEHICLES["model3"])
        ranks = [vp._SEVERITY_ORDER[f.severity] for f in findings]
        self.assertEqual(ranks, sorted(ranks))

    def test_finding_serialises_to_json_friendly_types(self):
        show = make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]})
        finding = vp.analyze(show, vp.VEHICLES["model3"])[0].as_dict()
        self.assertEqual(
            set(finding),
            {"severity", "code", "summary", "detail", "channels",
             "first_at_ms", "occurrences"},
        )
        self.assertEqual(finding["channels"][0]["name"], "Left Front Turn")

    def test_report_names_every_requested_vehicle(self):
        show = make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]})
        results = {k: vp.analyze(show, v) for k, v in vp.VEHICLES.items()}
        report = vp.render_report(show, results, verbose=True)
        for profile in vp.VEHICLES.values():
            self.assertIn(profile.label, report)

    def test_clean_show_is_reported_as_matching_the_preview(self):
        show = make_show(50, {LEFT_FRONT_TURN: [(0, 10, ON_INSTANT)]})
        results = {"models": vp.analyze(show, vp.VEHICLES["models"])}
        self.assertIn("renders the same way",
                      vp.render_report(show, results, verbose=False))


class CommandLineTests(unittest.TestCase):
    def _write_show(self, show):
        blob = build_fseq_bytes(
            frames=show.frame_count,
            channel_count=show.channel_count,
            step_time=show.step_time_ms,
            payload=show.data,
        )
        handle = tempfile.NamedTemporaryFile(suffix=".fseq", delete=False)
        handle.write(blob)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        saved = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout, stderr
        try:
            code = vp.main(argv)
        finally:
            sys.stdout, sys.stderr = saved
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exits_zero_for_a_show_with_findings(self):
        path = self._write_show(
            make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]}))
        code, out, _ = self._run([path, "--vehicle", "model3"])
        self.assertEqual(code, 0)
        self.assertIn("ramp-too-short", out)

    def test_strict_exits_non_zero_when_something_is_reported(self):
        path = self._write_show(
            make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]}))
        code, _, _ = self._run([path, "--vehicle", "model3", "--strict"])
        self.assertEqual(code, 1)

    def test_strict_exits_zero_for_a_clean_show(self):
        path = self._write_show(
            make_show(50, {LEFT_FRONT_TURN: [(0, 10, ON_INSTANT)]}))
        code, _, _ = self._run([path, "--vehicle", "models", "--strict"])
        self.assertEqual(code, 0)

    def test_json_output_is_parseable(self):
        import json
        path = self._write_show(
            make_show(50, {LEFT_FRONT_TURN: [(0, 2, ON_500)]}))
        code, out, _ = self._run([path, "--vehicle", "model3", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["frame_count"], 50)
        self.assertIn("model3", payload["vehicles"])

    def test_unreadable_file_reports_an_error(self):
        code, _, err = self._run([os.path.join(REPO_ROOT, "does-not-exist.fseq")])
        self.assertEqual(code, 2)
        self.assertTrue(err.strip())


class ShippedExampleTests(unittest.TestCase):
    """The example shows in this repository must analyse cleanly end to end."""

    def _example_fseqs(self):
        """Yield (label, bytes) for every example show, zipped or loose."""
        examples = os.path.join(REPO_ROOT, "examples")
        for name in sorted(os.listdir(examples)):
            if not name.endswith(".zip"):
                continue
            with zipfile.ZipFile(os.path.join(examples, name)) as bundle:
                for member in sorted(bundle.namelist()):
                    if member.lower().endswith(".fseq"):
                        yield "{}:{}".format(name, member), bundle.read(member)
        # The multi-car examples ship unpacked rather than as archives.
        for root, _, files in sorted(os.walk(examples)):
            for name in sorted(files):
                if not name.lower().endswith(".fseq"):
                    continue
                path = os.path.join(root, name)
                with open(path, "rb") as handle:
                    yield os.path.relpath(path, REPO_ROOT), handle.read()

    def test_every_example_show_analyses_on_every_vehicle(self):
        seen = 0
        for name, blob in self._example_fseqs():
            seen += 1
            handle = tempfile.NamedTemporaryFile(suffix=".fseq", delete=False)
            handle.write(blob)
            handle.close()
            try:
                show = vp.read_fseq(handle.name)
                for key, profile in vp.VEHICLES.items():
                    findings = vp.analyze(show, profile)
                    for finding in findings:
                        self.assertIn(finding.severity,
                                      (vp.ERROR, vp.WARNING, vp.INFO))
                        self.assertTrue(finding.summary, name)
                        self.assertTrue(finding.detail, name)
            finally:
                os.unlink(handle.name)
        self.assertGreater(seen, 0, "no example .fseq files were found")

    def test_examples_cover_both_channel_counts(self):
        # The 48-channel shows and the 200-channel Cybertruck shows take
        # different paths through the channel map, so both must be present.
        counts = set()
        for _, blob in self._example_fseqs():
            counts.add(struct.unpack("<I", blob[10:14])[0])
        self.assertEqual(counts, {48, 200})


if __name__ == "__main__":
    unittest.main()
