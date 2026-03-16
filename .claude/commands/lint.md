Run Ruff (lint + format check) and Ty (type check) against the src/ directory.

```bash
uv run --group lint ruff check src/ && \
uv run --group lint ruff format --check src/ && \
uv run --group lint ty check src/
```

If Ruff reports fixable issues, run `uv run --group lint ruff check --fix src/` to auto-fix them.
If Ruff format reports differences, run `uv run --group lint ruff format src/` to apply formatting.
Report a summary of all issues found, grouped by tool.
