This document is a work in progress. PRs are welcome.

### Tests

Tests are currently covering:

 - tools like shell and Python
 - integration tests that make LLM calls, run the generated code, and checks the output
   - this could be used as a LLM eval harness

There are also some integration tests in `./tests/test-integration.sh` for an alternative way to test.


### Release

To make a release, simply run `gh release create v0.0.0` (with the correct version number) and CI will publish the package to PyPI.
