# CLAUDE.md

Guidance for Claude Code (claude.ai/code) and other agents working in this repository.

## What this repository is

`teslamotors/light-show` distributes the assets Tesla owners use to author custom
vehicle light shows: an xLights show folder describing the car's lights and
closures, example sequences, and a validator for the `.fseq` files xLights
exports.

There is no application to build here. The deliverables are **data files**, and
almost every change is a change to something a car will eventually play.

## Layout

| Path | What it is |
| --- | --- |
| `README.md` | The product documentation. It is the main deliverable for most users; keep it in sync with any behaviour change. |
| `validator.py` | Standalone `.fseq` checker. Pure standard library, Python 3.7+, run by double-click on Windows. |
| `validator-windows.exe`, `validator-macos.zip` | Packaged builds of `validator.py`, produced by `.github/workflows/build.yml`. |
| `xlights/tesla_xlights_show_folder.zip` | **The xLights show folder.** The file that matters is `tesla_xlights_show_folder/xlights_rgbeffects.xml` inside it. |
| `xlights/tesla_xlights_cross_vehicle_folder.zip` | Separate show folder for mapping one show onto five vehicles. |
| `xlights/layer_groups.json` | Declarative spec for the positional "layer" model groups. Source of truth for what the zip contains. |
| `xlights/channel_map.json` | Recorded channel assignment of every model. A regression lock, see below. |
| `tools/xlights_layers.py` | Applies and verifies the two files above against the zip. |
| `tests/` | `unittest` suite, standard library only. |
| `examples/` | Example shows, distributed as zips. |

## The one rule: never move a channel

Shows are exported as `.fseq` files that are just arrays of channel values. A
`.fseq` a user exported last year must keep playing correctly on the same car
this year. That means the mapping from **model name → `StartChannel`** in
`xlights_rgbeffects.xml` is a public API.

`xlights/channel_map.json` records that mapping. `tools/xlights_layers.py verify`
fails if it ever drifts, and CI runs it on every pull request. If you are asked
to make a change that genuinely needs to remap channels, that is a deliberate
breaking change: say so explicitly, and regenerate the file with
`python3 tools/xlights_layers.py fingerprint` as part of the same commit.

Safe to add: model groups and views. They are sequencer-side only — they
reference existing models by name and own no channels.

## Working on the show folder

The show folder is a binary zip, so a diff shows nothing useful. Do not hand-edit
the zip. The workflow is:

```bash
# edit xlights/layer_groups.json, then
python3 tools/xlights_layers.py apply     # write it into the zip
python3 tools/xlights_layers.py verify    # check every invariant
python3 -m unittest discover -s tests     # run the suite
```

`apply` is idempotent and rewrites only the one XML entry, copying every other
entry's compressed stream verbatim — a round trip through `zipfile.writestr()`
re-deflates the 15 MB `.obj` meshes with Python's weaker compressor and adds
about 1 MB to the archive for no reason. CI asserts `apply` leaves the committed
zip byte-identical, which is what keeps the spec and the zip from drifting apart.

### Things that are easy to get wrong

- **Cybertruck preview models duplicate Model S channels.** `CT Left Mirror`,
  `Powered Frunk` and friends exist so the 3D layout can render a second
  vehicle; they deliberately reuse another model's `StartChannel`. Putting one in
  a timeline group drives a single channel from two rows. They are declared in
  `layer_groups.json` under `preview_models` — note that `Powered Frunk` does
  *not* follow the `CT ` naming convention, so a prefix check alone is wrong.
- **Rows within a view should not overlap.** Two rows that resolve to the same
  model race each other at render time.
- **Model groups may contain other model groups.** Prefer composing existing
  groups over restating their members, and keep the graph acyclic.
- **`Backup/` entries inside the zip are historical snapshots.** Leave them alone;
  xLights writes a fresh one each time it opens the folder.

## Conventions

- **Python**: standard library only, in both `validator.py` and `tools/`. Users
  run these by double-clicking a file; a dependency they have to install is a
  support burden. Target 3.7+.
- **Group naming**: `GRP ` for left/right pairs of one light type, `All ` for the
  multishow-import groups, `LR ` for light-bar halves, `LAYER ` for the
  positional layers. Match the surrounding convention rather than inventing one.
- **Tests**: every check should have a test proving it fails when the thing it
  checks is broken. A check that cannot fail is not a check.
- **README**: user-facing and screenshot-heavy. Images live in `images/` and are
  referenced as `/images/name.png?raw=true`.

## Not in scope unless asked

- Regenerating `validator-windows.exe` / `validator-macos.zip` (maintainers do
  this via the `Build Executable` workflow).
- `xlights/tesla_xlights_cross_vehicle_folder.zip`, which carries five copies of
  the vehicle models and is maintained separately from the main show folder.
