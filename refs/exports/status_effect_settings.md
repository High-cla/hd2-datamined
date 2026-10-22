# `generated_status_effect_settings.dl_bin` — whole-table export

102 row(s), stride 40 B, element **StatusEffectTemplate** (`0xA1E4D10D`), 4 field(s).

Values are read from row 0..n; a 4-byte slot prints both readings (`hex / f32`) because
the typelib does not say which one it is.

Rows are named by their own pointers (payload-relative u64 at 160 B stride): **73/102** rows resolve a display name.  The positional pairing is not used here because this table's string pools hold several strings per row.

## Fields

| offset | size | type | filled | distinct | examples |
|---:|---:|---|---:|---:|---|
| +0 | 4 | StatusEffectTemplateType | 102 | 73 | 0x00000001 / 1.4013e-45; 0x00000002 / 2.8026e-45; 0x00000003 / 4.2039e-45 |
| +4 | 4 | StatusEffectType | 29 | 26 | 0x00000021 / 4.62428e-44; 0x00000016 / 3.08286e-44; 0x00000005 / 7.00649e-45 |
| +8 | 4 | 0x00000000 | 102 | 76 | 0x0000000000002db0 / 1.63896e-41,0; 0x0000000000002db6 / 1.6398e-41,0; 0x0000000000002dbc / 1.64064e-41,0 |
| +36 | 1 | 0x00000000 | 102 | 20 | 0x3f800000 / 1; 0x40a00000 / 5; 0x00000000 / 0 |

## First 5 rows

| group | row | name | +0 | +4 | +8 | +36 |
|---|---|---|---|---|---|---|
| 0 | 0 | Blind | 0x00000001 / 1.4013e-45 |  | 0x0000000000002db0 / 1.63896e-41,0 | 0x3f800000 / 1 |
| 0 | 1 | Bleed | 0x00000002 / 2.8026e-45 |  | 0x0000000000002db6 / 1.6398e-41,0 | 0x40a00000 / 5 |
| 0 | 2 | Deaf | 0x00000003 / 4.2039e-45 |  | 0x0000000000002dbc / 1.64064e-41,0 | 0x3f800000 / 1 |
| 0 | 3 | Confusion | 0x00000004 / 5.60519e-45 |  | 0x0000000000002dc1 / 1.64134e-41,0 | 0x00000000 / 0 |
| 0 | 4 | Fire | 0x00000005 / 7.00649e-45 |  | 0x0000000000002dcb / 1.64274e-41,0 | 0x40a00000 / 5 |
