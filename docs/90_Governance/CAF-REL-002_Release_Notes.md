# CAF-REL-002 Release Notes

Release notes are the human-readable companion to the verification manifest. They live in `CHANGELOG.md`, newest first, one section per release.

## Required structure per release

```markdown
## <release string>

### Added
### Changed
### Fixed
```

Rules:

- The release string must match `release` in the verification manifest exactly (ARC-004 performs a string match against the CHANGELOG).
- Breaking contract changes are stated explicitly and require a new minor version line per the contract freeze policy (0.5.x → 0.6).
- Known limitations that ship with the release are listed under the release, not hidden in code comments.
