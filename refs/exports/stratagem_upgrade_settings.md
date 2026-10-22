# `generated_stratagem_upgrade_settings.dl_bin` — whole-table export

1 row(s), stride 64 B, element **StratagemCustomizationInfo** (`0x6F0A448D`), 12 field(s).

Values are read from row 0..n; a 4-byte slot prints both readings (`hex / f32`) because
the typelib does not say which one it is.

Rows are named by their own pointers (payload-relative u64 at 64 B stride): **1/1** rows resolve a display name.  The positional pairing is not used here because this table's string pools hold several strings per row.

## Fields

| offset | size | type | filled | distinct | examples |
|---:|---:|---|---:|---:|---|
| +0 | 8 | 0x00000000 | 1 | 1 | 0x0000000000000050 / 1.12104e-43,0 |
| +8 | 4 | 0x00000000 | 1 | 1 | 0x188c40a6 / 3.62544e-24 |
| +12 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +16 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +20 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +24 | 8 | 0x00000000 | 1 | 1 | 0x0000000000000000 / 0,0 |
| +32 | 4 | StratagemCustomizationType | 1 | 1 | 0x00000005 / 7.00649e-45 |
| +36 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +40 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +44 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +48 | 4 | 0x00000000 | 1 | 1 | 0x00000000 / 0 |
| +56 | 8 | 0x00000000 | 1 | 1 | 0x414054d365acdf30 / 1.02046e+23,12.0207 |

## First 1 rows

| row | name | +0 | +8 | +12 | +16 | +20 | +24 | +32 | +36 | +40 | +44 | +48 | +56 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | AMMO RACK MOUNTED TURRET | 0x0000000000000050 / 1.12104e-43,0 | 0x188c40a6 / 3.62544e-24 | 0x00000000 / 0 | 0x00000000 / 0 | 0x00000000 / 0 | 0x0000000000000000 / 0,0 | 0x00000005 / 7.00649e-45 | 0x00000000 / 0 | 0x00000000 / 0 | 0x00000000 / 0 | 0x00000000 / 0 | 0x414054d365acdf30 / 1.02046e+23,12.0207 |
