# Isolated Google Cloud CLI bootstrap

The executable wizard is `../setup-gcs.sh`; the reusable command wrapper is
`../gcs.sh`. Scope: Linux x86_64. It needs host Bash, curl, tar, sha256sum, flock,
and standard POSIX utilities. CLI/Python versions and credential configuration
are isolated; the host kernel, libc, CA certificates and bootstrap utilities
remain host dependencies. This is not an OS container.

The wrapper downloads the exact `587.0.0` archive over HTTPS, checks its pinned
SHA-256 before extraction, and promotes the installation under a lock. It uses
bundled Python `3.14.7`, launches the CLI with a cleared environment, and keeps
its HOME, temp directory and `CLOUDSDK_CONFIG` beneath `GCS_TOOL_ROOT`. Only
explicit proxy settings carry over. Google CLI/site-package override variables,
Python paths and global Google credential settings do not carry over. Shell
startup files and the Surflo Python environment are not changed.

Default tool root: `${XDG_CACHE_HOME:-$HOME/.cache}/sureal/gcs`.
Credential configuration: `{tool_root}/config`, mode 0700. Override the tool root
with an absolute `GCS_TOOL_ROOT` consistently for setup and subsequent commands.
This tooling root does not choose the dataset cache or its budget.

## Artifact verification, 2026-09-29

[Google's installation page](https://docs.cloud.google.com/sdk/docs/install-sdk)
published release `587.0.0` with the unversioned Linux x86_64 archive checksum:

```text
96c99c1ca5defa34776cd3a3888626c567e8b7ac9f9d2944fa62d16d522b98ac
```

The exact versioned artifact is
`https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-587.0.0-linux-x86_64.tar.gz`,
with locally measured pinned SHA-256:

```text
57df2448d259c654796a3703af8e5b53a02d439715b2034d6bb811efc2d6dd7b
```

Those compressed archives differ. The versioned payload was verified against
the official-checksum-verified unversioned release: all 33,544 entry names,
types, modes, links, sizes and file-content digests matched. The versioned
archive's `VERSION` was `587.0.0`. The wrapper pins that exact versioned digest;
it never learns a checksum at runtime or follows a latest-release URL.

The real bootstrap and CLI info commands passed using bundled Python and the
dedicated config directory. Authentication was not run by the agent. The wizard
guides the human through the [Waymo access page](https://waymo.com/open/download/)
and Google's [remote sign-in flow](https://docs.cloud.google.com/sdk/docs/authenticate),
then lists the v2 bucket to verify access. It accepts no terms automatically and
downloads no dataset payloads.
