# Our 22 patches on build 25988413 — what is salvageable

Question: with the shared loader dead and `ffi` gone, do we own anything that still works?

Method: every patch in the backup `D:\mod\backups\game-patches-25988413` was reopened with srkit and its
entries classified by resource type (`Repository` → `package.entries` → `type_name`). Read-only; the game
folder was not touched.

## Result

| slot | entries | lua | non-lua resources |
|---|---|---|---|
| 0 | 1 | 1 | — (shared loader) |
| 1 | 1 | 1 | — |
| 2 | 277 | **264** | material ×8, texture ×3, font ×2 (HD2Runtime) |
| 3 | 1 | 1 | — |
| 4 | 1 | 1 | — |
| 5 | 4 | 2 | texture ×1, material ×1 |
| 6 | 10 | 2 | texture ×4, material ×4 |
| 7–18, 20 | 1 each | 1 each | — |
| 19, 21 | 1 each | 1 each | — (loader copies) |

## Conclusions

1. **Every patch we own carries at least one lua resource.** There is no pure-asset mod in the whole
   portfolio, so there is nothing that "still works as-is" while the loader is missing.
2. The three patches that also ship art assets (2, 5, 6) ship them *alongside* lua that drives them; the
   assets alone do nothing. They are reusable **raw material** for a future cosmetic mod, not a working mod.
3. So the cosmetic direction is **new work**, not salvage - worth saying before anyone counts it as a
   quick win.
4. Everything stays rollback-able: the 66 files are byte-verified in the backup, restore with
   `python D:\mod\boot-probe\install_boot_probe.py --rollback`.

## What this does NOT say

It says nothing about whether the *assets* in those patches are still valid against the new build - that
requires the census comparison work (non-lua asset study), not a patch inventory. A patch can be
"mostly dead because of its lua" and still contain perfectly good textures.
