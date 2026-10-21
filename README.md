# repo-review
## Notes

- **Test fixtures.** `backend/analysis/fixtures/*.json` are raw GitHub API
  responses, recorded once. Each file stores `recorded_at`, which the smoke
  tests use as "now". Email addresses are replaced by a short hash (the same
  address always gives the same hash). Earlier commits on this branch contain
  the original addresses; they are public via the GitHub API anyway.
