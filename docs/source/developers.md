# Developer Documentation
## Installing Development Dependencies
Poetry installs dev dependencies by default from the `poetry.lock` or `pyproject.toml` files. Just run 
```bash
poetry install
```

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
GitHub Actions has an automatic release process that responds to pushes of annotated git tags. When a tag matching 
a semantic version (`[0-9]*.[0-9]*.[0-9]*` or `[0-9]*.[0-9]*.[0-9]*rc[0-9]*`) is pushed, a workflow runs that builds
the package, pushes the artifacts to PyPI, and creates a GitHub Release from the distributed artifacts. Release notes 
are automatically generated from commit history and the Release name is taken from the annotation on the tag.

To trigger a release, push a tag reference to the commit you want to release, like so:

```bash
git tag -a X.Y.Z -m "Version X.Y.Z"
git push origin X.Y.Z
```

To tag and publish a Release Candidate, your tag should look like the following:

```bash
git tag -a X.Y.Zrc1 -m "Release Candidate X.Y.Zrc1"
git push origin X.Y.Zrc1
```

Release candidate tags are always marked as Prereleases in GitHub and release notes are generated from the latest
non-prerelease Release.

**For production releases, tags should always reference commits in the `main` branch. Release candidates are less 
important and tags can reference any commit.**
