# CLAUDE.md

Guidance for Claude Code (claude.com/claude-code) and other coding agents working in this repository.

## What this repository is

This is the **Tesla Light Show xLights guide**: the documentation and tooling that let owners author custom light shows and run them on a Tesla vehicle from a USB drive. It is primarily a documentation repository with a small amount of Python tooling. There is no application to build or deploy.

The user-facing artifacts are:

- `README.md` — the guide itself. This is the normative specification for how the vehicle interprets a show, and most of the repository's value lives here.
- `xlights/tesla_xlights_show_folder.zip` — the xLights project directory that show authors download. It contains the 3D vehicle model and, in `xlights_rgbeffects.xml`, the authoritative channel assignment.
- `xlights/tesla_xlights_cross_vehicle_folder.zip` — the multi-vehicle variant.
- `examples/` — complete example shows, some as `.zip` bundles containing a `.fseq`.
- `validator.py` — checks that a `.fseq` meets the vehicle's format and duration limits.
- `tools/vehicle_preview.py` — reports where a show will behave differently on a given vehicle than it does in the xLights preview.

## How to run things

Everything is standard-library Python, no dependencies and no virtualenv needed.

```bash
# Run the test suite
python3 -m unittest discover -s tests -v

# Check a show's format and length
python3 validator.py path/to/lightshow.fseq

# See how a show will actually render on each vehicle
python3 tools/vehicle_preview.py path/to/lightshow.fseq
python3 tools/vehicle_preview.py path/to/lightshow.fseq --vehicle model3 -v
```

`validator.py` ends with `input("Press Enter to exit...")` so that Windows users can double-click it. Never call it non-interactively in a script or CI step; import `validate()` or use `tools/vehicle_preview.py` instead.

## Domain facts that are easy to get wrong

These cost real debugging time, so check them before changing behavior:

- **The xLights preview is a Model S.** The show folder ships one superset vehicle model. Every channel appears as its own light that switches instantly. Several vehicles do not work that way, which is the root of most "my show looks wrong on the car" reports.
- **Channels are OR'd on some vehicles.** On Model 3/Y, Channels 4, 5 and 6 drive a single output per side, and all four aux park / side marker channels drive one output. A group only flashes if *every* channel in it has a shared off-time.
- **Ramping is per-vehicle.** Front turn and signature lights are boolean on Model S but ramp on Model 3/Y. A two-frame effect that reads as a crisp flash in the preview barely lights the lamp on a Model 3.
- **Channel 4 is the ramp leader.** On every platform the ramp duration for Channels 4-6 comes from the Channel 4 effect, never from Channel 5 or 6.
- **Brightness is an enum, not a level.** Except on Cybertruck's full-brightness channels, the byte in the `.fseq` selects a documented effect: 0/10/20/30/70/80/90/100 for lights and 0/25/50/75/100 for closures. Anything above 50% is "on". The exact percentages are bound to hotkeys in `xlights_keybindings.xml`.
- **Channel numbers are 1-based** and come from the `StartChannel` attributes in `xlights_rgbeffects.xml` inside the show folder zip. A 48-channel show uses channels 1-46; 200-channel shows add the Cybertruck light bars.
- **`.fseq` files must be V2 uncompressed**, 48 or 200 channels, 15-100 ms frame interval, under 4 hours.

## Conventions

- **`README.md` is the source of truth.** When code encodes vehicle behavior, cite the README section it came from in a comment, and keep the two in sync. If you find the code and the README disagreeing, that is a bug worth raising rather than silently picking one.
- **Standard library only.** `validator.py` is packaged into a standalone executable by `.github/workflows/build.yml`; added dependencies would break that. Tooling targets Python 3.7+.
- **Do not regenerate the show folder zips casually.** They are binary artifacts that authors' existing `.fseq` files depend on. Changing channel assignments silently breaks every show already published.
- **Tests live in `tests/` and use `unittest`** so they run with no install step. Name tests after the behavior they pin, and add a regression test referencing the issue number when fixing a reported bug.
- Match the surrounding prose style in `README.md`: sentence case headings, tables for per-vehicle differences, and `<img>` tags with explicit widths.

## Scope

Changes here affect shows that people run on their own cars. Prefer additive tooling and documentation over changing how existing shows are interpreted. When a vehicle behavior is not documented in `README.md`, say so explicitly rather than inferring it — note the assumption in code and in the pull request instead of presenting it as fact.
