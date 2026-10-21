# repo-review
## Notes

- **Test fixtures.** `backend/analysis/fixtures/*.json` are raw GitHub API
  responses, recorded once. Each file stores `fetched_at`, which the smoke
  tests use as "now". Author emails are replaced by stable hashes (the same
  address always gives the same hash).
- **Responsiveness limitation.** The median close time counts every issue
  closed in the last 90 days, whenever it was opened. One release that closes a
  batch of long-standing issues can dominate the median and make a healthy
  project look slow.
