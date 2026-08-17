# PaperDaily v0.5.4

- Refresh immediately when `config.yaml` changes in the local/standalone edition.
- Cancel stale hosted refresh runs when a newer config/code push arrives.
- Distinguish valid zero-record bioRxiv/medRxiv responses from invalid/empty upstream responses.
- Retry arXiv timeouts and connection errors with backoff before using the last-good cache.
