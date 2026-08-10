# Changelog Fragments

Each unreleased change should be a file in this directory.

File naming: `<pr-number>.<type>.md`

Types: `added`, `changed`, `deprecated`, `removed`, `fixed`

Content: A single line describing the change.

Example: `42.added.md` → "New `Pot.summon()` streaming support."

At release time, `towncrier build` compiles all fragments into `CHANGELOG.md`.