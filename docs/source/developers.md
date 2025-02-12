# Developer Documentation

## Installing Development Dependencies

Poetry installs dev dependencies by default from the `poetry.lock` or `pyproject.toml` files.

```bash
poetry install
```

Alternatively, if you are using something other than Poetry for development you can install from
the `dev` extras group.

```bash
pip install ".[dev]"
```

Once the development dependencies are installed, you can run

```bash
pre-commit install
```

to get pre-commit hooks to automatically run the linting and formatting checks for you before each commit.

## Testing
Testing is run with `pytest` and the order is randomized by `pytest-randomly`.
To run all tests, run
```bash
pytest tests
```

To run all tests in docker containers (tests against many versions of python), run
```bash
docker-compose up --build && docker-compose down
```

## Building Documentation with Sphinx
Documentation is automatically built on ReadTheDocs in response to every PR and release,
but you can also build it locally with:
```bash
# From docs directory
make html && open build/html/index.html
```

## Making a Pull Request
Feel free to fork this repo and submit a PR!
- If you are working on an issue, link your PR to that issue.
- All PRs should be destined for the `main` branch (trunk-based development).
- Reviews are required before merging and our automated tests must pass.
- Please fill out the PR template that is populated when creating a PR in the GitHub interface.

## Release Process
Releases are automatically created using a GitHub Actions workflow that responds to pushes of annotated git tags.

### Versioning
Version numbers must be PEP440 strings: https://peps.python.org/pep-0440/

That is,
```
[N!]N(.N)*[{a|b|rc}N][.postN][.devN]
```

### Preparing for Release
1. Create a release candidate branch named according to the version to be released. This branch is used to polish
   the release but is fundamentally not different from any other feature branch in trunk-based development.
   The naming convention is `release/X.Y.Z`.

2. Bump the version of the package to the version you are about to release, either manually by editing `pyproject.toml`
   or by running `poetry version X.Y.Z` or bumping according to a valid bump rule like `poetry version minor`
   (see poetry docs: https://python-poetry.org/docs/cli/#version).

3. Update the version identifier in `CITATION.cff`.

4. Update `changelog.md` to reflect that the version is now "released" and revisit `README.md` to keep it up to date.

5. Open a PR to merge the release branch into main. This informs the rest of the team how the release
   process is progressing as you polish the release branch. You may need to rebase the release branch onto
   any recent changes to `main` and resolve any conflicts on a regular basis.

6. When you are satisfied that the release branch is ready, merge the PR into `main`.

7. Check out the `main` branch, pull the merged changes, and tag the newly created merge commit with the
   desired version `X.Y.Z` and push the tag upstream.

### Automatic Release Process
We use GitHub Actions for automatic release process that responds to pushes of git tags. When a tag matching
a semantic version (`[0-9]+.[0-9]+.[0-9]+*` or `test-release/[0-9]+.[0-9]+.[0-9]+*`) is pushed,
a workflow runs that builds the package, pushes the artifacts to PyPI or TestPyPI
(if tag is prefixed with `test-release`),
and creates a GitHub Release from the distributed artifacts. Release notes
are automatically generated from commit history and the Release name is taken from the basename of the tag.

#### Official Releases
Official releases are published to the public PyPI (even if they are release candidates like `1.2.3rc1`). This differs
from test releases, which are only published to TestPyPI and are not published to GitHub at all.
If the semantic version has any suffixes (e.g. `rc1`), the release will be marked as
a prerelease in GitHub and PyPI.

To trigger an official release, push a tag referencing the commit you want to release. The commit _MUST_ be on
the `main` branch. Never publish an official release from a commit that hasn't been merged to `main`!

```bash
git checkout main
git pull
git tag -a X.Y.Z -m "Version X.Y.Z"
git push origin X.Y.Z
```

#### Test Releases
Test releases are published to TestPyPI only and are not published on GitHub. Test releases are triggered by tags
prefixed with `test-release`.

To publish a test release, prefix the tag with `test-release`. This will prevent any publishing to the public PyPI
and will prevent the artifacts being published on GitHub.

```bash
git checkout <ref-to-test-release-from>
git pull
git tag -a test-release/X.Y.Zrc1 -m "Test Release Candidate X.Y.Zrc1"
git push origin test-release/X.Y.Zrc1
```

#### Prereleases
Unless the pushed tag matches the regex `^[0-9]*\.[0-9]*\.[0-9]*`, the release will be marked as a
prerelease in GitHub. This allows "official" prereleases of suffixed tags.

#### Release Notes Generation
Release notes are generated based on commit messages since the latest non-prerelease Release.
