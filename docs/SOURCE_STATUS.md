# Source status semantics

PaperDaily distinguishes a valid empty result from an upstream source failure.

- A successful API response with zero matching records is reported as `0 records` and is not a source issue.
- An empty response body, invalid JSON/HTML response, HTTP error, connection error, or timeout is a source issue.
- When a last-good source cache is available, PaperDaily may continue the daily issue using cached records while still reporting that the upstream source was unavailable.

For arXiv, transient HTTP 429/5xx responses, connection errors, and read timeouts are retried with configured backoff before the last-good cache fallback is used.
