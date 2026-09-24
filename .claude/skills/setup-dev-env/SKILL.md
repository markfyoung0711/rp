---
name: setup-dev-env
description: Set up the development environment for this project. Triggered by phrases like "setup env", "set up environment", "setup dev environment", "initialize environment", "bootstrap project", "get this running", "prepare dev env", or "configure environment".
allowed-tools: Read, Glob, Grep, Bash, Write, Edit
---

# Set Up Dev Environment

Set up the development environment for this construction bid ML project end-to-end.

## Steps

1. **Check for `uv`** — this project uses `uv` for environment management:
   - If `uv` is not installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Then: `export PATH="$HOME/.local/bin:$PATH"`

2. **Create the virtual environment** (Python 3.11+):
   - If `.venv/` does not exist: `uv venv .venv --python 3.11`
   - If `.venv/` already exists: skip and report it

3. **Install dependencies** from `pyproject.toml`:
   - Run: `uv sync`
   - This installs all project dependencies plus dev dependencies (pytest, black, ruff)

4. **Check for `.env` file**:
   - If `.env` does not exist, create it with a placeholder:
     ```
     ANTHROPIC_API_KEY=your_key_here
     ```
   - Remind the user to fill in their Anthropic API key (used as fallback PDF parser)

5. **Verify the setup**:
   - Run: `uv run python -c "import pdfplumber, pandas, xgboost, streamlit, shap; print('OK')"`
   - Report success or any import errors

6. **Report** what was done and remind the user how to activate the environment:
   ```
   source .venv/bin/activate
   ```

## Notes

- This is a construction bid ML project. Key dependencies: `pdfplumber`, `pandas`, `numpy`,
  `scikit-learn`, `xgboost`, `shap`, `streamlit`, `anthropic`, `jupyter`.
- Never commit `.venv/`, `.env`, `data/raw/`, `data/extracted/`, or `models/*.pkl`.
- Do NOT use `set -e` in any setup scripts that may be sourced — sourcing a script
  with `set -e` will cause the user's current shell to exit on any error.
- Use `uv sync` rather than `pip install` — the lockfile (`uv.lock`) ensures
  reproducible installs.
- If a `data/` directory structure is missing, create the skeleton:
  `data/raw/idot-wctb-unit-price-tabs/`, `data/raw/idot-wctb-contract-details/`,
  `data/staged/`, `data/warehouse/`, `data/reference/`
