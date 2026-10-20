# https://github.com/hermetoproject/hermeto/issues/1802
Feature: pnpm multi-document lockfiles

  Since pnpm 12 a pnpm-lock.yaml may be a stream of two YAML documents: a
  leading env document recording the project's config dependencies and its
  pinned package manager, followed by the project's own dependency graph. Both
  documents declare the same lockfileVersion, and both name packages that pnpm
  installs. Hermeto must read every document, report and fetch every package
  the lockfile installs, and preserve the stream when it rewrites the lockfile
  for the hermetic build.

  Scenario: A two-document lockfile is accepted
    Given a project with a pnpm lockfile holding an env document and a dependency graph
    When hermeto fetches the pnpm dependencies
    Then the fetch succeeds

  Scenario: The SBOM covers packages from both documents
    Given a project with a pnpm lockfile holding an env document and a dependency graph
    When hermeto fetches the pnpm dependencies
    Then the SBOM lists every package declared in the lockfile
    And the SBOM lists the pinned package manager declared in the env document

  Scenario: Packages from the env document are available for the hermetic build
    Given a project with a pnpm lockfile holding an env document and a dependency graph
    When hermeto fetches the pnpm dependencies
    Then every package declared in the env document resolves to a local tarball
