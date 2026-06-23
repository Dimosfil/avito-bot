## Verification

For documentation-only changes:

```powershell
git diff --check
```

For larger changes, reread the edited files and confirm links, paths, and
checklists still match the repository layout.

If adding a file under `templates/`, `patterns/`, or `checklists/`, update
`INDEX.md` in the same change.
