# hkid-watch

Checks the HK Immigration ID-card appointment quota for one date every 10 minutes
on GitHub Actions and sends a push through ntfy when the set of open offices changes.

- `watch.py`: the check. Stdlib Python. Reads the ntfy topic from `NTFY_TOPIC`.
- `state.json`: last seen open offices, committed back by the workflow when it changes.
- `.github/workflows/watch.yml`: schedule, manual trigger, and auto-stop.

Secret needed: `NTFY_TOPIC`.

Manual run with a test push: Actions tab, hkid-watch, Run workflow.
