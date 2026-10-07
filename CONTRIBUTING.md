# Contributing

Thanks for helping. The easiest contributions are **issues**: bugs, ideas and especially
**map corrections** from people at MCEC (room positions and walking times are estimates traced from
MCEC's published plans). Use the Feedback links in the planner; they pre-fill the page, device and version.

## Code changes

```powershell
pip install -r requirements.txt
python tools/build.py          # -> dist/public; open dist/public/index.html
python tools/build.py --check  # the same content check CI runs
```

- The whole app is `src/planner.html` (HTML, CSS and JavaScript in one file, no framework or build step
  beyond `tools/build.py` filling in the `/*@NAME@*/` placeholders).
- Keep changes small and test on a phone-sized window as well as desktop.
- The native app in `mobile/` calls some page functions and clicks some page elements by name.
  `tests/test_app_contract.py` lists them and runs in CI (`python -m pytest tests -q`): if it fails,
  either keep the old name or update `mobile/` in the same PR.

## Please don't add

- **Session abstracts** (AISA's text) or **floor-plan images** (MCEC's artwork). The public build links to
  the official pages and loads MCEC's own guide instead. CI fails if either appears.
- Third-party scripts, trackers or anything that sends a user's plan off their device.

By contributing you agree your code is released under the [MIT licence](LICENSE).
