# GitHub Copilot Instructions for Plotter Project

Known open issues for the project are tracked in [`../TODO.md`](../TODO.md).

**Language**: English (all code comments, docstrings, and documentation must be in English)

**Project Type**: Image-to-GCode Pipeline
**Primary Tech**: Python 3.13, vpype 1.15.0, vpype-gcode 0.13.0, PyGrbl_Streamer

## Code Style (Non-Negotiable)

**Language**: ALL code, comments, docstrings must be **English**. No German, no other languages in code.

**Type Hints**: Always required for parameters and return values
```python
def load_toml(path: Path) -> dict[str, Any]:  # ✅ Good
def load_toml(path):  # ❌ Bad
```

**Naming**: `snake_case.py`, `PascalCase` classes, `snake_case()` functions, `UPPER_SNAKE_CASE` constants

**Imports**: Standard library → Third-party → Local imports

**Docstrings**: Google-style, English only (see `pipeline/README.md` for architecture details)

## Testing

**Command**: `.venv/bin/pytest pipeline/tests/ -v`
**Target**: All tests must pass before committing
**Location**: `pipeline/tests/`
**Commissioning context**: `../testing.md` → Phase 3

## When to Create New Code

### Adding a Pipeline Step

1. Create `pipeline/steps/my_step.py` with `MyStep` class (inherit `PipelineStep`)
2. Implement `process(self, ctx: ImageContext) -> ImageContext`; set a
   `name = "..."` class attribute (human-readable, shown in logs / GUI progress)
3. Add entry to `STEP_REGISTRY` in `pipeline/core/registry.py`
4. Create `pipeline/tests/test_my_step.py` with unit tests
5. Run `.venv/bin/pytest pipeline/tests/ -v` — all tests must pass
6. **Update `pipeline/README.md`** with new step documentation

For detailed step parameters and architecture, see **`pipeline/README.md`**.

### Adding a Config Key

1. Add to target step's docstring
2. Add to test config in test file
3. Handle in step's `process()` method
4. Test: `.venv/bin/pytest pipeline/tests/ -v`
5. **Update `pipeline/README.md`** if new capability

## Dependencies

**Python Version**: 3.13 (required by vpype 1.15.x; use `python3.13 -m venv .venv`)

All dependencies are declared in `pipeline/pyproject.toml` — core
`dependencies` plus the `gui`, `diffusers` and `dev` optional-dependency
groups. Install with `pip install -e "pipeline/[gui]"` (add `,diffusers` /
`,dev` as needed). There is no `requirements.txt`.

## Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Detailed diagnostic info")
logger.info("Important state change")
logger.warning("Unexpected but handled")
logger.error("Error requiring attention")
```

## Git Workflow

**Commits**: Conventional format
- `feat:` new feature
- `fix:` bugfix
- `refactor:` code cleanup
- `docs:` documentation
- `test:` test additions
- `chore:` dependency/config updates

**Example**: `feat: add linesort optimization to GCodeFromSvgStep`

**Before Commit**:
1. Run `.venv/bin/pytest pipeline/tests/ -v`
2. Confirm all tests pass
3. No German comments/docstrings in code
4. All new functions have English docstrings with type hints

## Pipeline Documentation

**Reference**: `pipeline/README.md` — Complete architecture & usage guide

This document describes:
- Data flow (ImageContext, intermediates)
- All 7 stylization backends and their config keys
- Vectorization algorithm and parameters
- GCode generation (native vpype vs legacy)
- GRBL hardware integration
- Custom step development
- Performance tips
- Troubleshooting

**IMPORTANT for Pipeline Changes**:
When adding, modifying, or removing pipeline steps:
1. **Update `pipeline/README.md`**:
   - Add new step to appropriate section
   - Document all config keys with type/default/description
   - Update "Available Steps" table
   - Add examples if new capability
2. **Update `pipeline/core/registry.py`**:
   - Add import + STEP_REGISTRY entry
3. **Create tests** in `pipeline/tests/test_<step_name>.py`
4. **Update** this file if behavior changes significantly

Example: Adding a new stylizer
```markdown
# In pipeline/README.md, under "Available Steps"
| `stylise_mymethod` | Custom algorithm | numpy, pillow | Quality description |

# In config keys section
| Key | Type | Default | Description |
| `my_param` | float | 0.5 | What this controls |
```

## Troubleshooting

### "vpype not found"
→ Activate venv: `source .venv/bin/activate` or use `.venv/bin/python`

### "AttributeError: page_size"
→ This is a Pylance type system artifact. Code works correctly at runtime. Ignore if tests pass.

### Tests failing after changes
→ Most likely: German text in new docstrings or missing English comments
→ Run: `.venv/bin/pytest pipeline/tests/ -v` to see exact failure

### New code not being imported
→ Check: `pipeline/core/registry.py` — is your step registered?

## Quick Checklist for Any Changes

- [ ] All code is in English (comments, docstrings, variables)
- [ ] Type hints on all function signatures
- [ ] Google-style docstrings
- [ ] No unused imports
- [ ] `.venv/bin/pytest pipeline/tests/` passes
- [ ] No hardcoded German text in output/errors
- [ ] If modifying pipeline steps: `pipeline/README.md` updated

---

**Language Rule Enforcement**: Any PR with German comments/docstrings will be rejected. Use English everywhere in code.

