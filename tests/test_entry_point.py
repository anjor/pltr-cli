"""The `pltr` executable (pltr.cli:main) and `python -m pltr` entry points."""

import json
import subprocess
import sys

import pytest

from pltr import __version__
from pltr.cli import main
from pltr.config.settings import Settings


def test_pltr_executable_resolves_aliases(isolated_home, monkeypatch, capsys):
    """Aliases work from the console script, not only from `python -m pltr`."""
    config_dir = Settings().config_dir
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "aliases.json").write_text(json.dumps({"ver": "--version"}))
    monkeypatch.setattr(sys, "argv", ["pltr", "ver"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    assert f"pltr {__version__}" in capsys.readouterr().out


def test_main_without_aliases_runs_the_cli(isolated_home, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pltr", "--version"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    assert f"pltr {__version__}" in capsys.readouterr().out


def test_python_dash_m_pltr(isolated_home):
    result = subprocess.run(
        [sys.executable, "-m", "pltr", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert f"pltr {__version__}" in result.stdout
