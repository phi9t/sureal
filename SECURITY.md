# Security policy

## Supported branch

Security fixes are applied to the current `main` branch. This is research code,
not a hosted service or a supported production system; releases and historical
commits do not receive a guaranteed maintenance window.

## Reporting a vulnerability

Use a private
[GitHub security advisory](https://github.com/phi9t/sureal/security/advisories/new)
and include affected revisions, reproduction steps, impact, and any suggested
mitigation. Do not open a public issue, pull request, discussion, or log paste
for suspected vulnerabilities, credentials, private dataset links, or access
tokens.

If private advisories are unavailable, avoid publishing the sensitive details
and wait for a private reporting channel to be enabled. Never include live
secrets in a report; revoke and rotate exposed credentials first.

The project will assess reports in the context of its research-code boundary,
including local file handling, model/data provenance, dependency supply chains,
and reproducible execution. Operational deployment hardening remains the
responsibility of downstream users.
