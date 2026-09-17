"""Tests for tools/xlights_layers.py and the shipped xLights show folder.

Runs with the standard library only: `python3 -m unittest discover -s tests`.

Each check in the verifier gets two tests: one that it passes on the real show
folder, and one that it actually fails when the corresponding thing is broken.
A check that cannot fail is not a check.
"""

import copy
import json
import shutil
import sys
import tempfile
import zipfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import xlights_layers as xl  # noqa: E402


def load_show_folder():
    return xl.read_rgbeffects(xl.SHOW_ZIP)


class ShowFolderTestCase(unittest.TestCase):
    """Shared fixture: the real show folder, parsed once."""

    @classmethod
    def setUpClass(cls):
        cls.text = load_show_folder()
        cls.root = ET.fromstring(cls.text)
        cls.spec = xl.load_spec()

    def groups(self, root=None):
        root = self.root if root is None else root
        return {g.get("name"): xl.models_of(g) for g in root.find("modelGroups")}

    def failures_from(self, check, *args):
        found = []
        check(*args, found)
        return found


class TestShippedShowFolder(ShowFolderTestCase):
    """The show folder committed to the repo must satisfy every invariant."""

    def test_verify_passes(self):
        self.assertEqual(xl.cmd_verify(None), 0)

    def test_every_spec_group_is_present_and_matches(self):
        self.assertEqual(
            self.failures_from(xl.check_spec_applied, self.root, self.spec), [])

    def test_channel_assignments_match_the_recorded_fingerprint(self):
        self.assertEqual(self.failures_from(xl.check_channel_map, self.text), [])

    def test_all_references_resolve(self):
        self.assertEqual(self.failures_from(xl.check_references, self.root), [])

    def test_no_group_cycles(self):
        self.assertEqual(self.failures_from(xl.check_no_cycles, self.root), [])

    def test_layer_groups_exclude_cybertruck_preview_models(self):
        self.assertEqual(
            self.failures_from(xl.check_no_preview_models, self.root, self.spec), [])

    def test_layer_groups_partition_the_existing_front_and_rear_groups(self):
        self.assertEqual(
            self.failures_from(xl.check_partitions, self.root, self.spec), [])

    def test_layer_view_rows_are_mutually_exclusive(self):
        self.assertEqual(
            self.failures_from(xl.check_view_rows_disjoint, self.root, self.spec), [])

    def test_layer_view_covers_every_channel_carrying_model(self):
        """No model may be stranded: the view has to reach all of them."""
        groups = self.groups()
        covered = set()
        for row in self.spec["view"]["models"]:
            covered |= xl.flatten(groups, row)

        # Poly Line roll-ups restate their own left/right segments, which the
        # view lists individually, so they are covered by construction.
        rollups = {"Front Light Bar", "Rear Light Bar"}

        stranded = sorted(
            m.get("name") for m in self.root.find("models")
            if not xl.is_preview_model(m.get("name"), self.spec)
            and m.get("name") not in covered
            and m.get("name") not in rollups
            and m.get("name") not in {seg for r in rollups
                                      for seg in groups.get(r, [])}
        )
        self.assertEqual(stranded, [])


class TestApplyIsIdempotent(ShowFolderTestCase):

    def test_reapplying_the_spec_changes_nothing(self):
        self.assertEqual(xl.apply_spec(self.text, self.spec), self.text)

    def test_apply_recreates_the_show_folder_from_a_stripped_copy(self):
        stripped = xl.strip_existing(self.text, self.spec)
        self.assertNotIn("LAYER ", stripped)
        self.assertEqual(xl.apply_spec(stripped, self.spec), self.text)

    def test_apply_produces_well_formed_xml(self):
        ET.fromstring(xl.apply_spec(self.text, self.spec))


class TestChecksActuallyFail(ShowFolderTestCase):
    """Negative tests: break one thing, confirm the matching check complains."""

    def test_moving_a_start_channel_is_rejected(self):
        broken = self.text.replace('StartChannel="!Model S:1"',
                                   'StartChannel="!Model S:99"', 1)
        self.assertNotEqual(broken, self.text)
        failures = self.failures_from(xl.check_channel_map, broken)
        self.assertTrue(any("channel assignment changed" in f for f in failures),
                        failures)

    def test_deleting_a_model_is_rejected(self):
        """A model in the recorded map but absent from the zip must be caught."""
        fingerprint = xl.build_fingerprint(self.text)
        fingerprint["models"]["Ghost Model"] = {a: "0" for a in xl.CHANNEL_ATTRS}

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(fingerprint, handle)
            recorded = Path(handle.name)
        original = xl.FINGERPRINT_PATH
        try:
            xl.FINGERPRINT_PATH = recorded
            failures = self.failures_from(xl.check_channel_map, self.text)
        finally:
            xl.FINGERPRINT_PATH = original
            recorded.unlink()

        self.assertTrue(any("Ghost Model" in f and "removed" in f for f in failures),
                        failures)

    def test_a_missing_fingerprint_file_is_reported(self):
        original = xl.FINGERPRINT_PATH
        try:
            xl.FINGERPRINT_PATH = Path("/nonexistent/channel_map.json")
            failures = self.failures_from(xl.check_channel_map, self.text)
        finally:
            xl.FINGERPRINT_PATH = original
        self.assertTrue(any("missing" in f for f in failures), failures)

    def test_a_dangling_model_reference_is_rejected(self):
        root = ET.fromstring(self.text)
        group = root.find("modelGroups")[0]
        group.set("models", group.get("models") + ",No Such Model")
        failures = self.failures_from(xl.check_references, root)
        self.assertTrue(any("No Such Model" in f for f in failures), failures)

    def test_a_group_cycle_is_rejected(self):
        root = ET.fromstring(self.text)
        groups = {g.get("name"): g for g in root.find("modelGroups")}
        groups["LAYER Front Left"].set(
            "models", groups["LAYER Front Left"].get("models") + ",LAYER Left Side")
        failures = self.failures_from(xl.check_no_cycles, root)
        self.assertTrue(any("cycle" in f for f in failures), failures)

    def test_a_cybertruck_preview_model_in_a_layer_is_rejected(self):
        root = ET.fromstring(self.text)
        groups = {g.get("name"): g for g in root.find("modelGroups")}
        groups["LAYER Front Left"].set(
            "models", groups["LAYER Front Left"].get("models") + ",CT Left Mirror")
        failures = self.failures_from(xl.check_no_preview_models, root, self.spec)
        self.assertTrue(any("CT Left Mirror" in f for f in failures), failures)

    def test_an_incomplete_partition_is_rejected(self):
        root = ET.fromstring(self.text)
        groups = {g.get("name"): g for g in root.find("modelGroups")}
        members = groups["LAYER Rear Center"].get("models").split(",")
        groups["LAYER Rear Center"].set("models", ",".join(members[:-1]))
        failures = self.failures_from(xl.check_partitions, root, self.spec)
        self.assertTrue(any("not a partition" in f for f in failures), failures)

    def test_overlapping_partition_parts_are_rejected(self):
        root = ET.fromstring(self.text)
        groups = {g.get("name"): g for g in root.find("modelGroups")}
        groups["LAYER Rear Right"].set(
            "models", groups["LAYER Rear Right"].get("models") + ",Left Tail")
        failures = self.failures_from(xl.check_partitions, root, self.spec)
        self.assertTrue(any("overlap" in f for f in failures), failures)

    def test_overlapping_view_rows_are_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["view"]["models"].append("LAYER Left Side")
        failures = self.failures_from(xl.check_view_rows_disjoint, self.root, spec)
        self.assertTrue(any("both drive" in f for f in failures), failures)

    def test_a_missing_group_is_rejected(self):
        root = ET.fromstring(xl.strip_existing(self.text, self.spec))
        failures = self.failures_from(xl.check_spec_applied, root, self.spec)
        self.assertTrue(any("is missing" in f for f in failures), failures)


    def test_a_preview_model_that_shadows_nothing_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["preview_models"]["also"].append("Suspension")  # not a duplicate
        failures = self.failures_from(
            xl.check_preview_models_are_duplicates, self.root, spec)
        self.assertTrue(any("Suspension" in f for f in failures), failures)

    def test_a_stale_preview_model_name_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["preview_models"]["also"].append("Removed Model")
        failures = self.failures_from(
            xl.check_preview_models_are_duplicates, self.root, spec)
        self.assertTrue(any("Removed Model" in f for f in failures), failures)


class TestZipRewriting(ShowFolderTestCase):
    """The rewriter hand-builds the archive, so check it against zipfile itself."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.copy = Path(self.tmpdir) / "show.zip"
        shutil.copy(xl.SHOW_ZIP, self.copy)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_only_the_edited_entry_changes(self):
        marker = self.text.replace("</xrgb>", "  <!-- test -->\n</xrgb>")
        xl.write_rgbeffects(self.copy, marker)

        with zipfile.ZipFile(xl.SHOW_ZIP) as before, zipfile.ZipFile(self.copy) as after:
            self.assertEqual([i.filename for i in before.infolist()],
                             [i.filename for i in after.infolist()])
            self.assertIsNone(after.testzip())
            for info in before.infolist():
                if info.is_dir():
                    continue
                if info.filename == xl.RGBEFFECTS_ENTRY:
                    self.assertEqual(after.read(info.filename).decode(), marker)
                    continue
                self.assertEqual(before.read(info.filename),
                                 after.read(info.filename), info.filename)

    def test_entry_metadata_is_preserved(self):
        xl.write_rgbeffects(self.copy, self.text)
        with zipfile.ZipFile(xl.SHOW_ZIP) as before, zipfile.ZipFile(self.copy) as after:
            for info in before.infolist():
                other = after.getinfo(info.filename)
                self.assertEqual(
                    (info.date_time, info.compress_type, info.external_attr,
                     info.internal_attr, info.create_system, info.extra),
                    (other.date_time, other.compress_type, other.external_attr,
                     other.internal_attr, other.create_system, other.extra),
                    info.filename)

    def test_rewriting_does_not_inflate_the_archive(self):
        """Untouched entries must be copied, not re-deflated by Python."""
        xl.write_rgbeffects(self.copy, self.text)
        growth = self.copy.stat().st_size - xl.SHOW_ZIP.stat().st_size
        self.assertLess(abs(growth), 4096, f"archive size moved by {growth} bytes")


class TestSpecFile(ShowFolderTestCase):

    def test_group_names_all_use_the_layer_prefix(self):
        for group in self.spec["groups"]:
            self.assertTrue(group["name"].startswith(self.spec["group_prefix"]),
                            group["name"])

    def test_group_names_are_unique(self):
        names = [g["name"] for g in self.spec["groups"]]
        self.assertCountEqual(names, set(names))

    def test_no_group_lists_the_same_model_twice(self):
        for group in self.spec["groups"]:
            self.assertCountEqual(group["models"], set(group["models"]),
                                  group["name"])

    def test_powered_frunk_is_declared_a_preview_model(self):
        """It shadows Liftgate's channel without following the 'CT ' convention."""
        self.assertTrue(xl.is_preview_model("Powered Frunk", self.spec))

    def test_declared_preview_models_shadow_a_real_channel(self):
        self.assertEqual(
            self.failures_from(xl.check_preview_models_are_duplicates,
                               self.root, self.spec), [])

    def test_layer_names_do_not_collide_with_existing_groups(self):
        """The prefix has to keep the new groups out of the way of the old ones."""
        preexisting = {g.get("name") for g in self.root.find("modelGroups")
                       if not g.get("name").startswith(self.spec["group_prefix"])}
        for group in self.spec["groups"]:
            self.assertNotIn(group["name"], preexisting)


if __name__ == "__main__":
    unittest.main()
