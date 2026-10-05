# HDFS authentication for long experiment runs

Initial interactive login:

```bash
experiments/waymo-perception/scripts/refresh-hdfs-auth.sh
```

Install the password-free user timer after that succeeds:

```bash
python experiments/waymo-perception/scripts/install-hdfs-auth-keepalive.py
systemctl --user list-timers sureal-hdfs-auth.timer
cat ~/.local/state/sureal/hdfs-auth/status.json
```

The timer runs every30 minutes. It attempts `kinit -R` on the existing ticket,
then forces Waystone to refresh its restricted-permission token cache. Tool
hashes are pinned. No password is stored or requested unattended; command
output is suppressed and status contains only renewal/result metadata.
The current host issued a10-hour ticket with an approximately24-hour renewable
window. Renewal cannot extend that window indefinitely. After it ends, run the
interactive refresh script again; the timer keeps running and resumes refresh
when a valid renewable ticket exists. Changed pinned tools require reinstalling
the timer after verifying them.

Inspect or stop the timer:

```bash
journalctl --user -u sureal-hdfs-auth.service --no-pager
systemctl --user disable --now sureal-hdfs-auth.timer
```

HDFS artifact writers should use `--auth-source token-file` to consume the fresh
cache rather than a stale token exported in an old shell. A successful keepalive
is not an artifact-retention proof: uploads must still be independently
downloaded and verified before local payload release.
