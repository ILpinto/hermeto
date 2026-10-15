# SPDX-License-Identifier: GPL-3.0-only
"""Shared fixtures for the behavior scenarios.

Step definitions live in tests/bdd/steps/ and bind the Gherkin phrases in
features/ to assertions on observable behavior. Keep setup here rather than
in step bodies, and add no per-feature conftest files.
"""

import json
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest import mock

import git
import pytest
import typer.testing

from hermeto.interface.cli import app

# Step modules are not named test_*, so pytest does not rewrite their asserts
# unless asked. Without this a failing scenario reports a bare AssertionError
# instead of naming the packages that are missing.
pytest.register_assert_rewrite("tests.bdd.steps.pnpm_lockfiles")

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_ACTOR = git.Actor("hermeto behavior tests", "noreply@example.com")


async def _write_empty_tarballs(
    files_without_auth: dict[str, Path],
    files_with_auth: dict[str, Path],
    auth: Any = None,
) -> None:
    """Stand in for the real downloader, creating each destination file locally."""
    for destination in (*files_without_auth.values(), *files_with_auth.values()):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"")


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    """Keep every scenario offline.

    Downloads are mocked at the boundary tests/unit/package_managers/javascript/
    pnpm/test_main.py already mocks. Checksums go with them: the stand-in writes
    empty files, which cannot match the integrity hashes the fixtures declare.
    """
    base = "hermeto.core.package_managers.javascript.pnpm.main"
    with (
        mock.patch(f"{base}.async_download_with_auth", new=_write_empty_tarballs),
        mock.patch(f"{base}.must_match_any_checksum"),
    ):
        yield


@pytest.fixture
def scenario_context() -> dict[str, Any]:
    """Carry state between the steps of a single scenario."""
    return {}


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Return the directory hermeto writes its output to."""
    return tmp_path / "output"


@pytest.fixture
def make_pnpm_project(tmp_path: Path) -> Callable[[str], Path]:
    """Return a factory building a git-backed pnpm project from a committed fixture."""

    def _make(shape: str) -> Path:
        source = tmp_path / "source"
        source.mkdir()
        lockfile = FIXTURES_DIR / f"pnpm12-{shape}.yaml"
        source.joinpath("pnpm-lock.yaml").write_bytes(lockfile.read_bytes())
        source.joinpath("package.json").write_text(
            json.dumps({"name": "hermeto-bdd", "version": "1.0.0"}) + "\n"
        )
        repo = git.Repo.init(source)
        repo.create_remote("origin", "https://example.com/hermeto-bdd.git")
        repo.index.add(["package.json", "pnpm-lock.yaml"])
        repo.index.commit("initial", author=_ACTOR, committer=_ACTOR)
        return source

    return _make


@pytest.fixture
def run_hermeto() -> Callable[..., Any]:
    """Return a callable invoking the hermeto CLI in process."""
    runner = typer.testing.CliRunner()

    def _run(*args: str) -> Any:
        return runner.invoke(app, list(args), catch_exceptions=False)

    return _run
