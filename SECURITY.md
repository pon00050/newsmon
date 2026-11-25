# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub's
[private vulnerability reporting](https://github.com/pon00050/newsmon/security/advisories/new). Do not open a public
issue. Include the version, what an attacker can do, and steps to reproduce. You should get a reply within a week.

## Scope and design assumptions

- Newsmon is a single-user local application. The web UI binds to loopback (`127.0.0.1`) only and has no
  authentication, so do not expose it on a network or behind a reverse proxy.
- Feed and wire content is untrusted. It is parsed with `defusedxml`, rendered escaped, and fetched with an SSRF guard
  (private, link-local and special-purpose addresses are refused) and size and time limits.
- When optional AI is enabled, article text is treated as untrusted data: it is placed in delimiters, no tools are
  attached, output is validated against a schema, and a deterministic prompt-injection pre-filter runs first.
- Secrets are read only from the environment or `<config>/.env`. The configuration loader refuses secrets in YAML
  files and logs redact them.
- The public export publishes only a closed list of fields, behind a deny-by-default permission
  (`docs/publication-policy.md`).

## Supported versions

Only the latest release receives fixes.
