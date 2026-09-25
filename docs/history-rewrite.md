# History rewrite, 2026-09-25

The repository's git history was rewritten once, on 2026-09-25, to remove old
versions of the generated PDFs. **Every commit hash changed.** This note exists so
that the revision IDs quoted elsewhere in the project still mean something.

## Why

A clone was 63 MB, and 70 MB of the ~98 MB of blob storage was PDFs: 130 of them.
Typst PDFs are already-compressed binaries, so git cannot delta them — every report
rebuild stored a fresh ~2 MB `report_nbody.pdf`. Nothing else came close; the
SymbiYosys scratch and Yosys transcripts untracked the same day were 1.3 MB between
them.

Stripping PDF history and re-adding the current files took the clone from **63 MB to
about 25 MB**. All 249 commits and their messages are preserved unchanged; only the
hashes differ.

PDF history was the right thing to drop because the PDFs are build outputs of
committed Typst sources: any historical version can be reproduced by checking out
that commit and running `report/build.sh`.

## Revision IDs quoted in this project

Measurement directories under `results/` are named after the revision that was
measured. Those names are kept as they are — they are the historical record of what
was timed, and renaming them would both falsify that record and break the paths the
reports cite. The IDs refer to the **pre-rewrite** history:

| Quoted as | Pre-rewrite | Post-rewrite |
|---|---|---|
| `results/vm_canonical_20260910_2c8c754/` — the canonical timing run | `2c8c754` | `69b6bd5` |
| `results/profiles_20260910_08da63e/` — the recorded profiles | `08da63e` | `507e2a1` |
| `results/vm_rerun_20260910_3697a63/` — the VM trial run | `3697a63` | `3e1b098` |
| `results/vm_verify_20260921_f407567/` — the VM correctness run | `f407567` | `0a52580` |

`commit-map-20260925.txt` beside this file is the complete old → new mapping for all
249 commits, as emitted by `git-filter-repo`.

## Recovering the pre-rewrite history

A full bundle of every ref as it stood before the rewrite was written to
`~/hwsw-prerewrite-20260925-032232.bundle` on Matan's machine (63 MB, outside the
repository and outside OneDrive). To inspect the old history:

```sh
git clone ~/hwsw-prerewrite-20260925-032232.bundle old-history
```

It is not committed here — committing a 63 MB bundle would undo the whole point.
