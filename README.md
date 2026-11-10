# hkid-watch

Checks the HK Immigration ID-card appointment quota for one date every 5 minutes
on GitHub Actions and sends a push through ntfy when the set of open offices changes.

- `watch.py`: the check. Stdlib Python. Reads the ntfy topic from `NTFY_TOPIC`.
- `state.json`: last seen open offices, committed back by the workflow when it changes.
- `.github/workflows/watch.yml`: each run loops for about 5 hours and then starts the next one.
  An hourly schedule restarts the chain if it breaks. Cancelled runs in the history are
  hourly restarts that weren't needed. The workflow disables itself after the stop time.

Secret needed: `NTFY_TOPIC`.

Manual run with a test push: Actions tab, hkid-watch, Run workflow.
