# Getting Started with UV — Setup & Contribution Guide

## What is UV?

[UV](https://docs.astral.sh/uv/) is an **extremely fast** Python package and project manager, written in Rust.  
Think of it as a modern replacement for `pip`, `pip-tools`, `virtualenv`, and `pyenv` — all in one tool.

**Why UV?**
- ⚡ 10–100x faster than pip
- 📦 Manages packages, virtual environments, and Python versions
- 🔒 Generates a lockfile (`uv.lock`) for reproducible installs
- 🤝 Keeps the whole team on the same dependencies with a single command

---

## 1. Install UV

### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Mac / Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> Full installation options → [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)

Verify the installation:
```bash
uv --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/Al-Abdulkarim/multi-agent-codenames.git
cd multi-agent-codenames
```

---

## 3. Install Dependencies

```bash
uv sync
```

That's it. `uv sync` will:
1. Create a `.venv` virtual environment automatically (if it doesn't exist)
2. Install all project dependencies from the lockfile
3. Make sure everyone has the **exact same** packages

---

## 4. Running Python Scripts

### Always use `uv run`

```bash
uv run main.py
uv run run.py
```

### Why not just `python main.py`?

| Scenario | Command | Works? |
|---|---|---|
| venv **NOT** activated | `uv run main.py` | ✅ uv handles the environment automatically |
| venv **NOT** activated | `python main.py` | ❌ uses system Python, wrong packages |
| venv **IS** activated | `python main.py` | ✅ works fine |
| venv **IS** activated | `uv run main.py` | ✅ also works |

### Recommendation → Just use `uv run` always, because:

- No need to remember to activate the venv
- Works the same on every machine
- Your teammates don't have to think about it

So instead of:
```bash
python main.py
python run.py
```

Just:
```bash
uv run main.py
uv run run.py
```

It's the "uv way" and keeps things consistent across the whole team. 🎯

---

## 5. Adding a New Library

To add a new dependency to the project:

```bash
uv add <package-name>
```

For example:
```bash
uv add requests
```

This will:
1. Install the package
2. Add it to `pyproject.toml`
3. Update the lockfile (`uv.lock`)

To add a dev-only dependency:
```bash
uv add --dev pytest
```

To remove a package:
```bash
uv remove <package-name>
```

---

## Quick Reference

| Task | Command |
|---|---|
| Install UV | See [installation guide](https://docs.astral.sh/uv/getting-started/installation/) |
| Clone repo | `git clone https://github.com/Al-Abdulkarim/multi-agent-codenames.git` |
| Install dependencies | `uv sync` |
| Run a script | `uv run main.py` |
| Add a package | `uv add <package>` |
| Remove a package | `uv remove <package>` |
