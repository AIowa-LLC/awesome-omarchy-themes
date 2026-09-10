## What does this PR change?

<!-- Keep this focused: one theme or one maintenance/docs fix per PR. -->

## Change type

- [ ] Theme addition/update
- [ ] Repository maintenance/docs/tooling

## Required for every PR

- [ ] `python3 -m unittest discover -s tests -v` passes
- [ ] `python3 scripts/validate.py` exits 0
- [ ] Diff is limited to the stated scope
- [ ] No secrets, credentials, personal data, or machine-specific paths

## Theme PR checklist

<!-- Mark these N/A for maintenance/docs PRs. -->

- [ ] `colors.toml` parses as valid TOML
- [ ] Directory name is a lowercase kebab-case slug
- [ ] Foreground and accent colors are >= 3:1 contrast against `background`
- [ ] Theme installs and applies locally: `cp -r themes/<name> ~/.config/omarchy/themes/ && omarchy theme set <name>`
- [ ] README row is in the matching Dark themes / Light themes table
- [ ] Any committed images are redistributable, with source and license noted below

## Contrast ratios

<!-- Theme PRs: e.g. foreground 12.4:1, accent 4.1:1. Maintenance PRs: N/A. -->

## Image source / redistribution license

<!-- Required when adding or replacing image assets. Otherwise N/A. -->

## Screenshot

<!-- If practical, include a screenshot of the applied theme or documentation change. -->
