# `generated_planet_override_settings.dl_bin` — whole-table export

44 row(s), stride 40 B, element **PlanetOverrides** (`0x7630FBB7`), 5 field(s).

Values are read from row 0..n; a 4-byte slot prints both readings (`hex / f32`) because
the typelib does not say which one it is.

Rows are named by their own pointers (payload-relative u64 at 40 B stride): **44/44** rows resolve a display name.  The positional pairing is not used here because this table's string pools hold several strings per row.

## Fields

| offset | size | type | filled | distinct | examples |
|---:|---:|---|---:|---:|---|
| +0 | 8 | 0x00000000 | 44 | 37 | 0x0000000000000038 / 7.84727e-44,0; 0x00000000000000d8 / 3.0268e-43,0; 0x00000000000006b8 / 2.41023e-42,0 |
| +8 | 4 | 0x00000000 | 44 | 44 | 0x20512e9a / 1.77184e-19; 0xb73bc87a / -1.11927e-05; 0x7fd94f51 |
| +16 | 8 | 0x00000000 | 44 | 44 | 0xda62db36134d2e4d / 2.58975e-27,-1.59636e+16; 0xc62cf40ae9c27599 / -2.93859e+25,-11069; 0x5b9e6a4fe6f8f1bd / -5.87803e+23,8.91799e+16 |
| +24 | 8 | 0x00000000 | 44 | 35 | 0x0000000000000048 / 1.00893e-43,0; 0x00000000000000e8 / 3.25101e-43,0; 0x00000000000006c8 / 2.43265e-42,0 |
| +32 | 8 | 0x00000000 | 44 | 32 | 0x000000000000000b / 1.54143e-44,0; 0x000000000000003e / 8.68805e-44,0; 0x000000000000000f / 2.10195e-44,0 |

## First 5 rows

| group | row | name | +0 | +8 | +16 | +24 | +32 |
|---|---|---|---|---|---|---|---|
| 0 | 0 | superearth | 0x0000000000000038 / 7.84727e-44,0 | 0x20512e9a / 1.77184e-19 | 0xda62db36134d2e4d / 2.58975e-27,-1.59636e+16 | 0x0000000000000048 / 1.00893e-43,0 | 0x000000000000000b / 1.54143e-44,0 |
| 1 | 0 | moor_shared | 0x00000000000000d8 / 3.0268e-43,0 | 0xb73bc87a / -1.11927e-05 | 0xc62cf40ae9c27599 / -2.93859e+25,-11069 | 0x00000000000000e8 / 3.25101e-43,0 | 0x000000000000003e / 8.68805e-44,0 |
| 1 | 1 | moor_base | 0x00000000000006b8 / 2.41023e-42,0 | 0x7fd94f51 | 0x5b9e6a4fe6f8f1bd / -5.87803e+23,8.91799e+16 | 0x00000000000006c8 / 2.43265e-42,0 | 0x000000000000000f / 2.10195e-44,0 |
| 1 | 2 | moor_tundra | 0x0000000000000830 / 2.93712e-42,0 | 0xec813906 | 0x0d546c602bfc59fd / 1.79307e-12,6.5458e-31 | 0x0000000000000840 / 2.95954e-42,0 | 0x0000000000000020 / 4.48416e-44,0 |
| 1 | 3 | moor_arid | 0x0000000000000b40 / 4.03574e-42,0 | 0x7a5a6dc3 | 0x8213c292860e76ac / -2.67944e-35,-1.08557e-37 | 0x0000000000000b50 / 4.05816e-42,0 | 0x0000000000000019 / 3.50325e-44,0 |
