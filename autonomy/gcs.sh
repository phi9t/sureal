#!/usr/bin/env bash
# Pinned GCS bootstrap. Host prerequisites: Linux x86_64, Bash, curl, tar,
# sha256sum, flock, and standard POSIX utilities. No pip or sudo required.
set -euo pipefail
umask 077

usage() {
    cat <<'EOF'
Usage: gcs.sh install|auth|check|-- GCLOUD_ARGUMENTS...

  install  Download, SHA-256 verify, and stage the pinned CLI and bundled Python
  auth     Interactive Google login using a browser on another machine
  check    List the Waymo Perception v2 bucket to verify access
  -- ...   Run gcloud with this isolated runtime and credential configuration

GCS_TOOL_ROOT overrides the absolute tool/config directory.
Default: ${XDG_CACHE_HOME:-$HOME/.cache}/sureal/gcs
Dataset storage remains a separate Waystone-owned policy.
EOF
}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
MODE="${1:---help}"
case "$MODE" in
    -h|--help) usage; exit 0 ;;
    install|auth|check|--) shift ;;
    *) usage >&2; exit 2 ;;
esac
if [[ "$MODE" == -- ]]; then
    [[ $# -gt 0 ]] || die 'provide gcloud arguments after --'
else
    [[ $# == 0 ]] || die 'unexpected arguments'
fi
if [[ "$MODE" == auth ]]; then
    [[ -t 0 && -t 1 ]] || die 'run auth directly in an interactive terminal'
fi
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] \
    || die 'this pinned bundle supports Linux x86_64 only'

VERSION=587.0.0
ARCHIVE_NAME="google-cloud-cli-${VERSION}-linux-x86_64.tar.gz"
# Versioned archive digest; payload verified against the published latest-release
# checksum on 2026-09-29. See research/gcs-bootstrap.md.
ARCHIVE_SHA256=57df2448d259c654796a3703af8e5b53a02d439715b2034d6bb811efc2d6dd7b
ARCHIVE_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/${ARCHIVE_NAME}"
TOOL_ROOT="${GCS_TOOL_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/sureal/gcs}"
[[ "$TOOL_ROOT" == /* ]] || die 'GCS_TOOL_ROOT must be an absolute path'
SDK_PARENT="${TOOL_ROOT}/sdk/${VERSION}"
SDK="${SDK_PARENT}/google-cloud-sdk"
ARCHIVE="${TOOL_ROOT}/downloads/${ARCHIVE_NAME}"
INSTALL_TMP=""
DOWNLOAD_TMP=""
cleanup() {
    [[ -z "$INSTALL_TMP" ]] || rm -rf -- "$INSTALL_TMP"
    [[ -z "$DOWNLOAD_TMP" ]] || rm -f -- "$DOWNLOAD_TMP"
    return 0
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for tool in curl tar sha256sum flock env; do
    command -v "$tool" >/dev/null || die "missing host prerequisite: ${tool}"
done
mkdir -p -- "$TOOL_ROOT"
chmod 700 -- "$TOOL_ROOT"
exec 9>"${TOOL_ROOT}/install.lock"
flock 9

if [[ ! -d "$SDK_PARENT" ]]; then
    mkdir -p -- "${TOOL_ROOT}/downloads" "${TOOL_ROOT}/sdk"
    if [[ ! -f "$ARCHIVE" ]]; then
        printf 'Downloading Google Cloud CLI %s (88 MB)...\n' "$VERSION" >&2
        DOWNLOAD_TMP="$(mktemp "${TOOL_ROOT}/downloads/.download-XXXXXX")"
        curl --fail --location --retry 3 --connect-timeout 30 \
            --proto '=https' --proto-redir '=https' \
            --output "$DOWNLOAD_TMP" "$ARCHIVE_URL"
        mv -- "$DOWNLOAD_TMP" "$ARCHIVE"
        DOWNLOAD_TMP=""
    fi
    printf '%s  %s\n' "$ARCHIVE_SHA256" "$ARCHIVE" | sha256sum --check --status \
        || die "archive checksum mismatch; remove ${ARCHIVE} and retry"
    INSTALL_TMP="$(mktemp -d "${TOOL_ROOT}/sdk/.install-XXXXXX")"
    tar --extract --gzip --file "$ARCHIVE" --directory "$INSTALL_TMP" --no-same-owner
    [[ -x "${INSTALL_TMP}/google-cloud-sdk/bin/gcloud" && \
       -x "${INSTALL_TMP}/google-cloud-sdk/platform/bundledpythonunix/bin/python3" ]] \
        || die 'verified archive lacks the required CLI or bundled Python'
    mv -- "$INSTALL_TMP" "$SDK_PARENT"
    INSTALL_TMP=""
fi
[[ -x "${SDK}/bin/gcloud" && \
   -x "${SDK}/platform/bundledpythonunix/bin/python3" ]] \
    || die "incomplete SDK at ${SDK_PARENT}"
[[ -f "${SDK}/VERSION" && "$(<"${SDK}/VERSION")" == "$VERSION" ]] \
    || die "SDK version mismatch at ${SDK_PARENT}"
mkdir -p -- "${TOOL_ROOT}/config" "${TOOL_ROOT}/home" "${TOOL_ROOT}/tmp"
chmod 700 -- "${TOOL_ROOT}/config" "${TOOL_ROOT}/home" "${TOOL_ROOT}/tmp"
flock -u 9
exec 9>&-

gcloud_isolated() {
    local -a command=(
        env -i
        "PATH=/usr/bin:/bin"
        "HOME=${TOOL_ROOT}/home"
        "TMPDIR=${TOOL_ROOT}/tmp"
        "LANG=C.UTF-8"
        "CLOUDSDK_CONFIG=${TOOL_ROOT}/config"
        "CLOUDSDK_PYTHON=${SDK}/platform/bundledpythonunix/bin/python3"
        "PYTHONNOUSERSITE=1"
        "CLOUDSDK_CORE_DISABLE_USAGE_REPORTING=true"
        "CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK=true"
    )
    # Connectivity settings are the only optional inherited runtime settings.
    local name
    for name in HTTPS_PROXY HTTP_PROXY ALL_PROXY NO_PROXY https_proxy http_proxy all_proxy no_proxy; do
        [[ -z "${!name:-}" ]] || command+=("${name}=${!name}")
    done
    "${command[@]}" "${SDK}/bin/gcloud" "$@"
}

case "$MODE" in
    install) gcloud_isolated version ;;
    auth) gcloud_isolated auth login --no-launch-browser ;;
    check)
        if ! gcloud_isolated storage ls gs://waymo_open_dataset_v_2_0_1/; then
            printf 'Access check failed. Use the Google account enrolled for Waymo and complete its access/terms flow.\n' >&2
            exit 1
        fi
        ;;
    --) gcloud_isolated "$@" ;;
esac
