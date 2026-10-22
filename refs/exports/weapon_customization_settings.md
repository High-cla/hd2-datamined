# `generated_weapon_customization_settings.dl_bin` — whole-table export

252 row(s), stride 88 B, element **WeaponCustomizableItem** (`0xE56D4F6B`), 13 field(s).

Values are read from row 0..n; a 4-byte slot prints both readings (`hex / f32`) because
the typelib does not say which one it is.

Rows are named by their own pointers (payload-relative u64 at 88 B stride): **252/252** rows resolve a display name.  The positional pairing is not used here because this table's string pools hold several strings per row.

## Fields

| offset | size | type | filled | distinct | examples |
|---:|---:|---|---:|---:|---|
| +0 | 8 | DebugNameOffset / 0x00000000 | 252 | 247 | 0x0000000000002168 / 1.19839e-41,0; 0x000000000000218c / 1.20344e-41,0; 0x00000000000021b8 / 1.2096e-41,0 |
| +8 | 4 | ID / 0x00000000 | 252 | 252 | 0x5cd7f1bf; 0x4b7f0b70; 0xabea8c15 / -1.66656e-12 |
| +12 | 4 | NameUpper / 0x00000000 | 252 | 158 | 0xbf6d1c14 / -0.92621; 0x87b1d111 / -2.67549e-34; 0xb33df70d / -4.42297e-08 |
| +16 | 4 | NameCased / 0x00000000 | 252 | 158 | 0x9321ca5b / -2.04208e-27; 0xf5ae8259; 0x236506a1 / 1.24155e-17 |
| +20 | 4 | Description / 0x00000000 | 252 | 158 | 0xcbf63d7f; 0xeae9aeac; 0xa1439747 / -6.62688e-19 |
| +24 | 4 | Fluff / 0x00000000 | 252 | 1 | 0x00000000 / 0 |
| +32 | 8 | AddPath / 0x00000000 | 252 | 249 | 0x0bcd6f93eab8db93 / -1.1174e+26,7.9131e-32; 0xc756800da816efe1 / -8.37869e-15,-54912.1; 0x70564bca8bdd43d1 / -8.52281e-32,2.65286e+29 |
| +40 | 8 | Icon / 0x00000000 | 252 | 1 | 0x0000000000000000 / 0,0 |
| +48 | 16 | SlotsOffset / WeaponCustomizationSlot | 252 | 249 | 0x88210000000000000100000000000000; 0xb4210000000000000100000000000000; 0xd8210000000000000100000000000000 |
| +64 | 4 | UIWidgetColorsOffset / 0x00000000 | 252 | 12 | 0xffffffff; 0x00000458 / 1.55824e-42; 0x0000049c / 1.65353e-42 |
| +68 | 4 | 0x00000000 | 252 | 2 | 0xffffffff; 0x00000000 / 0 |
| +72 | 4 | UIWidgetColorsCount / 0x00000000 | 252 | 2 | 0x00000000 / 0; 0x00000004 / 5.60519e-45 |
| +80 | 4 | SortGroups / WeaponCustomizationSortGroups | 252 | 4 | 0x00000000 / 0; 0x00000001 / 1.4013e-45; 0x00000002 / 2.8026e-45 |

## First 5 rows

| group | row | name | slots | sort_group | +0 | +8 | +12 | +16 | +20 | +24 | +32 | +40 | +48 | +64 | +68 | +72 | +80 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | PISTOL-SMG 9x20mm. EXPLOSIVE | AmmoType | None | 0x0000000000002168 / 1.19839e-41,0 | 0x5cd7f1bf | 0xbf6d1c14 / -0.92621 | 0x9321ca5b / -2.04208e-27 | 0xcbf63d7f | 0x00000000 / 0 | 0x0bcd6f93eab8db93 / -1.1174e+26,7.9131e-32 | 0x0000000000000000 / 0,0 | 0x88210000000000000100000000000000 | 0xffffffff | 0xffffffff | 0x00000000 / 0 | 0x00000000 / 0 |
| 0 | 1 | PISTOL-SMG 9x20mm. FULL METAL JACKET | AmmoType | None | 0x000000000000218c / 1.20344e-41,0 | 0x4b7f0b70 | 0x87b1d111 / -2.67549e-34 | 0xf5ae8259 | 0xeae9aeac | 0x00000000 / 0 | 0xc756800da816efe1 / -8.37869e-15,-54912.1 | 0x0000000000000000 / 0,0 | 0xb4210000000000000100000000000000 | 0xffffffff | 0xffffffff | 0x00000000 / 0 | 0x00000000 / 0 |
| 0 | 2 | PISTOL-SMG 9x20mm. HOLLOW POINT | AmmoType | None | 0x00000000000021b8 / 1.2096e-41,0 | 0xabea8c15 / -1.66656e-12 | 0xb33df70d / -4.42297e-08 | 0x236506a1 / 1.24155e-17 | 0xa1439747 / -6.62688e-19 | 0x00000000 / 0 | 0x70564bca8bdd43d1 / -8.52281e-32,2.65286e+29 | 0x0000000000000000 / 0,0 | 0xd8210000000000000100000000000000 | 0xffffffff | 0xffffffff | 0x00000000 / 0 | 0x00000000 / 0 |
| 0 | 3 | PISTOL-SMG 9x20mm. HIGH VELOCITY | AmmoType | None | 0x00000000000021dc / 1.21465e-41,0 | 0x58aeef6e | 0xb81b4853 / -3.70222e-05 | 0xfb7a777e | 0xf27b38b9 | 0x00000000 / 0 | 0x484d20b65c791d31 / 2.80477e+17,210051 | 0x0000000000000000 / 0,0 | 0x00220000000000000100000000000000 | 0xffffffff | 0xffffffff | 0x00000000 / 0 | 0x00000000 / 0 |
| 0 | 4 | PISTOL-SMG 9x20mm. PLASMA | AmmoType | None | 0x0000000000002204 / 1.22025e-41,0 | 0x28476fc6 / 1.1071e-14 | 0x5f9c5ef8 | 0x6a6a555f | 0x9d674790 / -3.06096e-21 | 0x00000000 / 0 | 0x803b8f8f573c5810 / 2.07086e+14,-5.46979e-39 | 0x0000000000000000 / 0,0 | 0x20220000000000000100000000000000 | 0xffffffff | 0xffffffff | 0x00000000 / 0 | 0x00000000 / 0 |
