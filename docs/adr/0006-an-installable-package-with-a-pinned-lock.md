# An installable package with a pinned lock

The tool ran from a clone through `main.py`, which added `src/` to `sys.path`
by hand, and its dependencies were ranges in `requirements.txt`: two builds a
month apart could ship different libraries. Decision (2026-09-15):
`pyproject.toml` declares the package, the dependency ranges the code supports
and the `androidcontextdeploy` command; `requirements.txt` becomes the exact
lock that CI and the release install, and `requirements-dev.txt` adds the
tools. Installing from a clone is `pip install -r requirements.txt -e .`.

## Considered Options

- uv and `uv.lock` — faster and cross-platform, but it makes uv a requirement
  for every contributor, for a lock of fifteen packages.
- pip-tools (`requirements.in` compiled to `requirements.txt`) — one more tool
  for what a `pip freeze` in a clean virtual environment already gives.
- Keeping the `sys.path` line — rejected: the tool was not installable, and
  every entry point had to repeat it.

## Consequences

- Only an editable install is supported: `app_root()` looks for `deploy.json`,
  `locales/` and `scrcpy_server/` next to the source tree, or next to the frozen
  executable — never in `site-packages`.
- The lock is for Python 3.12, the version CI and the release use. Packages only
  one platform needs (colorama, pefile on Windows) are resolved by pip.
- Dependabot opens a weekly pull request for the lock and the GitHub Actions,
  and CI has to pass before it is merged.
