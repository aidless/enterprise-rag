# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Evidence: the README metric block is rendered from committed results JSON.
  `make check` recounts those rows, recomputes the bootstrap, re-runs the
  in-repo baseline, and fails if the prose drifts. No new retrieval score was
  added. Timings that were not fields in the JSON were removed from the docs.
- Governance baseline: LICENSE, security policy, code of conduct, contributor and
  support guides, issue and pull-request templates, CODEOWNERS, dependabot, and
  `.editorconfig` added. No research content changed.
