# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
from typing import Any

import pytest

from hermeto.core.errors import InvalidLockfileFormat, LockfileNotFound, UnsupportedFeature
from hermeto.core.package_managers.javascript.pnpm.project import PnpmLock, parse_packages

# Since pnpm 12, a lockfile may be a stream of two documents: a leading "env"
# document for the project's config dependencies and pinned package manager,
# followed by the project's own dependency graph. https://pnpm.io/lockfile
TWO_DOCUMENT_LOCKFILE = """\
---
lockfileVersion: '9.0'
importers:
  .:
    packageManagerDependencies:
      pnpm:
        specifier: 12.11.2
        version: 12.11.2
packages:
  pnpm@12.11.2:
    resolution: {integrity: sha512-pnpm}
snapshots:
  pnpm@12.11.2: {}
---
lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      is-number:
        specifier: 7.0.0
        version: 7.0.0
packages:
  is-number@7.0.0:
    resolution: {integrity: sha512-isnumber}
snapshots:
  is-number@7.0.0: {}
"""

SINGLE_DOCUMENT_LOCKFILE = """\
lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      is-number:
        specifier: 7.0.0
        version: 7.0.0
packages:
  is-number@7.0.0:
    resolution: {integrity: sha512-isnumber}
snapshots:
  is-number@7.0.0: {}
"""


def write_lockfile(tmp_path: Path, content: str) -> Path:
    lockfile = tmp_path / "pnpm-lock.yaml"
    lockfile.write_text(content)
    return lockfile


class TestPnpmLock:
    def test_from_dir_fails_with_missing_pnpm_lock(self, tmp_path: Path) -> None:
        with pytest.raises(LockfileNotFound):
            PnpmLock.from_dir(tmp_path)

    def test_from_file_fails_with_invalid_yaml(self, tmp_path: Path) -> None:
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(":")
        with pytest.raises(InvalidLockfileFormat):
            PnpmLock.from_file(lockfile)

    @pytest.mark.parametrize(
        ("data", "exc"),
        [
            pytest.param(
                {"lockfileVersion": "1000.0"}, UnsupportedFeature, id="unsupported_version_str"
            ),
            pytest.param(
                {"lockfileVersion": 1000.0}, UnsupportedFeature, id="unsupported_version_float"
            ),
            pytest.param({}, InvalidLockfileFormat, id="missing_version"),
        ],
    )
    def test_pnpm_lock_version_validation_fails(
        self, tmp_path: Path, data: dict[str, Any], exc: type[Exception]
    ) -> None:
        with pytest.raises(exc):
            PnpmLock(path=tmp_path, data=data)

    def test_from_file_fails_with_an_empty_lockfile(self, tmp_path: Path) -> None:
        # Reading the stream rather than a single document must not turn the
        # empty file into a crash on a missing key. The actionable part of the
        # message lives in .solution, which str(exc) does not include.
        with pytest.raises(InvalidLockfileFormat) as exc_info:
            PnpmLock.from_file(write_lockfile(tmp_path, ""))
        assert exc_info.value.solution == (
            "The pnpm-lock.yaml file must contain a lockfileVersion field."
        )

    @pytest.mark.parametrize(
        ("content", "expected_ids"),
        [
            pytest.param(SINGLE_DOCUMENT_LOCKFILE, {"is-number@7.0.0"}, id="single_document"),
            pytest.param(
                TWO_DOCUMENT_LOCKFILE,
                {"pnpm@12.11.2", "is-number@7.0.0"},
                id="two_documents",
            ),
        ],
    )
    def test_from_file_reads_packages_from_every_document(
        self, tmp_path: Path, content: str, expected_ids: set[str]
    ) -> None:
        lockfile = PnpmLock.from_file(write_lockfile(tmp_path, content))
        assert set(lockfile.packages) == expected_ids

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(SINGLE_DOCUMENT_LOCKFILE, id="single_document"),
            pytest.param(TWO_DOCUMENT_LOCKFILE, id="two_documents"),
        ],
    )
    def test_from_file_takes_the_dependency_graph_from_the_last_document(
        self, tmp_path: Path, content: str
    ) -> None:
        lockfile = PnpmLock.from_file(write_lockfile(tmp_path, content))
        assert lockfile.direct_dependencies == ["is-number@7.0.0"]

    def test_from_file_keeps_the_env_document(self, tmp_path: Path) -> None:
        lockfile = PnpmLock.from_file(write_lockfile(tmp_path, TWO_DOCUMENT_LOCKFILE))
        assert lockfile.env["importers"]["."]["packageManagerDependencies"] == {
            "pnpm": {"specifier": "12.11.2", "version": "12.11.2"}
        }

    def test_from_file_has_no_env_document_for_a_single_document_lockfile(
        self, tmp_path: Path
    ) -> None:
        lockfile = PnpmLock.from_file(write_lockfile(tmp_path, SINGLE_DOCUMENT_LOCKFILE))
        assert lockfile.env == {}

    def test_parse_packages_version_field_overrides_version_from_id(self, tmp_path: Path) -> None:
        lockfile = PnpmLock(
            path=tmp_path / "pnpm-lock.yaml",
            data={
                "lockfileVersion": "9.0",
                "packages": {
                    "repo@https://codeload.github.com/org/repo/tar.gz/abc123": {
                        "version": "1.0.0",
                        "resolution": {
                            "tarball": "https://codeload.github.com/org/repo/tar.gz/abc123"
                        },
                    }
                },
            },
        )
        packages = parse_packages(lockfile)
        assert packages[0].version == "1.0.0"
        assert packages[0].url == "https://codeload.github.com/org/repo/tar.gz/abc123"
