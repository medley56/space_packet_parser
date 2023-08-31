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

## Release Process
Reference: [https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow)

1. Create a release candidate branch named according to the version to be released. This branch is used to polish
   the release while work continues on dev (towards the next release). The naming convention is `release/X.Y.Z`

2. Bump the version of the package to the version you are about to release, either manually by editing `pyproject.toml`
   or by running `poetry version X.Y.Z` or bumping according to a valid bump rule like `poetry version minor`
   (see poetry docs: https://python-poetry.org/docs/cli/#version).

3. Update the version identifier in `CITATION.cff`.

4. Update `changelog.md` to reflect that the version is now "released" and revisit `README.md` to keep it up to date.
   
5. Open a PR to merge the release branch into master. This informs the rest of the team how the release 
   process is progressing as you polish the release branch.

6. When you are satisfied that the release branch is ready, merge the PR into `master`. 

7. Check out the `master` branch, pull the merged changes, and tag the newly created merge commit with the 
   desired version `X.Y.Z` and push the tag upstream. 
   
   ```bash
   git tag -a X.Y.Z -m "version release X.Y.Z"
   git push origin X.Y.Z
   ```
   
8. Ensure that you have `master` checked out and build the package (see below).
   Check that the version of the built artifacts is as you expect (should match the version git tag and the 
   output from `poetry version --short`).
   
9. Optionally distribute the artifacts to PyPI/Nexus if desired (see below).
   
10. Open a PR to merge `master` back into `dev` so that any changes made during the release process are also captured
    in `dev`. 


## Building and Distribution
1. Ensure that `poetry` is installed by running `poetry --version`.
   
2. To build the distribution archives, run `poetry build`.
   
3. To upload the wheel to Nexus, run `poetry publish`. You will need credentials to sign into PyPI.
