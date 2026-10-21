# repo-review
## Notes

- **Test fixtures.** `backend/analysis/fixtures/*.json` are raw GitHub API
  responses, recorded once. Each file stores `recorded_at`, which the smoke
  tests use as "now". Email addresses are replaced by a short hash (the same
  address always gives the same hash). Earlier commits on this branch contain
  the original addresses; they are public via the GitHub API anyway.
- **Responsiveness limitation.** The median close time counts every issue
  closed in the last 90 days, whenever it was opened. One release that closes a
  batch of long-standing issues can dominate the median and make a healthy
  project look slow.
