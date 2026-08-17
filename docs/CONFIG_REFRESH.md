# Refresh behavior after editing `config.yaml`

PaperDaily treats `config.yaml` as an active runtime configuration, not a file that is only read at the next scheduled update.

## Hosted GitHub edition

A commit that changes `config.yaml` on `master` immediately triggers the `Daily literature refresh` workflow. If an older refresh is still running, it is cancelled because it was started with stale configuration, and the newest configuration is used by the replacement run.

## Local / standalone edition

With the default settings:

```yaml
local:
  refresh_mode: scheduled
  scheduler_enabled: true
  scheduler_check_seconds: 30
  refresh_on_config_change: true
```

PaperDaily calculates a SHA-256 fingerprint of `config.yaml` after every successful refresh. While the app is running, the scheduler reloads the configuration periodically. If the fingerprint changes, PaperDaily immediately runs the full retrieval, filtering, AI ranking, and summary pipeline instead of waiting for the next scheduled time slot.

The successful fingerprint is stored in `local_state.json`. This means a changed configuration is also detected on the next application launch if PaperDaily was closed when the file was edited.

`refresh_mode: never` remains authoritative and disables automatic refreshes, including configuration-triggered refreshes.
