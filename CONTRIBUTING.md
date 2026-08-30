# Contributing

Thanks for your interest in contributing to this project! Contributions are welcome and appreciated. To make collaboration smooth, please follow these guidelines.

## How to contribute

1. Fork the repository and create a feature branch.
2. Make your changes in a clearly named branch (e.g., `fix/export-naming` or `feat/add-step-through-ui`).
3. Write clear commit messages and keep changes focused.
4. Open a Pull Request describing what you changed and why.

## Reporting issues

- Search existing issues before opening a new one.
- Provide clear steps to reproduce, expected vs actual behavior.

## Coding style

- Keep functions small and add comments for non-obvious logic.
- Keep the `print/stl`, `print/png` folder structure when changing the mechanics (as used by my Fusion plugins, see other project in my GitHub space).
- For `pipeline/` code, `.github/copilot-instructions.md` is the source of
  truth: English-only comments/docstrings, type hints on every signature,
  Google-style docstrings. A PR with non-English comments/docstrings will be
  asked to fix them before merge.

## Testing

Run `.venv/bin/pytest pipeline/tests/ -v` before opening a PR — it must pass.
For hardware or firmware changes, also include manual testing steps (which of
the `testing.md` cases you ran) and photos where appropriate.

The full test and commissioning procedure (hardware sketches, GRBL integration,
pipeline tests, end-to-end plot) is in [testing.md](testing.md). Known open
issues are tracked in [TODO.md](TODO.md).

## Licensing of contributions

This repo is licensed per component (see the README "License" section). By
submitting a contribution you agree it is released under the license of the
area you touch: **GPL-3.0-or-later** for `firmware/`, **MIT** for `pipeline/`,
**CC BY-SA 4.0** for hardware design and documentation. Keep the SPDX headers
in `firmware/` sources intact.
