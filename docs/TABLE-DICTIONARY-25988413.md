# 全表字典 · build 25988413（只读）

> 这份文档回答一件事：**这个 build 的数据表都有什么、每张表长什么样、字段在哪个偏移。**
> 不涉及改游戏，也不含任何密钥材料——重新生成需要你自己的 `recipient.sk`（见 §用法）。

## 0. 一句话状态

55 张 `generated_*.dl_bin` + 1 个类型库，**全部能解封并解析**；类型库给出 **1,208 个类型 / 7,349
个成员偏移**，配合公开的名字表能还原 **6,696 个类型名**：

| 几何状态 | 表数 | 含义 |
|---|---:|---|
| **行数从组头直接读出** | **23** | 组头 `u64 0x10 + u64 count` 里的 count **就是行数** |
| 其中带尾部字符串块 | 13 | `16 + 行数×步长 < payload`，多出来的是**变长字符串**（名字/本地化键） |
| 无描述符（`raw`） | 32 | 没有 `0x10` 头，行数是 `payload ÷ 步长` 推的；entities 是 275 个组件块 |

> **修正**：上一版把 5 张表（stamp / weapon_customization / stratagem / planet_override /
> stratagem_upgrade）写成"hashmap，count 是槽数"——**这是错的**。它们其实是「行数组 + 尾部字符串块」，
> count 就是行数。见下一节。

## 0.5 那 5 张"哈希图"表已经解开

模型：`payload = 16 + 行数 × 步长 + 字符串块`，**36/36 个组全部成立**；行里存的是指向字符串块的偏移。

| 表 | 行数 | 步长 | 字符串块 | 尾部里是什么 |
|---|---:|---:|---:|---|
| `stamp_settings` | **4,096** | 112 B | 219,332 B | 印章名 |
| `weapon_customization_settings` | **252** | 88 B | 8,284 B | 弹药名，如 `PISTOL-SMG 9x20mm. EXPLOSIVE` |
| `stratagem_settings` | **153** | 400 B | 20,700 B | 战备名与本地化键，如 `nui_stratagem_backpack_ammo_name` |
| `planet_override_settings` | **44** | 40 B | 33,190 B | 行星名，如 `superearth` |
| `stratagem_upgrade_settings` | **1** | 64 B | 25 B | `AMMO RACK MOUNTED TURRET` |

**名字怎么取（2026-10-22 修正）**：字符串块**不是**靠行内偏移寻址的。行里那个 u64 只是碰巧落在
某条字符串内部（在不同行里偏移量是 8/16/8/12/4… 变化），按它取名字会被截掉前缀。
真实结构是**按行序平行的名字数组**：块里第 i 条可读字符串就是第 i 行的名字。
已验证覆盖每一行的有 6 张表：`weapon_customization` 252、`stratagem` 153、`status_effect` 73、
`planet_override` 44、`language` 15、`stratagem_upgrade` 1。抽出来的名字在
`refs/table-row-names.json`，工具是 `tools/table_row_names.py`。

**整表导出**：`tools/table_export.py` 把一张表导成 CSV + Markdown（名字 + 每字段 hex/f32 + 字段统计），
首张产物在 `refs/exports/weapon-customization-rows.csv|md`（252 行 × 13 字段，行名就是弹药名）。

样例（都是表里原样读出来的）：

| 表 | 前几条名字 |
|---|---|
| `status_effect_settings` | `Blind` / `Bleed` / `Deaf` / `Confusion` |
| `weapon_customization_settings` | `PISTOL-SMG 9x20mm. EXPLOSIVE` / `… FULL METAL JACKET` / `… HOLLOW POINT` |
| `stratagem_settings` | `BACKPACK. SUPPLY BACKPACK` / `nui_stratagem_backpack_ammo_name`（名 + 本地化键成对出现）|
| `planet_override_settings` | `superearth` / `moor_shared` / `moor_base` / `moor_tundra` |
| `language_settings` | `english` / `en-US` / `English US` / `en-GB` |

⚠ 约 1% 的条目会带一个对齐填充字节（如 `sBACKPACK…`、`"moor_tundra`），是块内 padding 恰好可打印
造成的，原样保留、不猜着裁。

## 1. 已验证的几何（我们自己的工具实测过）

| 表 | 行 × 步长 | 我们怎么确认的 |
|---|---|---|
| `projectile_settings` | **355 × 272** | `proj_copy_row.py` 整行搬运，实机换弹头成功 |
| `explosion_settings` | **424 × 152 + 3,664 尾块** | `expl_set.py` 写 `+80/+84`，实机出破片 |
| `damage_settings` | 661 × 76 | `dmg_edit.py` 行级改写 |
| `hit_effect_settings` | 1,512 × 48 | 本字典（几何闭合） |
| `surface_effect_settings` | 7,644 × 40 | 本字典（几何闭合） |
| `beam_settings` / `arc_settings` | 30 × 112 / 16 × 104 | `name_rows.py` 跨版本命名时确认 |
| `sky` / `scenario` / `collision_event` / `weather_color` / `route` | 480×24 / 149×48 / 180×80 / 132×196 / 3×112 | 本字典（几何闭合） |
| `entities` | **275 个组件块**（非行表） | `ENTITY-TABLE-25988413.md`：hashmap 开放寻址 + 块序列 |

**交叉验证（两边独立得出、结果一致）**：我们早先靠实机差分测出"射弹 `+144` = 命中爆炸类型、
`+156` = 到期爆炸类型"；类型库在 `ProjectileInfo` 的 144 / 156 两个成员上标的类型正是
**`ExplosionType`**（4 B，`0x11BEEE03`），而偏移 0 是 `ProjectileType`。两套方法互证，说明这份
字典的偏移是可信的。

## 2. 三层能力（这份字典覆盖第 1 层）

| 层 | 状态 |
|---|---|
| **结构层**：组、行步长、字段偏移、嵌套类型 | ✓ **55/55 张全部可得**（本文档） |
| **语义层**：哪个偏移是伤害 / 半径 / 掉率 | ◐ 只有 5 张表标过（entities 部件、damage、projectile、explosion、weapon_customization） |
| **可改层**：哈希校正空位 + 实机验证 | ◐ 同样 5 张；其余未验证 |

## 3. 已知限制（别把本字典当全知）

1. ~~hashmap 的 count 是槽数~~ —— **已更正**：那 5 张表的 count 就是行数，见 §0.5。剩余 32 张
   没有描述符的表，行数仍是推算值，可能有 ±1 零头。
2. **`raw` 表没有 `0x10` 描述符**，行数是 `payload // 步长` 推的，可能有 ±1 的零头。
3. **entities 不是行表**：275 个组件块，每块是「哈希图 + 行数组」，本字典只给出块与类型。
4. **类型名来自公开哈希表，不是游戏自带**：`dl_library.dl_typelib` 是**去字符串**的（1208 个
   类型、0 个字符串），所以成员**没有名字**，只有偏移、尺寸、类型——语义要靠猜和实测。
5. 未被任何 projectile / fire 表引用的射弹、爆炸行（见各自的文档）仍然存在，本字典只给结构。
6. **原始字段不做类型猜测**：类型库把 primitive 的 type id 记为 0 且不说它是 f32 还是 u32
   （去字符串，连字段名都没有）。所以字段表最后一列同时给 **十六进制**和 **f32 读数**，由人判断——
   例如 `0x41C80000 · f32 25` 多半是 25.0，而 `0xCAE08F72 · f32 -7358393` 多半是个 u32 位标志。
   唯一有类型信息的是非 0 的 type id（枚举或嵌套结构）。

## 4. 用法

```bash
# 重新生成（需要你自己的密钥，仓库里不含）
python tools/table_dictionary.py \
    --sk <你的>/recipient.sk \
    --game "<Steam>/steamapps/common/Helldivers 2" \
    --names refs/dl-type-names.txt \
    --json out/dictionary.json --md out/TABLE-DICTIONARY.md
```

* `--json` 里有每张表每个组的明细（偏移、类型、count、尾块、布局）和每个元素的完整字段树。
* `--md` 就是本文档的正文。
* 类型名列表是公开的（filediver 的 `dl_type_names.txt`），随仓库放在 `refs/dl-type-names.txt`。

---

# 正文：表清单与字段布局
| table | plain B | groups | count | layout | element type(s) |
|---|---:|---:|---:|---|---|
| `generated_entities.dl_bin` | 47,259,396 | 275 | 275 | raw+raw-array | EntitySettingsHashmap×131072B, EntityNetworkDataArray×15072B, VisibilityComponentData×3392B |
| `generated_destruction_settings.dl_bin` | 1,643,910 | 1647 | 16,156 | raw+raw-array+rows | DestructionSettings×168B, DestructionTemplates×16B, DestructionHashMap×16B |
| `generated_planet_territory_graphs.dl_bin` | 1,574,628 | 11 | 28,105 | raw+raw-array | SavedPlanetTerritoryGraph×56B |
| `generated_stamp_settings.dl_bin` | 678,124 | 1 | 4,096 | rows+blob | StampHashEntry×112B |
| `generated_zone_data.dl_bin` | 518,478 | 88 | 517 | raw+raw-array | ZoneSettings×912B |
| `generated_customization_armor_sets.dl_bin` | 453,204 | 422 | 6,821 | raw | HelldiverCustomizationKit×64B |
| `generated_location_groups.dl_bin` | 397,106 | 13 | 7,080 | raw+raw-array | LevelGenerationLocation×56B |
| `generated_planet_data.dl_bin` | 369,540 | 438 | 438 | raw | LevelGenerationPlanetData×624B |
| `generated_credits_settings.dl_bin` | 368,228 | 1 | 4,515 | rows+blob | CreditsRowData×64B |
| `generated_entity_deltas.dl_bin` | 352,345 | 1 | 4,403 | raw | ComponentEntityDeltaStorage×80B |
| `generated_surface_effect_settings.dl_bin` | 305,804 | 1 | 7,644 | rows | SurfaceEffectInfo×40B |
| `generated_region_settings.dl_bin` | 259,627 | 87 | 310 | raw+raw-array | GenerationRegionSettings×3272B, GenerationRegionGroup×64B |
| `generated_animation_event_trigger_settings.dl_bin` | 165,068 | 1 | 213 | rows+blob | AnimationEventTriggerSetting×24B |
| `generated_weather_settings.dl_bin` | 162,908 | 184 | 190 | raw | WeatherSettings×648B |
| `generated_galactic_presence_settings.dl_bin` | 155,853 | 137 | 137 | raw | 0xF8F9EC3E×1000B |
| `generated_projectile_settings.dl_bin` | 96,604 | 1 | 355 | rows | ProjectileInfo×272B |
| `generated_solar_system_settings.dl_bin` | 91,764 | 1 | 3,822 | raw | SolarSystemSettings×24B |
| `generated_satellite_groups.dl_bin` | 83,413 | 36 | 3,429 | raw+raw-array | LevelGenerationSatelliteGroup×24B |
| `generated_stratagem_settings.dl_bin` | 82,384 | 12 | 153 | rows+blob | StratagemInfo×400B |
| `generated_hit_effect_settings.dl_bin` | 72,620 | 1 | 1,512 | rows | HitEffectInfo×48B |
| `generated_explosion_settings.dl_bin` | 68,156 | 1 | 424 | rows+blob | ExplosionInfo×152B |
| `generated_unit_effect_settings.dl_bin` | 63,004 | 1 | 408 | rows+blob | UnitEffectSetting×112B |
| `generated_planet_region_settings.dl_bin` | 61,485 | 369 | 369 | raw | PlanetRegionSettings×128B |
| `generated_damage_settings.dl_bin` | 50,336 | 2 | 662 | raw-array+rows | DamageArmorAngles×32B, DamageInfo×76B |
| `generated_planet_override_settings.dl_bin` | 35,474 | 13 | 44 | rows+blob+unknown | PlanetOverrides×40B |
| `generated_weapon_customization_settings.dl_bin` | 30,824 | 9 | 252 | rows+blob | WeaponCustomizableItem×88B |
| `generated_unit_customization_settings.dl_bin` | 27,744 | 12 | 339 | raw | UnitCustomizationSettings×80B |
| `generated_weather_color_set_settings.dl_bin` | 25,916 | 1 | 132 | rows | WeatherColorSet×196B |
| `generated_planet_types_settings.dl_bin` | 16,844 | 1 | 88 | rows+blob | SolarSystemObjectType×24B |
| `generated_collision_event_settings.dl_bin` | 14,444 | 1 | 180 | rows | CollisionEventSetting×80B |
| `generated_status_effect_settings.dl_bin` | 14,020 | 2 | 102 | rows+rows+blob | StatusEffectInfo×160B, StatusEffectTemplate×40B |
| `generated_sky_settings.dl_bin` | 12,484 | 40 | 480 | raw-array | SkySettings×24B |
| `generated_environment_settings.dl_bin` | 10,962 | 17 | 17 | raw | EnvironmentSettings×576B |
| `generated_generation_settings.dl_bin` | 10,396 | 1 | 22 | raw | LevelGenerationSettings×464B |
| `generated_scenario_settings.dl_bin` | 8,092 | 39 | 149 | raw-array | ScenarioSettings×48B |
| `generated_font_settings.dl_bin` | 5,980 | 6 | 50 | raw | FontSettings×112B |
| `generated_customization_passive_bonuses.dl_bin` | 4,016 | 33 | 40 | raw+raw-array | HelldiverCustomizationPassiveBonusSettings×56B |
| `generated_language_settings.dl_bin` | 3,948 | 1 | 15 | rows+blob | LanguageListEntry×208B |
| `generated_beam_settings.dl_bin` | 3,404 | 1 | 30 | rows | BeamInfo×112B |
| `generated_video_flow_settings.dl_bin` | 2,060 | 1 | 63 | raw | VideoFlowSettings×32B |
| `generated_planet_color_set_settings.dl_bin` | 1,964 | 1 | 30 | rows | 0x80EB67CF×64B |
| `generated_modifier_settings.dl_bin` | 1,764 | 15 | 52 | raw+raw-array | Modifier×24B |
| `generated_arc_settings.dl_bin` | 1,708 | 1 | 16 | rows | ArcInfo×104B |
| `generated_distant_war_effect_settings.dl_bin` | 1,468 | 7 | 26 | raw+raw-array | DistantWarEffectPool×48B |
| `generated_video_ui_settings.dl_bin` | 1,124 | 1 | 9 | rows | VideoUIElement×120B |
| `generated_candidate_descs.dl_bin` | 812 | 1 | 12 | rows+blob | CandidateDescription×40B |
| `generated_font_lookup.dl_bin` | 604 | 6 | 19 | raw-array | FontLookup×24B |
| `generated_policy_settings.dl_bin` | 480 | 1 | 14 | raw | PolicySettings×32B |
| `generated_route_settings.dl_bin` | 436 | 3 | 3 | raw-array | RouteSettings×112B |
| `generated_corporation_logos.dl_bin` | 364 | 1 | 8 | rows | CorporationLogo×40B |
| `generated_add_resource_dependencies.dl_bin` | 180 | 2 | 6 | rows | 0x06F9ABD0×16B |
| `generated_stratagem_upgrade_settings.dl_bin` | 133 | 1 | 1 | rows+blob | StratagemCustomizationInfo×64B |
| `generated_body_settings.dl_bin` | 116 | 2 | 2 | raw-array | HelldiverBody×32B |
| `generated_layer_package_indirection_settings.dl_bin` | 108 | 1 | 5 | raw-array | PackageLayerTagIndirection×16B |
| `generated_resource_swap.dl_bin` | 24 | 0 | 0 |  |  |

## Field layouts

### 0x06F9ABD0  (`generated_add_resource_dependencies.dl_bin`, stride 16 B, rows 6)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | 0x1F0B6202 (`0x1F0B6202`) |  |

### AnimationEventTriggerSetting  (`generated_animation_event_trigger_settings.dl_bin`, stride 24 B, rows 213)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 16 | AnimationEventTrigger (`0x37B7C916`) |  |

### ArcInfo  (`generated_arc_settings.dl_bin`, stride 104 B, rows 16)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | ArcType (`0xA064A858`) |  |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x00000010 · f32 2.242078e-44 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00000007 · f32 9.809089e-45 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x43960000 · f32 300 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x425C0000 · f32 55 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x42200000 · f32 40 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x42200000 · f32 40 |
| 36 | 4 | DamageInfoType (`0x39D2F78D`) |  |
| 40 | 8 | 0x00000000 (`0x00000000`) | 0x0000000140400000 · f32 3/1.4013e-45 |
| 48 | 8 | 0x00000000 (`0x00000000`) | 0x000000CE00000001 · f32 1.4013e-45/2.88667e-43 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 64 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 72 | 4 | HitEffectDamageType (`0xB43002D3`) |  |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 80 | 8 | 0x00000000 (`0x00000000`) | 0x6C3208B3FAB4A0B4 · f32 -4.68936e+35/8.6092e+26 |
| 88 | 4 | 0x00000000 (`0x00000000`) | 0x00000003 · f32 4.203895e-45 |
| 92 | 1 | 0x00000000 (`0x00000000`) | 0x0B |
| 96 | 4 | 0x00000000 (`0x00000000`) | 0x84F7539A · f32 -5.81462e-36 |
| 100 | 1 | 0x00000000 (`0x00000000`) | 0x64 |

### BeamInfo  (`generated_beam_settings.dl_bin`, stride 112 B, rows 30)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | BeamType (`0xAD8F0477`) |  |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x0000001E · f32 4.203895e-44 |
| 12 | 4 | DamageInfoType (`0x39D2F78D`) |  |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x0000000B · f32 1.541428e-44 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x447A0000 · f32 1000 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x00000200 · f32 7.174648e-43 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 44 | 4 | SurfaceImpactType (`0xCF328969`) |  |
| 48 | 8 | 0x00000000 (`0x00000000`) | 0x3F8000003F800000 · f32 1/1 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x000000163DCCCCCD · f32 0.1/3.08286e-44 |
| 64 | 8 | 0x00000000 (`0x00000000`) | 0xDBAF8323AA29198D · f32 -1.50191e-13/-9.88046e+16 |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 80 | 4 | RaycastTemplate (`0xD7658573`) |  |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 88 | 4 | HitEffectDamageType (`0xB43002D3`) |  |
| 92 | 4 | 0x00000000 (`0x00000000`) | 0x305355A4 · f32 7.688306e-10 |
| 96 | 4 | ExplosionType (`0x11BEEE03`) |  |
| 100 | 1 | 0x00000000 (`0x00000000`) | 0xB7 |
| 104 | 4 | DangerLevel (`0x6A3EC669`) |  |
| 108 | 1 | 0x00000000 (`0x00000000`) | 0x00 |

### HelldiverBody  (`generated_body_settings.dl_bin`, stride 32 B, rows 2)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | HelldiverCustomizationBodyType (`0x793E06A8`) |  |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0xDB990E0A · f32 nan/inf |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0xA4907A4E · f32 -6.265724e-17 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x5500828B · f32 nan/inf |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0xC4419807 · f32 -774.3754 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |

### CandidateDescription  (`generated_candidate_descs.dl_bin`, stride 40 B, rows 12)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x00000010 · f32 2.242078e-44 |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x000000000000000C · f32 1.68156e-44/0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x369DF8DB · f32 4.707935e-06 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 24 | 16 | CandidateTierSpeech (`0xEF6859E9`) |  |

### CollisionEventSetting  (`generated_collision_event_settings.dl_bin`, stride 80 B, rows 180)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x000000B4 · f32 2.522337e-43 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x89F2BD5E · f32 -5.843746e-33 |
| 24 | 48 | EffectSetting (`0x10CEE58B`) |  |
| 72 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |

### CorporationLogo  (`generated_corporation_logos.dl_bin`, stride 40 B, rows 8)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | Corporation (`0x4102A6B0`) |  |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000008 · f32 1.12104e-44/0 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000001 · f32 1.4013e-45/0 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |

### CreditsRowData  (`generated_credits_settings.dl_bin`, stride 64 B, rows 4,515)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 4 | MenuFontStyle (`0x360D7FBD`) |  |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x000468D0 · f32 4.049416e-40 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000100000011 · f32 2.38221e-44/1.4013e-45 |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x000468D1 · f32 4.04943e-40 |
| 48 | 8 | 0x00000000 (`0x00000000`) | 0x00000000000468D2 · f32 4.04944e-40/0 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 60 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |

### HelldiverCustomizationKit  (`generated_customization_armor_sets.dl_bin`, stride 64 B, rows 6,821)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x1F9BFA78 · f32 6.605942e-20 |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x1E4D2119 · f32 1.085945e-20 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x4B2DCC62 · f32 1.139005e+07 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x60C107C2 · f32 nan/inf |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0xA23CABAE · f32 -2.556964e-18 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0xB651AD59 · f32 -3.124433e-06 |
| 24 | 4 | HelldiverCustomizationRarity (`0x00818233`) |  |
| 28 | 4 | HelldiverCustomizationPassiveBonus (`0x1F938AFA`) |  |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0x267FCB7E9E312E33 · f32 -9.37986e-21/8.87467e-16 |
| 40 | 4 | HelldiverCustomizationKitType (`0x089EC682`) |  |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0xBF800000 · f32 -1 |
| 48 | 16 | HelldiverBodyTypePieces (`0xBCB00FA8`) |  |

### HelldiverCustomizationPassiveBonusSettings  (`generated_customization_passive_bonuses.dl_bin`, stride 56 B, rows 40)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | HelldiverCustomizationPassiveBonus (`0x1F938AFA`) |  |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0xFAC24AB8 · f32 nan/inf |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x3642B3057D12359E · f32 1.21466e+37/2.90125e-06 |
| 16 | 16 | HelldiverCustomizationPassiveBonusModifier (`0xB5EE1FE9`) |  |
| 32 | 16 | HelldiverCustomizationStatModifier (`0xD269EE03`) |  |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |

### DamageArmorAngles  (`generated_damage_settings.dl_bin`, stride 32 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | 0x00000000 (`0x00000000`) | 0000c84100007042 |
| 16 | 16 | 0x00000000 (`0x00000000`) | 0000c84100007042 |

### DamageInfo  (`generated_damage_settings.dl_bin`, stride 76 B, rows 661)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | DamageInfoType (`0x39D2F78D`) |  |
| 4 | 8 | 0x00000000 (`0x00000000`) | 0x0000029500000000 · f32 0/9.26258e-43 |
| 12 | 16 | 0x00000000 (`0x00000000`) | 0000000001000000 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x00000005 · f32 7.006492e-45 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x00000005 · f32 7.006492e-45 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x00000005 · f32 7.006492e-45 |
| 40 | 4 | ElementType (`0x86B0A9AC`) |  |
| 44 | 32 | DamageStatusEffectInfo (`0xB99AE45C`) |  |

### DestructionSettings  (`generated_destruction_settings.dl_bin`, stride 168 B, rows 7,953)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 144 | DestructionEventLevel (`0xF8CBFA8E`) |  |
| 144 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 148 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 152 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 152 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 152 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 152 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 156 | 12 | CApiVector3 (`0x85B82A43`) |  |

### DestructionTemplates  (`generated_destruction_settings.dl_bin`, stride 16 B, rows 11)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | DestructionTemplate (`0xB247DB30`) |  |

### DestructionHashMap  (`generated_destruction_settings.dl_bin`, stride 16 B, rows 8,192)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | DestructionHashEntry (`0x8CE2D12A`) |  |

### DistantWarEffectPool  (`generated_distant_war_effect_settings.dl_bin`, stride 48 B, rows 26)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | DistantWarEffectPoolType (`0x744AABCA`) |  |
| 4 | 4 | DistantWarEffectPoolLoadType (`0xA3981C2A`) |  |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x7E0BE3330DF85C69 · f32 1.53064e-30/4.64856e+37 |
| 16 | 8 | CApiVector2 (`0x85B82A42`) |  |
| 24 | 8 | CApiVector2 (`0x85B82A42`) |  |
| 32 | 16 | DistantWarEffect (`0x4304352E`) |  |

### EntitySettingsHashmap  (`generated_entities.dl_bin`, stride 131072 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 131072 | EntitySettings (`0xF38A4C8E`) |  |

### EntityNetworkDataArray  (`generated_entities.dl_bin`, stride 15072 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 15072 | EntityNetworkData (`0xF6239341`) |  |

### VisibilityComponentData  (`generated_entities.dl_bin`, stride 3392 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2464 | ComponentIndexData (`0xFCDFC705`) |  |
| 2464 | 924 | VisibilityComponent (`0xB44C147B`) |  |

### LocalUnitComponentData  (`generated_entities.dl_bin`, stride 2784 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1856 | ComponentIndexData (`0xFCDFC705`) |  |
| 1856 | 928 | LocalUnitComponent (`0xFB5A80FE`) |  |

### TagComponentData  (`generated_entities.dl_bin`, stride 326592 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 18144 | ComponentIndexData (`0xFCDFC705`) |  |
| 18144 | 308448 | TagComponent (`0x51DF988F`) |  |

### WeaponMagazineComponentData  (`generated_entities.dl_bin`, stride 53152 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8832 | ComponentIndexData (`0xFCDFC705`) |  |
| 8832 | 44320 | WeaponMagazineComponent (`0xFBA3CBE9`) |  |

### 0xD74E6E1A  (`generated_entities.dl_bin`, stride 128 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 96 | 0x08768DE0 (`0x08768DE0`) |  |

### GameModeComponentData  (`generated_entities.dl_bin`, stride 2128 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) |  |
| 608 | 1520 | GameModeComponent (`0x420B6672`) |  |

### RandomSlotComponentData  (`generated_entities.dl_bin`, stride 120 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 24 | RandomSlotComponent (`0xC01586F6`) |  |

### PowerGeneratorComponentData  (`generated_entities.dl_bin`, stride 200 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) |  |
| 160 | 40 | PowerGeneratorComponent (`0x1B6E25C7`) |  |

### HitEffectComponentData  (`generated_entities.dl_bin`, stride 24080 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 9632 | ComponentIndexData (`0xFCDFC705`) |  |
| 9632 | 14448 | HitEffectComponent (`0xCEB1EF25`) |  |

### 0x295933BE  (`generated_entities.dl_bin`, stride 64 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 32 | 0xE2582184 (`0xE2582184`) |  |

### SpawnOnPlayersComponentData  (`generated_entities.dl_bin`, stride 2552 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 928 | ComponentIndexData (`0xFCDFC705`) |  |
| 928 | 1624 | SpawnOnPlayersComponent (`0x618C4AF9`) |  |

### PowerSwitchTargetComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 12 | PowerSwitchTargetComponent (`0x8352E479`) |  |

### ResourceDependencyComponentData  (`generated_entities.dl_bin`, stride 65624 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 65536 | ComponentIndexData (`0xFCDFC705`) |  |
| 65536 | 88 | ResourceDependencyComponent (`0x8611A8BA`) |  |

### StratagemScramblerComponentData  (`generated_entities.dl_bin`, stride 240 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 112 | StratagemScramblerComponent (`0x665F3DD6`) |  |

### ObjectiveWidgetPriorityComponentData  (`generated_entities.dl_bin`, stride 544 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) |  |
| 480 | 64 | ObjectiveWidgetPriorityComponent (`0x4FFCA954`) |  |

### 0xA43A4273  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 4 | 0x7FDC1DB9 (`0x7FDC1DB9`) |  |

### OrbitalTargetPriorityComponentData  (`generated_entities.dl_bin`, stride 288 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 32 | OrbitalTargetPriorityComponent (`0x451F5F69`) |  |

### NpcDialogueComponentData  (`generated_entities.dl_bin`, stride 4312 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2464 | ComponentIndexData (`0xFCDFC705`) |  |
| 2464 | 1848 | NpcDialogueComponent (`0x9559E9DE`) |  |

### ObjectiveVehicleDeliveryComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 8 | ObjectiveVehicleDeliveryComponent (`0xEF1B98B2`) |  |

### StratagemBlockerComponentData  (`generated_entities.dl_bin`, stride 368 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) |  |
| 224 | 140 | StratagemBlockerComponent (`0xAABFE3FD`) |  |

### LoadoutPackageComponentData  (`generated_entities.dl_bin`, stride 35232 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 17600 | ComponentIndexData (`0xFCDFC705`) |  |
| 17600 | 17632 | LoadoutPackageComponent (`0x2B9E02D7`) |  |

### LoadoutEntryComponentData  (`generated_entities.dl_bin`, stride 13536 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6368 | ComponentIndexData (`0xFCDFC705`) |  |
| 6368 | 6368 | LoadoutEntryComponent (`0x838F9D5D`) |  |
| 12736 | 796 | 0x00000000 (`0x00000000`) | 7a01000036010000 |

### ReinforcementLocationComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 4 | ReinforcementLocationComponent (`0xBB40DC5D`) |  |

### ObjectiveCarryDeployAreaComponentData  (`generated_entities.dl_bin`, stride 176 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 48 | ObjectiveCarryDeployAreaComponent (`0xC81BC175`) |  |

### MeleeAttackComponentData  (`generated_entities.dl_bin`, stride 8032 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5344 | ComponentIndexData (`0xFCDFC705`) |  |
| 5344 | 2688 | MeleeAttackComponent (`0xDBCED0D3`) |  |

### ShipCustomizationComponentData  (`generated_entities.dl_bin`, stride 12368 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 12336 | ShipCustomizationComponent (`0x415F5D20`) |  |

### MusicIntensifierComponentData  (`generated_entities.dl_bin`, stride 7336 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4192 | ComponentIndexData (`0xFCDFC705`) |  |
| 4192 | 3144 | MusicIntensifierComponent (`0x3467A794`) |  |

### LevitationAreaComponentData  (`generated_entities.dl_bin`, stride 96 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 32 | LevitationAreaComponent (`0xF8CA046B`) |  |

### PrespawnLocationComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 16 | PrespawnLocationComponent (`0x5B5B149C`) |  |

### ObjectiveDeliverableVehicleComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 4 | ObjectiveDeliverableVehicleComponent (`0x9B8A15CD`) |  |

### ShipModulesSyncComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 40 | ShipModulesSyncComponent (`0x27085D9D`) |  |

### ShipMasterComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 132 | ShipMasterComponent (`0x670FD5D3`) |  |

### KillStreakComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 136 | KillStreakComponent (`0x301E5EC9`) |  |

### KeypadCodeRevealComponentData  (`generated_entities.dl_bin`, stride 216 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 24 | KeypadCodeRevealComponent (`0x5704118B`) |  |

### ObjectiveConvoyComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 8 | ObjectiveConvoyComponent (`0x22A86C2C`) |  |

### TutorialComponentData  (`generated_entities.dl_bin`, stride 296 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 260 | TutorialComponent (`0x51F51E27`) |  |

### DamagePropagatorComponentData  (`generated_entities.dl_bin`, stride 472 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) |  |
| 416 | 52 | DamagePropagatorComponent (`0x6003FF51`) |  |

### EffectSwitcherComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 128 | EffectSwitcherComponent (`0xD02E4C49`) |  |

### AiSquadMemberComponentData  (`generated_entities.dl_bin`, stride 6648 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4832 | ComponentIndexData (`0xFCDFC705`) |  |
| 4832 | 1812 | AiSquadMemberComponent (`0x566AA053`) |  |

### BackpackComponentData  (`generated_entities.dl_bin`, stride 1160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1120 | ComponentIndexData (`0xFCDFC705`) |  |
| 1120 | 35 | BackpackComponent (`0x2612EF83`) |  |

### VehicleCollisionInfoComponentData  (`generated_entities.dl_bin`, stride 6376 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5664 | ComponentIndexData (`0xFCDFC705`) |  |
| 5664 | 708 | VehicleCollisionInfoComponent (`0x32D207AB`) |  |

### DormancyComponentData  (`generated_entities.dl_bin`, stride 616 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) |  |
| 448 | 168 | DormancyComponent (`0x0CBCC690`) |  |

### WeaponAttachmentComponentData  (`generated_entities.dl_bin`, stride 400 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 44 | WeaponAttachmentComponent (`0xF2135B86`) |  |

### BackblastComponentData  (`generated_entities.dl_bin`, stride 2080 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) |  |
| 672 | 1408 | BackblastComponent (`0x91A80A1A`) |  |

### WeaponAssistedReloadComponentData  (`generated_entities.dl_bin`, stride 952 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) |  |
| 224 | 728 | WeaponAssistedReloadComponent (`0x2D56A994`) |  |

### VehicleStorageComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 128 | VehicleStorageComponent (`0xA8DA5E48`) |  |

### CharacterVoiceComponentData  (`generated_entities.dl_bin`, stride 112 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 16 | CharacterVoiceComponent (`0x4525A336`) |  |

### ExplorationRewardComponentData  (`generated_entities.dl_bin`, stride 336 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 144 | ExplorationRewardComponent (`0x647E42CD`) |  |

### EquipmentShowcaseComponentData  (`generated_entities.dl_bin`, stride 20520 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5472 | ComponentIndexData (`0xFCDFC705`) |  |
| 5472 | 15048 | EquipmentShowcaseComponent (`0x2C220E88`) |  |

### BuoyancyComponentData  (`generated_entities.dl_bin`, stride 2376 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) |  |
| 288 | 2088 | BuoyancyComponent (`0x0D74501D`) |  |

### VoIntensityComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 124 | VoIntensityComponent (`0x23F8E07F`) |  |

### VistaShipPositionComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 48 | VistaShipPositionComponent (`0xF5EF3823`) |  |

### WeatherControlComponentData  (`generated_entities.dl_bin`, stride 648 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) |  |
| 288 | 360 | WeatherControlComponent (`0x5D3CD804`) |  |

### WeaponWindUpComponentData  (`generated_entities.dl_bin`, stride 648 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) |  |
| 288 | 360 | WeaponWindUpComponent (`0x600754B4`) |  |

### EncyclopediaEntryComponentData  (`generated_entities.dl_bin`, stride 59400 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 21600 | ComponentIndexData (`0xFCDFC705`) |  |
| 21600 | 37800 | EncyclopediaEntryComponent (`0x85C25B75`) |  |

### EnemyPackageComponentData  (`generated_entities.dl_bin`, stride 10240 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5120 | ComponentIndexData (`0xFCDFC705`) |  |
| 5120 | 5120 | EnemyPackageComponent (`0xD2502C9D`) |  |

### 0x2CDEC6D5  (`generated_entities.dl_bin`, stride 136 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 100 | 0xF579C11B (`0xF579C11B`) |  |

### CorpseDecayerComponentData  (`generated_entities.dl_bin`, stride 2360 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1888 | ComponentIndexData (`0xFCDFC705`) |  |
| 1888 | 472 | CorpseDecayerComponent (`0x98269C3C`) |  |

### ConvoyComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 12 | ConvoyComponent (`0x2DE556F1`) |  |

### EnvironmentalHazardComponentData  (`generated_entities.dl_bin`, stride 680 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) |  |
| 416 | 260 | EnvironmentalHazardComponent (`0xC456924F`) |  |

### VistaEffectComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 4 | VistaEffectComponent (`0x99B83B87`) |  |

### EntityBindComponentData  (`generated_entities.dl_bin`, stride 3240 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2880 | ComponentIndexData (`0xFCDFC705`) |  |
| 2880 | 360 | EntityBindComponent (`0xE37B720D`) |  |

### EnvironmentalEffectTagComponentData  (`generated_entities.dl_bin`, stride 480 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 384 | ComponentIndexData (`0xFCDFC705`) |  |
| 384 | 96 | EnvironmentalEffectTagComponent (`0x2231511E`) |  |

### WorldLootManagerComponentData  (`generated_entities.dl_bin`, stride 30024 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) |  |
| 608 | 29412 | WorldLootManagerComponent (`0x2A037914`) |  |

### StaticPositionComponentData  (`generated_entities.dl_bin`, stride 3832 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 3712 | ComponentIndexData (`0xFCDFC705`) |  |
| 3712 | 116 | StaticPositionComponent (`0x15C2CDB0`) |  |

### UnitComponentData  (`generated_entities.dl_bin`, stride 288928 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 55008 | ComponentIndexData (`0xFCDFC705`) |  |
| 55008 | 233920 | UnitComponent (`0x18ECD593`) |  |

### MaterialSwapComponentData  (`generated_entities.dl_bin`, stride 92160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1536 | ComponentIndexData (`0xFCDFC705`) |  |
| 1536 | 90624 | MaterialSwapComponent (`0xFB9C3D3D`) |  |

### FactionComponentData  (`generated_entities.dl_bin`, stride 98224 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 17056 | ComponentIndexData (`0xFCDFC705`) |  |
| 17056 | 81168 | FactionComponent (`0x37DA66D7`) |  |

### VehicleComponentData  (`generated_entities.dl_bin`, stride 78424 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 640 | ComponentIndexData (`0xFCDFC705`) |  |
| 640 | 77784 | VehicleComponent (`0x6D4CC953`) |  |

### ObjectiveComponentData  (`generated_entities.dl_bin`, stride 593712 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6944 | ComponentIndexData (`0xFCDFC705`) |  |
| 6944 | 586768 | ObjectiveComponent (`0x4EB42DEE`) |  |

### MinefieldComponentData  (`generated_entities.dl_bin`, stride 1032 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) |  |
| 416 | 616 | MinefieldComponent (`0xF285D860`) |  |

### ShieldComponentData  (`generated_entities.dl_bin`, stride 5984 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) |  |
| 480 | 5504 | ShieldComponent (`0x11A2352C`) |  |

### OrbitalShipComponentData  (`generated_entities.dl_bin`, stride 568 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) |  |
| 544 | 17 | OrbitalShipComponent (`0x03901E14`) |  |

### NoiseComponentData  (`generated_entities.dl_bin`, stride 880 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 704 | ComponentIndexData (`0xFCDFC705`) |  |
| 704 | 176 | NoiseComponent (`0xD9CFC111`) |  |

### SquadTransportComponentData  (`generated_entities.dl_bin`, stride 1200 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 1008 | SquadTransportComponent (`0x0AFBAD9E`) |  |

### 0xF34610E9  (`generated_entities.dl_bin`, stride 112 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 12 | 0x12C7212F (`0x12C7212F`) |  |

### RechargeComponentData  (`generated_entities.dl_bin`, stride 112 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 16 | RechargeComponent (`0x69900D54`) |  |

### InteractableMinigameComponentData  (`generated_entities.dl_bin`, stride 795232 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2400 | ComponentIndexData (`0xFCDFC705`) |  |
| 2400 | 792832 | InteractableMinigameComponent (`0x4169A708`) |  |

### ObjectiveCarryDeliveryComponentData  (`generated_entities.dl_bin`, stride 952 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) |  |
| 544 | 408 | ObjectiveCarryDeliveryComponent (`0xA5B0C973`) |  |

### DestructibleComponentData  (`generated_entities.dl_bin`, stride 9872 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 9568 | ComponentIndexData (`0xFCDFC705`) |  |
| 9568 | 299 | DestructibleComponent (`0xA4FFE67D`) |  |

### EffectReferenceComponentData  (`generated_entities.dl_bin`, stride 2733192 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 22176 | ComponentIndexData (`0xFCDFC705`) |  |
| 22176 | 2711016 | EffectReferenceComponent (`0xC98E550F`) |  |

### CollisionEventComponentData  (`generated_entities.dl_bin`, stride 30848 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 15424 | ComponentIndexData (`0xFCDFC705`) |  |
| 15424 | 15424 | CollisionEventComponent (`0x907000C1`) |  |

### PhysicsImpactEffectComponentData  (`generated_entities.dl_bin`, stride 49232 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 11584 | ComponentIndexData (`0xFCDFC705`) |  |
| 11584 | 37648 | PhysicsImpactEffectComponent (`0x3F0D9F21`) |  |

### PoweredDeathSequenceComponentData  (`generated_entities.dl_bin`, stride 17280 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2880 | ComponentIndexData (`0xFCDFC705`) |  |
| 2880 | 14400 | PoweredDeathSequenceComponent (`0xBF027488`) |  |

### WeaponScreenComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 8 | WeaponScreenComponent (`0x2B8DF91D`) |  |

### PowerSwitchComponentData  (`generated_entities.dl_bin`, stride 1872 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1152 | ComponentIndexData (`0xFCDFC705`) |  |
| 1152 | 720 | PowerSwitchComponent (`0x5C13F512`) |  |

### WoundableComponentData  (`generated_entities.dl_bin`, stride 6384 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 3648 | ComponentIndexData (`0xFCDFC705`) |  |
| 3648 | 2736 | WoundableComponent (`0x432D1854`) |  |

### WieldableComponentData  (`generated_entities.dl_bin`, stride 32960 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16480 | ComponentIndexData (`0xFCDFC705`) |  |
| 16480 | 16480 | WieldableComponent (`0xC83092BC`) |  |

### RemoteTriggerComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 4 | RemoteTriggerComponent (`0x42C6F973`) |  |

### WeaponReloadComponentData  (`generated_entities.dl_bin`, stride 28528 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8128 | ComponentIndexData (`0xFCDFC705`) |  |
| 8128 | 20400 | WeaponReloadComponent (`0xCE31EB14`) |  |

### RagdollSyncComponentData  (`generated_entities.dl_bin`, stride 136136 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2464 | ComponentIndexData (`0xFCDFC705`) |  |
| 2464 | 133672 | RagdollSyncComponent (`0xDF297875`) |  |

### WeaponLinkerComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 48 | WeaponLinkerComponent (`0x107DA162`) |  |

### WarHologramComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 44 | WarHologramComponent (`0xF84673F6`) |  |

### WeaponRoundsComponentData  (`generated_entities.dl_bin`, stride 4336 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 800 | ComponentIndexData (`0xFCDFC705`) |  |
| 800 | 3536 | WeaponRoundsComponent (`0x84CCC438`) |  |

### ProjectileClusterComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 16 | ProjectileClusterComponent (`0x77A73C46`) |  |

### StanceComponentData  (`generated_entities.dl_bin`, stride 5984 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 704 | ComponentIndexData (`0xFCDFC705`) |  |
| 704 | 5280 | StanceComponent (`0x6A0316F1`) |  |

### SquadTransportFormationComponentData  (`generated_entities.dl_bin`, stride 7200 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2880 | ComponentIndexData (`0xFCDFC705`) |  |
| 2880 | 4320 | SquadTransportFormationComponent (`0xD829390D`) |  |

### StatusEffectVolumeComponentData  (`generated_entities.dl_bin`, stride 6176 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 5920 | StatusEffectVolumeComponent (`0x6FE5E9DC`) |  |

### SpawnLinkComponentData  (`generated_entities.dl_bin`, stride 1800 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 960 | ComponentIndexData (`0xFCDFC705`) |  |
| 960 | 840 | SpawnLinkComponent (`0x2E612FAA`) |  |

### SpottableComponentData  (`generated_entities.dl_bin`, stride 72800 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 22400 | ComponentIndexData (`0xFCDFC705`) |  |
| 22400 | 50400 | SpottableComponent (`0x5C1FBB21`) |  |

### TargetableFleetShipComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 16 | TargetableFleetShipComponent (`0xA613E132`) |  |

### TrampleComponentData  (`generated_entities.dl_bin`, stride 13816 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5024 | ComponentIndexData (`0xFCDFC705`) |  |
| 5024 | 8792 | TrampleComponent (`0xBA9960E8`) |  |

### TriggerAreaLogicComponentData  (`generated_entities.dl_bin`, stride 768 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 512 | TriggerAreaLogicComponent (`0xC98D5D6E`) |  |

### StratagemFiresupportComponentData  (`generated_entities.dl_bin`, stride 616 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) |  |
| 544 | 68 | StratagemFiresupportComponent (`0xABC88BDE`) |  |

### TransportComponentData  (`generated_entities.dl_bin`, stride 1008 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) |  |
| 448 | 560 | TransportComponent (`0x35CCCFC0`) |  |

### VehicleShuttleComponentData  (`generated_entities.dl_bin`, stride 664 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 308 | VehicleShuttleComponent (`0x40A01E7C`) |  |

### ShipCustomizationTargetComponentData  (`generated_entities.dl_bin`, stride 504 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) |  |
| 160 | 340 | ShipCustomizationTargetComponent (`0xD33B9F07`) |  |

### ShieldControllerComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 8 | ShieldControllerComponent (`0xC7041FD0`) |  |

### SensorDangerComponentData  (`generated_entities.dl_bin`, stride 8408 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6112 | ComponentIndexData (`0xFCDFC705`) |  |
| 6112 | 2292 | SensorDangerComponent (`0x0A6D35FE`) |  |

### ShowOnMapComponentData  (`generated_entities.dl_bin`, stride 2080 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 832 | ComponentIndexData (`0xFCDFC705`) |  |
| 832 | 1248 | ShowOnMapComponent (`0x9433E54F`) |  |

### TutorialTargetRangeComponentData  (`generated_entities.dl_bin`, stride 312 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 248 | TutorialTargetRangeComponent (`0x1B78079B`) |  |

### ShipPropVisibilityComponentData  (`generated_entities.dl_bin`, stride 1160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) |  |
| 544 | 612 | ShipPropVisibilityComponent (`0x83724730`) |  |

### ShipTeleporterComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 12 | ShipTeleporterComponent (`0xCD6AB78D`) |  |

### FireSourceComponentData  (`generated_entities.dl_bin`, stride 104 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 40 | FireSourceComponent (`0x0C33606A`) |  |

### 0xCE728CA9  (`generated_entities.dl_bin`, stride 256 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 192 | 0x298BBCEF (`0x298BBCEF`) |  |

### FakeGravityMotionComponentData  (`generated_entities.dl_bin`, stride 360 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 168 | FakeGravityMotionComponent (`0xC6AC7AC6`) |  |

### MaterialVariablesComponentData  (`generated_entities.dl_bin`, stride 119072 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1952 | ComponentIndexData (`0xFCDFC705`) |  |
| 1952 | 117120 | MaterialVariablesComponent (`0x6B91FB5B`) |  |

### LootDropComponentData  (`generated_entities.dl_bin`, stride 1664 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 832 | ComponentIndexData (`0xFCDFC705`) |  |
| 832 | 832 | LootDropComponent (`0x3A79E786`) |  |

### GameEventShipComponentData  (`generated_entities.dl_bin`, stride 7976 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 7944 | GameEventShipComponent (`0x0C1C32E3`) |  |

### FogMachineComponentData  (`generated_entities.dl_bin`, stride 1584 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 704 | ComponentIndexData (`0xFCDFC705`) |  |
| 704 | 880 | FogMachineComponent (`0x4DDF3CE4`) |  |

### ExtractionZoneComponentData  (`generated_entities.dl_bin`, stride 104 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 6 | ExtractionZoneComponent (`0x37340A30`) |  |

### MinigameStratagemArcadeComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 44 | MinigameStratagemArcadeComponent (`0xA77CF722`) |  |

### MinigameWaitComponentData  (`generated_entities.dl_bin`, stride 6960 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1856 | ComponentIndexData (`0xFCDFC705`) |  |
| 1856 | 5104 | MinigameWaitComponent (`0x8B438E0F`) |  |

### MinigameExternalSwitchesComponentData  (`generated_entities.dl_bin`, stride 2856 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) |  |
| 672 | 2184 | MinigameExternalSwitchesComponent (`0xCBE67607`) |  |

### DynamicLightComponentData  (`generated_entities.dl_bin`, stride 488 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 132 | DynamicLightComponent (`0xE14B4B70`) |  |

### HellpodRackComponentData  (`generated_entities.dl_bin`, stride 43768 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2304 | ComponentIndexData (`0xFCDFC705`) |  |
| 2304 | 41464 | HellpodRackComponent (`0x817B931C`) |  |

### InteractableObjectiveTerminalComponentData  (`generated_entities.dl_bin`, stride 9640 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2336 | ComponentIndexData (`0xFCDFC705`) |  |
| 2336 | 7300 | InteractableObjectiveTerminalComponent (`0x89F44898`) |  |

### InteractableStateSwitchComponentData  (`generated_entities.dl_bin`, stride 7400 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 800 | ComponentIndexData (`0xFCDFC705`) |  |
| 800 | 6600 | InteractableStateSwitchComponent (`0x1B0491B4`) |  |

### AnimationComponentData  (`generated_entities.dl_bin`, stride 110880 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 24640 | ComponentIndexData (`0xFCDFC705`) |  |
| 24640 | 86240 | AnimationComponent (`0x4210E273`) |  |

### HitReactComponentData  (`generated_entities.dl_bin`, stride 954128 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6272 | ComponentIndexData (`0xFCDFC705`) |  |
| 6272 | 947856 | HitReactComponent (`0xC299C547`) |  |

### HintTriggerComponentData  (`generated_entities.dl_bin`, stride 8640 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 3840 | ComponentIndexData (`0xFCDFC705`) |  |
| 3840 | 4800 | HintTriggerComponent (`0x43AB1F7A`) |  |

### HellpodPayloadComponentData  (`generated_entities.dl_bin`, stride 5160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 3744 | ComponentIndexData (`0xFCDFC705`) |  |
| 3744 | 1416 | HellpodPayloadComponent (`0x4B889585`) |  |

### AttackPatternComponentData  (`generated_entities.dl_bin`, stride 2208 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 2176 | AttackPatternComponent (`0xCE83B069`) |  |

### LootContainerComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 8 | LootContainerComponent (`0x93703274`) |  |

### GibEntityComponentData  (`generated_entities.dl_bin`, stride 1264 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) |  |
| 480 | 780 | GibEntityComponent (`0xE93DC9C2`) |  |

### LaserDesignatorComponentData  (`generated_entities.dl_bin`, stride 384 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 256 | LaserDesignatorComponent (`0xB7D3043A`) |  |

### ObjectiveRescuePointComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 128 | ObjectiveRescuePointComponent (`0x6082C7BF`) |  |

### ObjectiveSecureAreaComponentData  (`generated_entities.dl_bin`, stride 472 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 340 | ObjectiveSecureAreaComponent (`0xE656A5CE`) |  |

### CarryEffectComponentData  (`generated_entities.dl_bin`, stride 264 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) |  |
| 160 | 100 | CarryEffectComponent (`0xFD2E3F41`) |  |

### ObjectiveOilRigComponentData  (`generated_entities.dl_bin`, stride 256 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 128 | ObjectiveOilRigComponent (`0x7C9E8EF4`) |  |

### ObjectivePreventInvasionComponentData  (`generated_entities.dl_bin`, stride 376 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 344 | ObjectivePreventInvasionComponent (`0xDF5D1959`) |  |

### 0x430CA328  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 16 | 0x29786BEE (`0x29786BEE`) |  |

### ObjectiveShellComponentData  (`generated_entities.dl_bin`, stride 512 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 256 | ObjectiveShellComponent (`0x05330626`) |  |

### ObstacleComponentData  (`generated_entities.dl_bin`, stride 704 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) |  |
| 224 | 476 | ObstacleComponent (`0x446996E0`) |  |

### DangerWarningComponentData  (`generated_entities.dl_bin`, stride 1456 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1056 | ComponentIndexData (`0xFCDFC705`) |  |
| 1056 | 396 | DangerWarningComponent (`0xF3B0BFBA`) |  |

### DepositComponentData  (`generated_entities.dl_bin`, stride 5672 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 960 | ComponentIndexData (`0xFCDFC705`) |  |
| 960 | 4712 | DepositComponent (`0x038A5CCB`) |  |

### ObjectiveShellRackComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 12 | ObjectiveShellRackComponent (`0x54FF6027`) |  |

### ObjectiveShuttleControllerComponentData  (`generated_entities.dl_bin`, stride 480 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) |  |
| 160 | 320 | ObjectiveShuttleControllerComponent (`0x2D347B1B`) |  |

### NetworkPhysicsComponentData  (`generated_entities.dl_bin`, stride 14064 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 9376 | ComponentIndexData (`0xFCDFC705`) |  |
| 9376 | 4688 | NetworkPhysicsComponent (`0x2C6F4C60`) |  |

### 0x88630F9F  (`generated_entities.dl_bin`, stride 56 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 24 | 0x3C3534E5 (`0x3C3534E5`) |  |

### AiSpawnerComponentData  (`generated_entities.dl_bin`, stride 7528 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1056 | ComponentIndexData (`0xFCDFC705`) |  |
| 1056 | 6468 | AiSpawnerComponent (`0xFE7D9FBD`) |  |

### BurrowerComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 72 | BurrowerComponent (`0x56B9460B`) |  |

### ObjectiveEncounterTriggerComponentData  (`generated_entities.dl_bin`, stride 816 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) |  |
| 224 | 588 | ObjectiveEncounterTriggerComponent (`0x9BF2F6F5`) |  |

### 0xF57457DA  (`generated_entities.dl_bin`, stride 107744 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) |  |
| 416 | 107328 | 0x32AD97A0 (`0x32AD97A0`) |  |

### ObjectiveDynamicLinkComponentData  (`generated_entities.dl_bin`, stride 1984 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1440 | ComponentIndexData (`0xFCDFC705`) |  |
| 1440 | 540 | ObjectiveDynamicLinkComponent (`0xCE273501`) |  |

### ObjectiveCarryComponentData  (`generated_entities.dl_bin`, stride 6400 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1280 | ComponentIndexData (`0xFCDFC705`) |  |
| 1280 | 5120 | ObjectiveCarryComponent (`0xF6A785AF`) |  |

### ObjectiveCollectResourcesComponentData  (`generated_entities.dl_bin`, stride 96 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 32 | ObjectiveCollectResourcesComponent (`0xCE4458AF`) |  |

### 0xF087811C  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 96 | 0x666A6FE2 (`0x666A6FE2`) |  |

### SensorEyeComponentData  (`generated_entities.dl_bin`, stride 23984 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 10080 | ComponentIndexData (`0xFCDFC705`) |  |
| 10080 | 13904 | SensorEyeComponent (`0xB4789330`) |  |

### SensorEarComponentData  (`generated_entities.dl_bin`, stride 8976 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5984 | ComponentIndexData (`0xFCDFC705`) |  |
| 5984 | 2992 | SensorEarComponent (`0x6850F3C5`) |  |

### BombardmentComponentData  (`generated_entities.dl_bin`, stride 5344 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) |  |
| 736 | 4608 | BombardmentComponent (`0x0793349E`) |  |

### ShieldHitFilterComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 4 | ShieldHitFilterComponent (`0x81976017`) |  |

### SensorProximityComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 16 | SensorProximityComponent (`0x48572122`) |  |

### SeekingMissileComponentData  (`generated_entities.dl_bin`, stride 8816 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 928 | ComponentIndexData (`0xFCDFC705`) |  |
| 928 | 7888 | SeekingMissileComponent (`0x2DD927CF`) |  |

### CharacterTemplateComponentData  (`generated_entities.dl_bin`, stride 1928 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1184 | ComponentIndexData (`0xFCDFC705`) |  |
| 1184 | 740 | CharacterTemplateComponent (`0x791CC75C`) |  |

### VisibilityMaskComponentData  (`generated_entities.dl_bin`, stride 184128 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8768 | ComponentIndexData (`0xFCDFC705`) |  |
| 8768 | 175360 | VisibilityMaskComponent (`0xB4E1B587`) |  |

### MineSpawnerComponentData  (`generated_entities.dl_bin`, stride 512 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 256 | MineSpawnerComponent (`0xC57D209C`) |  |

### DecorationComponentData  (`generated_entities.dl_bin`, stride 672 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 640 | DecorationComponent (`0xB662B2FB`) |  |

### LandingZoneBeaconComponentData  (`generated_entities.dl_bin`, stride 104 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 3 | LandingZoneBeaconComponent (`0xBEA608B4`) |  |

### WeaponFlashlightComponentData  (`generated_entities.dl_bin`, stride 592 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) |  |
| 224 | 364 | WeaponFlashlightComponent (`0x0CDB8E03`) |  |

### WeaponChargeComponentData  (`generated_entities.dl_bin`, stride 2696 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 320 | ComponentIndexData (`0xFCDFC705`) |  |
| 320 | 2376 | WeaponChargeComponent (`0x3CBEA9E7`) |  |

### HellpodComponentData  (`generated_entities.dl_bin`, stride 1088 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 832 | HellpodComponent (`0xA5EA069B`) |  |

### UnitCustomizationComponentData  (`generated_entities.dl_bin`, stride 107832 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 3072 | ComponentIndexData (`0xFCDFC705`) |  |
| 3072 | 104760 | UnitCustomizationComponent (`0xC90D306C`) |  |

### NavigationComponentData  (`generated_entities.dl_bin`, stride 10960 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 7968 | ComponentIndexData (`0xFCDFC705`) |  |
| 7968 | 2988 | NavigationComponent (`0x7F6D5483`) |  |

### RaycastSchedulerComponentData  (`generated_entities.dl_bin`, stride 352 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 320 | RaycastSchedulerComponent (`0x6CC37AA9`) |  |

### GuardForceComponentData  (`generated_entities.dl_bin`, stride 1008 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) |  |
| 672 | 336 | GuardForceComponent (`0x428D2095`) |  |

### GameModeMissionComponentData  (`generated_entities.dl_bin`, stride 648 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) |  |
| 544 | 102 | GameModeMissionComponent (`0xBD4E2734`) |  |

### HiveMindComponentData  (`generated_entities.dl_bin`, stride 22288 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) |  |
| 608 | 21680 | HiveMindComponent (`0xFFF1A667`) |  |

### TruthTransmitterFactionComponentData  (`generated_entities.dl_bin`, stride 416 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 384 | TruthTransmitterFactionComponent (`0x960B7A2B`) |  |

### EncounterComponentData  (`generated_entities.dl_bin`, stride 64 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 32 | EncounterComponent (`0xB183DDE6`) |  |

### BugholeComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 80 | BugholeComponent (`0x6E65CD39`) |  |

### 0xE3F485C7  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 112 | 0xE371D70D (`0xE371D70D`) |  |

### GroundCheckComponentData  (`generated_entities.dl_bin`, stride 12952 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 7968 | ComponentIndexData (`0xFCDFC705`) |  |
| 7968 | 4980 | GroundCheckComponent (`0x7A8BC440`) |  |

### GuidanceTargetComponentData  (`generated_entities.dl_bin`, stride 1528 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) |  |
| 288 | 1240 | GuidanceTargetComponent (`0x4E6C92FA`) |  |

### MovingHazardComponentData  (`generated_entities.dl_bin`, stride 384 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 192 | MovingHazardComponent (`0xEB79BE1D`) |  |

### SearchlightEnemyComponentData  (`generated_entities.dl_bin`, stride 192 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 128 | SearchlightEnemyComponent (`0x87D0A7BF`) |  |

### OverlapDamageComponentData  (`generated_entities.dl_bin`, stride 100864 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2048 | ComponentIndexData (`0xFCDFC705`) |  |
| 2048 | 98816 | OverlapDamageComponent (`0xF38A964B`) |  |

### HealthComponentData  (`generated_entities.dl_bin`, stride 11218864 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16192 | ComponentIndexData (`0xFCDFC705`) |  |
| 16192 | 11202672 | HealthComponent (`0x728F0129`) |  |

### VehicleMotionComponentData  (`generated_entities.dl_bin`, stride 6832 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) |  |
| 448 | 6384 | VehicleMotionComponent (`0x48F7C789`) |  |

### MeleeShieldComponentData  (`generated_entities.dl_bin`, stride 176 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 108 | MeleeShieldComponent (`0x7E824934`) |  |

### DamageZoneShieldComponentData  (`generated_entities.dl_bin`, stride 35136 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 34944 | DamageZoneShieldComponent (`0x868B11A7`) |  |

### GoreComponentData  (`generated_entities.dl_bin`, stride 7039200 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6720 | ComponentIndexData (`0xFCDFC705`) |  |
| 6720 | 7032480 | GoreComponent (`0x66518C40`) |  |

### VehicleElectricsComponentData  (`generated_entities.dl_bin`, stride 34112 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) |  |
| 416 | 33696 | VehicleElectricsComponent (`0x5322DCD1`) |  |

### AvatarComponentData  (`generated_entities.dl_bin`, stride 1736 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 1704 | AvatarComponent (`0xB501F712`) |  |

### EquipmentComponentData  (`generated_entities.dl_bin`, stride 92896 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 11232 | ComponentIndexData (`0xFCDFC705`) |  |
| 11232 | 81664 | EquipmentComponent (`0xD4967A6B`) |  |

### TargetingComponentData  (`generated_entities.dl_bin`, stride 28512 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 9504 | ComponentIndexData (`0xFCDFC705`) |  |
| 9504 | 19008 | TargetingComponent (`0x5E30EC98`) |  |

### WeaponWielderComponentData  (`generated_entities.dl_bin`, stride 15032 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 7072 | ComponentIndexData (`0xFCDFC705`) |  |
| 7072 | 7956 | WeaponWielderComponent (`0x967FB669`) |  |

### WeaponDataComponentData  (`generated_entities.dl_bin`, stride 475696 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 11936 | ComponentIndexData (`0xFCDFC705`) |  |
| 11936 | 463760 | WeaponDataComponent (`0xD25FC7F7`) |  |

### InventoryComponentData  (`generated_entities.dl_bin`, stride 15280 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2752 | ComponentIndexData (`0xFCDFC705`) |  |
| 2752 | 12528 | InventoryComponent (`0x1BBAEB81`) |  |

### MultiTargetComponentData  (`generated_entities.dl_bin`, stride 22016 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1024 | ComponentIndexData (`0xFCDFC705`) |  |
| 1024 | 20988 | MultiTargetComponent (`0x23A58AC5`) |  |

### InteractorComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 48 | InteractorComponent (`0xB52212CE`) |  |

### InteractableComponentData  (`generated_entities.dl_bin`, stride 638432 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 17984 | ComponentIndexData (`0xFCDFC705`) |  |
| 17984 | 620448 | InteractableComponent (`0xB6109121`) |  |

### RotationSoundPlayerComponentData  (`generated_entities.dl_bin`, stride 832 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) |  |
| 288 | 540 | RotationSoundPlayerComponent (`0xB1FA2519`) |  |

### WeaponLinkedAmmoComponentData  (`generated_entities.dl_bin`, stride 584 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 392 | WeaponLinkedAmmoComponent (`0xFCBC2A9E`) |  |

### StickyComponentData  (`generated_entities.dl_bin`, stride 2056 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) |  |
| 608 | 1444 | StickyComponent (`0x463F606A`) |  |

### TurretComponentData  (`generated_entities.dl_bin`, stride 8072 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2368 | ComponentIndexData (`0xFCDFC705`) |  |
| 2368 | 5700 | TurretComponent (`0x98FFC0D9`) |  |

### StratagemBallComponentData  (`generated_entities.dl_bin`, stride 248 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 216 | StratagemBallComponent (`0xF3CBDB76`) |  |

### ShipInventoryComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 8 | ShipInventoryComponent (`0x42E63ED5`) |  |

### TwoPointChainAttachTargetComponentData  (`generated_entities.dl_bin`, stride 120 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 24 | TwoPointChainAttachTargetComponent (`0x1CD16F16`) |  |

### TwoPointChainComponentData  (`generated_entities.dl_bin`, stride 504 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 408 | TwoPointChainComponent (`0x953D943A`) |  |

### UploadDiscoveryComponentData  (`generated_entities.dl_bin`, stride 880 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 528 | UploadDiscoveryComponent (`0x596D1B70`) |  |

### ExplosiveComponentData  (`generated_entities.dl_bin`, stride 28192 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2272 | ComponentIndexData (`0xFCDFC705`) |  |
| 2272 | 25920 | ExplosiveComponent (`0xD866D252`) |  |

### CharacterNameComponentData  (`generated_entities.dl_bin`, stride 4368 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 2912 | ComponentIndexData (`0xFCDFC705`) |  |
| 2912 | 1456 | CharacterNameComponent (`0x8EDCA0C1`) |  |

### ThrowerComponentData  (`generated_entities.dl_bin`, stride 4672 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) |  |
| 160 | 4512 | ThrowerComponent (`0xCD78F59E`) |  |

### ThrowableComponentData  (`generated_entities.dl_bin`, stride 18032 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1472 | ComponentIndexData (`0xFCDFC705`) |  |
| 1472 | 16560 | ThrowableComponent (`0x5961C6FB`) |  |

### WeatheringComponentData  (`generated_entities.dl_bin`, stride 2656 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) |  |
| 544 | 2108 | WeatheringComponent (`0x39C02001`) |  |

### InteractableMenuScreenComponentData  (`generated_entities.dl_bin`, stride 1120 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) |  |
| 448 | 672 | InteractableMenuScreenComponent (`0x73B8EA16`) |  |

### AttachableComponentData  (`generated_entities.dl_bin`, stride 77952 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 25984 | ComponentIndexData (`0xFCDFC705`) |  |
| 25984 | 51968 | AttachableComponent (`0xCB1718DC`) |  |

### FriendlyNpcComponentData  (`generated_entities.dl_bin`, stride 77760 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 864 | ComponentIndexData (`0xFCDFC705`) |  |
| 864 | 76896 | FriendlyNpcComponent (`0xEE5DCCF1`) |  |

### JumppackComponentData  (`generated_entities.dl_bin`, stride 1216 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 1120 | JumppackComponent (`0x3A145ECE`) |  |

### ArcWeaponComponentData  (`generated_entities.dl_bin`, stride 1200 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 320 | ComponentIndexData (`0xFCDFC705`) |  |
| 320 | 880 | ArcWeaponComponent (`0x9BB0D833`) |  |

### WeaponHeatComponentData  (`generated_entities.dl_bin`, stride 19312 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 960 | ComponentIndexData (`0xFCDFC705`) |  |
| 960 | 18352 | WeaponHeatComponent (`0x3A90B51F`) |  |

### AbilityWeaponComponentData  (`generated_entities.dl_bin`, stride 1080 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) |  |
| 288 | 792 | AbilityWeaponComponent (`0x6EC1CEAB`) |  |

### MeleeWeaponComponentData  (`generated_entities.dl_bin`, stride 2464 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 2112 | MeleeWeaponComponent (`0xB1DBD585`) |  |

### PhysicsWeaponComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 8 | PhysicsWeaponComponent (`0x9BDCD9A0`) |  |

### BeamWeaponComponentData  (`generated_entities.dl_bin`, stride 3616 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) |  |
| 736 | 2880 | BeamWeaponComponent (`0x3DA202F2`) |  |

### WeaponCustomizationComponentData  (`generated_entities.dl_bin`, stride 966056 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6272 | ComponentIndexData (`0xFCDFC705`) |  |
| 6272 | 959784 | WeaponCustomizationComponent (`0xB976A896`) |  |

### EagleSpawnerComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 72 | EagleSpawnerComponent (`0x0CDA64D1`) |  |

### FoleySoundComponentData  (`generated_entities.dl_bin`, stride 637264 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6240 | ComponentIndexData (`0xFCDFC705`) |  |
| 6240 | 631020 | FoleySoundComponent (`0x5EC1F5FB`) |  |

### DisplacementComponentData  (`generated_entities.dl_bin`, stride 1296 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 1264 | DisplacementComponent (`0x56EC9F0C`) |  |

### AiCoverComponentData  (`generated_entities.dl_bin`, stride 496 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) |  |
| 480 | 15 | AiCoverComponent (`0x7710A1BC`) |  |

### CurveNavigationComponentData  (`generated_entities.dl_bin`, stride 784 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 752 | CurveNavigationComponent (`0x46E9D628`) |  |

### VehicleCollisionDamageComponentData  (`generated_entities.dl_bin`, stride 3360 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) |  |
| 448 | 2912 | VehicleCollisionDamageComponent (`0x76CC175E`) |  |

### FootstepEventComponentData  (`generated_entities.dl_bin`, stride 685560 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6304 | ComponentIndexData (`0xFCDFC705`) |  |
| 6304 | 679256 | FootstepEventComponent (`0xF7689E09`) |  |

### ExpandableCoverComponentData  (`generated_entities.dl_bin`, stride 392 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 328 | ExpandableCoverComponent (`0x4FA9D4E6`) |  |

### DetectorComponentData  (`generated_entities.dl_bin`, stride 17976 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 10272 | ComponentIndexData (`0xFCDFC705`) |  |
| 10272 | 7704 | DetectorComponent (`0xE7B724AD`) |  |

### MountComponentData  (`generated_entities.dl_bin`, stride 25048 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5248 | ComponentIndexData (`0xFCDFC705`) |  |
| 5248 | 19800 | MountComponent (`0x8BC6DEA6`) |  |

### BehaviorComponentData  (`generated_entities.dl_bin`, stride 43704 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 31776 | ComponentIndexData (`0xFCDFC705`) |  |
| 31776 | 11928 | BehaviorComponent (`0xF7420683`) |  |

### RouteNavigationComponentData  (`generated_entities.dl_bin`, stride 832 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) |  |
| 736 | 92 | RouteNavigationComponent (`0x6B40FFB2`) |  |

### SeatCollectionComponentData  (`generated_entities.dl_bin`, stride 25536 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1792 | ComponentIndexData (`0xFCDFC705`) |  |
| 1792 | 23744 | SeatCollectionComponent (`0xE014C64C`) |  |

### IdleAbilityComponentData  (`generated_entities.dl_bin`, stride 13568 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 3392 | ComponentIndexData (`0xFCDFC705`) |  |
| 3392 | 10176 | IdleAbilityComponent (`0xE3AFA17F`) |  |

### LoopingSurfaceEffectsComponentData  (`generated_entities.dl_bin`, stride 400 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 44 | LoopingSurfaceEffectsComponent (`0x3C4A0034`) |  |

### AbilityComponentData  (`generated_entities.dl_bin`, stride 63616 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 31808 | ComponentIndexData (`0xFCDFC705`) |  |
| 31808 | 31808 | AbilityComponent (`0x4DE4EBA1`) |  |

### CommanderComponentData  (`generated_entities.dl_bin`, stride 136 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) |  |
| 128 | 4 | CommanderComponent (`0xEB7BC449`) |  |

### ShipHellpodComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 8 | ShipHellpodComponent (`0x7DC074EF`) |  |

### HiveLordComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 8 | HiveLordComponent (`0xEBB9A230`) |  |

### ShipComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 8 | ShipComponent (`0x44504DC7`) |  |

### StoryInteractableComponentData  (`generated_entities.dl_bin`, stride 5280 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1920 | ComponentIndexData (`0xFCDFC705`) |  |
| 1920 | 3360 | StoryInteractableComponent (`0xFCA9E402`) |  |

### LootComponentData  (`generated_entities.dl_bin`, stride 6688 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1216 | ComponentIndexData (`0xFCDFC705`) |  |
| 1216 | 5472 | LootComponent (`0x9FB51CF1`) |  |

### BoidsComponentData  (`generated_entities.dl_bin`, stride 4232 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) |  |
| 736 | 3496 | BoidsComponent (`0x7AF25E84`) |  |

### ThrusterGroupComponentData  (`generated_entities.dl_bin`, stride 10368 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 864 | ComponentIndexData (`0xFCDFC705`) |  |
| 864 | 9504 | ThrusterGroupComponent (`0x193D4981`) |  |

### VehicleCrashComponentData  (`generated_entities.dl_bin`, stride 31680 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 576 | ComponentIndexData (`0xFCDFC705`) |  |
| 576 | 31104 | VehicleCrashComponent (`0xB5418864`) |  |

### HoverComponentData  (`generated_entities.dl_bin`, stride 960 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) |  |
| 256 | 704 | HoverComponent (`0xDC219A57`) |  |

### AiEnemyComponentData  (`generated_entities.dl_bin`, stride 122880 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 5120 | ComponentIndexData (`0xFCDFC705`) |  |
| 5120 | 117760 | AiEnemyComponent (`0xA53879FB`) |  |

### AiCharacterComponentData  (`generated_entities.dl_bin`, stride 22512 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6432 | ComponentIndexData (`0xFCDFC705`) |  |
| 6432 | 16080 | AiCharacterComponent (`0xD23B3E8A`) |  |

### AiSquadComponentData  (`generated_entities.dl_bin`, stride 3024 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) |  |
| 672 | 2352 | AiSquadComponent (`0x4AD82C9B`) |  |

### AiSquadBehaviorComponentData  (`generated_entities.dl_bin`, stride 760 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) |  |
| 672 | 84 | AiSquadBehaviorComponent (`0xC879B22B`) |  |

### AirborneNavigationComponentData  (`generated_entities.dl_bin`, stride 176 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 140 | AirborneNavigationComponent (`0x030B4335`) |  |

### StatusEffectReceiverComponentData  (`generated_entities.dl_bin`, stride 15388528 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 10528 | ComponentIndexData (`0xFCDFC705`) |  |
| 10528 | 15378000 | StatusEffectReceiverComponent (`0xF23ABD79`) |  |

### OrbitalAbilityComponentData  (`generated_entities.dl_bin`, stride 1768 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) |  |
| 64 | 1704 | OrbitalAbilityComponent (`0xAAFCF4CE`) |  |

### DrownableComponentData  (`generated_entities.dl_bin`, stride 5856 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 1952 | ComponentIndexData (`0xFCDFC705`) |  |
| 1952 | 3904 | DrownableComponent (`0x14DC6EB1`) |  |

### RotationComponentData  (`generated_entities.dl_bin`, stride 78968 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 7232 | ComponentIndexData (`0xFCDFC705`) |  |
| 7232 | 71732 | RotationComponent (`0x97646EE3`) |  |

### LocomotionComponentData  (`generated_entities.dl_bin`, stride 964592 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 6592 | ComponentIndexData (`0xFCDFC705`) |  |
| 6592 | 957996 | LocomotionComponent (`0x97313C56`) |  |

### FakeTankVehicleComponentData  (`generated_entities.dl_bin`, stride 224 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) |  |
| 160 | 60 | FakeTankVehicleComponent (`0x1143C438`) |  |

### VehicleLocomotionComponentData  (`generated_entities.dl_bin`, stride 360 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) |  |
| 192 | 168 | VehicleLocomotionComponent (`0xB18C54B6`) |  |

### SprayWeaponComponentData  (`generated_entities.dl_bin`, stride 6112 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) |  |
| 736 | 5376 | SprayWeaponComponent (`0x516D8AEC`) |  |

### 0x1DDF9A2D  (`generated_entities.dl_bin`, stride 64 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) |  |
| 32 | 32 | IlluminateAttackShipComponent (`0x1626A873`) |  |

### VehicleTracksComponentData  (`generated_entities.dl_bin`, stride 3912 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) |  |
| 96 | 3816 | VehicleTracksComponent (`0x66AC907B`) |  |

### MotionComponentData  (`generated_entities.dl_bin`, stride 22848 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 7616 | ComponentIndexData (`0xFCDFC705`) |  |
| 7616 | 15232 | MotionComponent (`0xC219DF29`) |  |

### EagleComponentData  (`generated_entities.dl_bin`, stride 4384 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) |  |
| 352 | 4032 | EagleComponent (`0x65EB85D1`) |  |

### ProjectileWeaponComponentData  (`generated_entities.dl_bin`, stride 180760 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8896 | ComponentIndexData (`0xFCDFC705`) |  |
| 8896 | 171864 | ProjectileWeaponComponent (`0x2290C42E`) |  |

### TargetAimConstraintComponentData  (`generated_entities.dl_bin`, stride 31144 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 7328 | ComponentIndexData (`0xFCDFC705`) |  |
| 7328 | 23816 | TargetAimConstraintComponent (`0x1700FA36`) |  |

### WeaponLaserComponentData  (`generated_entities.dl_bin`, stride 560 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 320 | ComponentIndexData (`0xFCDFC705`) |  |
| 320 | 240 | WeaponLaserComponent (`0x896AE274`) |  |

### ComponentEntityDeltaStorage  (`generated_entity_deltas.dl_bin`, stride 80 B, rows 4,403)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | EntityDeltaTypeData (`0x4AEE4D43`) |  |
| 16 | 16 | EntityDeltaSettings (`0x65984B18`) |  |
| 32 | 16 | ComponentDeltaSettings (`0x9A66FB2E`) |  |
| 48 | 16 | ComponentModificationDelta (`0x5D407DF3`) |  |
| 64 | 16 | 0x00000000 (`0x00000000`) | 8cb3010000000000 |

### EnvironmentSettings  (`generated_environment_settings.dl_bin`, stride 576 B, rows 17)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | PlanetType (`0x29EED886`) |  |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000240 · f32 8.07148e-43/0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x015827A8 · f32 3.970139e-38 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000247 · f32 8.16957e-43/0 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x8D49914A · f32 -6.211279e-31 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x85375151 · f32 -8.619554e-36 |
| 40 | 8 | 0x00000000 (`0x00000000`) | 0x7371C64D957E5C74 · f32 -5.13678e-26/1.91554e+31 |
| 48 | 8 | 0x00000000 (`0x00000000`) | 0x490E03DDBA81F222 · f32 -0.000991408/581694 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x826C3B62B5387EC7 · f32 -6.87298e-07/-1.73556e-37 |
| 64 | 8 | 0x00000000 (`0x00000000`) | 0xA3F4A764E4EACB1F · f32 -3.46494e+22/-2.65254e-17 |
| 72 | 8 | 0x00000000 (`0x00000000`) | 0x976FE5B308D162AC · f32 1.26019e-33/-7.7515e-25 |
| 80 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 92 | 4 | 0x00000000 (`0x00000000`) | 0x6D1130CE · f32 nan/inf |
| 96 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 108 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 120 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 136 | 8 | 0x00000000 (`0x00000000`) | 0xB27AF0D28AAEB98C · f32 -1.68254e-32/-1.46067e-08 |
| 144 | 360 | LevelGenerationPathSettings (`0x6D91F262`) |  |
| 504 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 520 | 4 | 0x00000000 (`0x00000000`) | 0x00000004 · f32 5.605194e-45 |
| 528 | 8 | 0x00000000 (`0x00000000`) | 0x3BD60BF1E55633C8 · f32 -6.32214e+22/0.00653219 |
| 536 | 8 | 0x00000000 (`0x00000000`) | 0x000000000000025A · f32 8.43582e-43/0 |
| 544 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 548 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 552 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 556 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 560 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000269 · f32 8.64601e-43/0 |
| 568 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |

### ExplosionInfo  (`generated_explosion_settings.dl_bin`, stride 152 B, rows 424)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | ExplosionType (`0x11BEEE03`) |  |
| 4 | 4 | DamageInfoType (`0x39D2F78D`) |  |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x000001A8 · f32 5.941505e-43 |
| 12 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00000113 · f32 3.853571e-43 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x0000012A · f32 4.175869e-43 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x40800000 · f32 4 |
| 40 | 16 | 0x00000000 (`0x00000000`) | 0000304100000000 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x000000000000FBD0 · f32 9.03333e-41/0 |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 68 | 1 | TerrainDeformationType (`0xC801688F`) |  |
| 72 | 4 | SurfaceImpactType (`0xCF328969`) |  |
| 76 | 4 | HitEffectDamageType (`0xB43002D3`) |  |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x80313676 · f32 -4.519476e-39 |
| 84 | 4 | ProjectileType (`0xA2B5F333`) |  |
| 88 | 1 | NoiseTemplate (`0x39117D3A`) |  |
| 92 | 4 | WindEffectTemplate (`0x8436CA1B`) |  |
| 96 | 4 | FireTemplate (`0x1ABF81A2`) |  |
| 100 | 4 | StatusEffectTemplateType (`0x375DAB6F`) |  |
| 104 | 4 | 0x00000000 (`0x00000000`) | 0x0000000E · f32 1.961818e-44 |
| 108 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 112 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 116 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 116 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 116 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 116 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 116 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 116 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 120 | 4 | ArcType (`0xA064A858`) |  |
| 124 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 124 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 128 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 132 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 132 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 136 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 140 | 1 | 0x00000000 (`0x00000000`) | 0x02 |
| 140 | 1 | 0x00000000 (`0x00000000`) | 0x02 |
| 144 | 4 | 0x22C3CE6D (`0x22C3CE6D`) |  |

### FontLookup  (`generated_font_lookup.dl_bin`, stride 24 B, rows 19)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x90B6AF29C294FE9A · f32 -74.4973/-7.20562e-29 |
| 8 | 16 | FontLookupEntry (`0x0AF4AC23`) |  |

### FontSettings  (`generated_font_settings.dl_bin`, stride 112 B, rows 50)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x90B6AF29C294FE9A · f32 -74.4973/-7.20562e-29 |
| 8 | 16 | 0x00000000 (`0x00000000`) | 7000000000000000 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0xF7B9C03FFF72FFD3 · f32 -3.23001e+38/-7.53495e+33 |
| 32 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 48 | 16 | 0x00000000 (`0x00000000`) | 8000000000000000 |
| 64 | 16 | UiFontSettingsEntry (`0xAB967758`) |  |
| 80 | 16 | UiHudFontStyleEntry (`0x7E330F19`) |  |
| 96 | 16 | UiMenuFontStyleEntry (`0xA50E2E2D`) |  |

### 0xF8F9EC3E  (`generated_galactic_presence_settings.dl_bin`, stride 1000 B, rows 137)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x00000000000003E8 · f32 1.4013e-42/0 |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x00000000000003E9 · f32 1.4027e-42/0 |
| 16 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 16 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 20 | 4 | 0x8BCB853B (`0x8BCB853B`) |  |
| 24 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 28 | 4 | RaceType (`0x41DCECBD`) |  |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x67D00A5C · f32 nan/inf |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x8D5D6884 · f32 -6.822669e-31 |
| 40 | 8 | 0x00000000 (`0x00000000`) | 0xC27B1ABB156120F9 · f32 4.54644e-26/-62.7761 |
| 48 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0xB2C92AE0 · f32 -2.341898e-08 |
| 68 | 4 | 0x1C8FF028 (`0x1C8FF028`) |  |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 76 | 1 | 0x00000000 (`0x00000000`) | 0x03 |
| 76 | 1 | 0x00000000 (`0x00000000`) | 0x03 |
| 76 | 1 | 0x00000000 (`0x00000000`) | 0x03 |
| 80 | 16 | VoTag (`0x0E5176C1`) |  |
| 96 | 16 | OperationTag (`0xA73A9FED`) |  |
| 112 | 4 | 0x735440CC (`0x735440CC`) |  |
| 120 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 128 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 136 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 144 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 152 | 4 | 0xCBDB4E2A (`0xCBDB4E2A`) |  |
| 156 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 168 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 172 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 176 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 184 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 184 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 188 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 192 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 200 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 204 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 208 | 16 | MaterialVariableSetting (`0x66AC0E33`) |  |
| 224 | 4 | 0x68F0ABB4 (`0x68F0ABB4`) |  |
| 228 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 232 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 240 | 16 | ResourceOverride (`0xB950E768`) |  |
| 256 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 260 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 264 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 268 | 4 | 0x4EA41426 (`0x4EA41426`) |  |
| 272 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 276 | 4 | PlanetSelectableType (`0x4E8E449A`) |  |
| 280 | 16 | DistantWarEffectPoolType (`0x744AABCA`) |  |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0x07 |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0x07 |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0x07 |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0x07 |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0x07 |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0x07 |
| 300 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 312 | 4 | 0x00000000 (`0x00000000`) | 0x40000000 · f32 2 |
| 316 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 320 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 324 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 328 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 332 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 344 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 348 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 360 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 372 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 384 | 16 | MaterialVariableSetting (`0x66AC0E33`) |  |
| 400 | 8 | 0x00000000 (`0x00000000`) | 0x9873EB0209157D28 · f32 1.79941e-33/-3.15257e-24 |
| 408 | 8 | 0x00000000 (`0x00000000`) | 0xCDC24954FD9D0DE2 · f32 -2.60951e+37/-4.07448e+08 |
| 416 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 424 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 432 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 440 | 16 | WeatherType (`0x40929612`) |  |
| 456 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 464 | 16 | 0x5C708081 (`0x5C708081`) |  |
| 480 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 496 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 504 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 520 | 8 | 0x00000000 (`0x00000000`) | 0x835F4AE8B0EE5FB7 · f32 -1.7344e-09/-6.56198e-37 |
| 528 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 544 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 548 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 552 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 564 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 576 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 580 | 4 | 0x00000000 (`0x00000000`) | 0xCFAD9CC5 · f32 -5.825465e+09 |
| 584 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 588 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 592 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 596 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 600 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 604 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 608 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 612 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 616 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 632 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 640 | 16 | SubRegionSettingsOverride (`0x5B4DABFF`) |  |
| 656 | 16 | 0x645E23F8 (`0x645E23F8`) |  |
| 672 | 16 | 0xB1185137 (`0xB1185137`) |  |
| 688 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 704 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 720 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 736 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 740 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 744 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 752 | 104 | 0x8BD8F3DE (`0x8BD8F3DE`) |  |
| 856 | 60 | 0x69413FE8 (`0x69413FE8`) |  |
| 920 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 928 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 936 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 944 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 952 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 960 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 968 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 976 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 984 | 16 | 0x9B4E7037 (`0x9B4E7037`) |  |

### LevelGenerationSettings  (`generated_generation_settings.dl_bin`, stride 464 B, rows 22)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x41800000 · f32 16 |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x42200000 · f32 40 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x3F1B0000 · f32 0.6054688 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x3F2A0000 · f32 0.6640625 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x3F19999A · f32 0.6 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x3F4CCCCD · f32 0.8 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x41200000 · f32 10 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x3F600000 · f32 0.875 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x3FC00000 · f32 1.5 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x3DCCCCCD · f32 0.1 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x3ED9999A · f32 0.425 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x41400000 · f32 12 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 60 | 4 | 0x00000000 (`0x00000000`) | 0x42000000 · f32 32 |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 68 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x432E0000 · f32 174 |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x40000000 · f32 2 |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0x3FE66666 · f32 1.8 |
| 88 | 8 | 0x00000000 (`0x00000000`) | 0xA4471002723A2DC7 · f32 3.68765e+30/-4.31648e-17 |
| 96 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 104 | 40 | ExplorationSettings (`0xDE9425C6`) |  |
| 144 | 16 | CacheLootTable (`0xCFE4197A`) |  |
| 160 | 96 | LocationFlagSettings (`0x0E20FFC4`) |  |
| 256 | 96 | RegionLightingSettings (`0x3F75D8EB`) |  |
| 352 | 16 | CityLayoutTemplate (`0xCAEA9E93`) |  |
| 368 | 16 | 0xB1814DA3 (`0xB1814DA3`) |  |
| 384 | 16 | PlanetAffiliationTemplate (`0x9A26D6E6`) |  |
| 400 | 16 | CityLayoutTemplate (`0xCAEA9E93`) |  |
| 416 | 16 | 0x29A36DB0 (`0x29A36DB0`) |  |
| 432 | 16 | 0x8D0A3882 (`0x8D0A3882`) |  |
| 448 | 16 | 0xED8AA652 (`0xED8AA652`) |  |

### HitEffectInfo  (`generated_hit_effect_settings.dl_bin`, stride 48 B, rows 1,512)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | HitEffectDamageType (`0xB43002D3`) |  |
| 4 | 4 | HitEffectReceiverType (`0x091B24E9`) |  |
| 8 | 4 | HitEffectLevel (`0x796C944A`) |  |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x0000000100000001 · f32 1.4013e-45/1.4013e-45 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x1AD8623F · f32 8.949423e-23 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0xEBD575F0 · f32 nan/inf |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |

### LanguageListEntry  (`generated_language_settings.dl_bin`, stride 208 B, rows 15)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x00000010 · f32 2.242078e-44 |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x000000000000000F · f32 2.10195e-44/0 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x00000000A6702562 · f32 -8.33174e-16/0 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x00000C40 · f32 4.394472e-42 |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000C43 · f32 4.39868e-42/0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x57627294 · f32 nan/inf |
| 44 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 46 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 48 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000C46 · f32 4.40288e-42/0 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x000100000008737E · f32 7.76115e-40/9.18355e-41 |
| 64 | 64 | LanguageLocaleInfo (`0x59CF9D40`) |  |
| 128 | 72 | LanguageListSettingsInfo (`0xCC6AA6FD`) |  |
| 200 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |

### PackageLayerTagIndirection  (`generated_layer_package_indirection_settings.dl_bin`, stride 16 B, rows 5)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | PackageLayerTagIndirectionPair (`0xA073D889`) |  |

### LevelGenerationLocation  (`generated_location_groups.dl_bin`, stride 56 B, rows 7,080)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0xAF13D778 · f32 -1.344612e-10 |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0xAF13D778 · f32 -1.344612e-10 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000004 · f32 5.605194e-45 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00000006 · f32 8.407791e-45 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x42B40000 · f32 90 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x43020000 · f32 130 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x000003E7 · f32 1.399897e-42 |
| 32 | 1 | LocationFlags (`0x673D8D46`) |  |
| 40 | 16 | LevelGenerationLocationGroup (`0xBBFEA78A`) |  |

### Modifier  (`generated_modifier_settings.dl_bin`, stride 24 B, rows 52)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x1DA06C9E · f32 4.246395e-21 |
| 4 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 8 | 16 | ModifierGroup (`0x05238A1C`) |  |

### 0x80EB67CF  (`generated_planet_color_set_settings.dl_bin`, stride 64 B, rows 30)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x00000010 · f32 2.242078e-44 |
| 4 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 16 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 28 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 40 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 52 | 12 | CApiVector3 (`0x85B82A43`) |  |

### LevelGenerationPlanetData  (`generated_planet_data.dl_bin`, stride 624 B, rows 438)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000270 · f32 8.7441e-43/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x55EB9C53 · f32 nan/inf |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x4FDB0093 · f32 7.348496e+09 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x76BAAB11 · f32 nan/inf |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0xF3B52DB1 · f32 nan/inf |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0xBB4C88EEB04EAB2A · f32 -7.51856e-10/-0.00312095 |
| 40 | 8 | 0x00000000 (`0x00000000`) | 0x5F403951506B65E2 · f32 1.57973e+10/1.38512e+19 |
| 48 | 8 | 0x00000000 (`0x00000000`) | 0x6C012D2AD0623533 · f32 -1.51805e+10/6.24659e+26 |
| 56 | 16 | OperationTag (`0xA73A9FED`) |  |
| 72 | 16 | ResourceOverride (`0xB950E768`) |  |
| 88 | 8 | 0x00000000 (`0x00000000`) | 0x00000000000002CB · f32 1.00193e-42/0 |
| 96 | 40 | LevelGenerationRegion (`0x312C4148`) |  |
| 136 | 40 | LevelGenerationRegion (`0x312C4148`) |  |
| 176 | 112 | LevelGenerationPaletteGroup (`0xC0C75C00`) |  |
| 288 | 112 | LevelGenerationPaletteGroup (`0xC0C75C00`) |  |
| 400 | 8 | 0x00000000 (`0x00000000`) | 0x586B86141D4CA270 · f32 2.70832e-21/1.03584e+15 |
| 408 | 8 | 0x00000000 (`0x00000000`) | 0x586B86141D4CA270 · f32 2.70832e-21/1.03584e+15 |
| 416 | 1 | 0x12FDF387 (`0x12FDF387`) |  |
| 424 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 440 | 4 | PlanetType (`0x29EED886`) |  |
| 444 | 4 | 0x00000000 (`0x00000000`) | 0x20512E9A · f32 1.771841e-19 |
| 448 | 16 | NatureLocationTag (`0x56635484`) |  |
| 464 | 4 | 0x00000000 (`0x00000000`) | 0x20512E9A · f32 1.771841e-19 |
| 472 | 8 | 0x00000000 (`0x00000000`) | 0x2039E03737EF59BF · f32 2.85328e-05/1.57443e-19 |
| 480 | 8 | 0x00000000 (`0x00000000`) | 0x931CD30118B09273 · f32 4.56428e-24/-1.9794e-27 |
| 488 | 8 | 0x00000000 (`0x00000000`) | 0xF2341A69E31478DC · f32 -2.73883e+21/-3.56731e+30 |
| 496 | 8 | 0x00000000 (`0x00000000`) | 0x8179C65722C3F0EE · f32 5.311e-18/-4.58764e-38 |
| 504 | 8 | 0x00000000 (`0x00000000`) | 0x257C4A1807D825FC · f32 3.25224e-34/2.18826e-16 |
| 512 | 16 | 0x00000000 (`0x00000000`) | 0003000000000000 |
| 528 | 16 | SampleType (`0xF104D1C4`) |  |
| 544 | 4 | 0x00000000 (`0x00000000`) | 0xB686AA5E · f32 -4.013345e-06 |
| 548 | 4 | 0x00000000 (`0x00000000`) | 0x398C7999 · f32 0.0002679348 |
| 552 | 8 | 0x00000000 (`0x00000000`) | 0x6C747ECFCB7DFDE2 · f32 -1.66456e+07/1.18231e+27 |
| 560 | 8 | 0x00000000 (`0x00000000`) | 0x4FC004E4038C7635 · f32 8.2556e-37/6.44309e+09 |
| 568 | 16 | 0x62FECBF9 (`0x62FECBF9`) |  |
| 584 | 8 | 0x00000000 (`0x00000000`) | 0xADAF78E20DEF0894 · f32 1.47316e-30/-1.99489e-11 |
| 592 | 8 | 0x00000000 (`0x00000000`) | 0x3F048D438C3AE5BC · f32 -1.43981e-31/0.51778 |
| 600 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 608 | 8 | 0x00000000 (`0x00000000`) | 0x19549DDDE39AE1E8 · f32 -5.71415e+21/1.0992e-23 |
| 616 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |

### PlanetOverrides  (`generated_planet_override_settings.dl_bin`, stride 40 B, rows 44)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000038 · f32 7.84727e-44/0 |
| 24 | 16 | ResourceOverride (`0xB950E768`) |  |

### PlanetRegionSettings  (`generated_planet_region_settings.dl_bin`, stride 128 B, rows 369)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000080 · f32 1.79366e-43/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x41835545 · f32 16.41664 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 24 | 4 | RaceType (`0x41DCECBD`) |  |
| 32 | 16 | OperationTag (`0xA73A9FED`) |  |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x00000063 · f32 1.387285e-43 |
| 56 | 4 | OperationType (`0x8E91A5D3`) |  |
| 64 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 80 | 4 | 0xA1CDD14D (`0xA1CDD14D`) |  |
| 88 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 104 | 16 | 0xB1185137 (`0xB1185137`) |  |
| 120 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |

### SavedPlanetTerritoryGraph  (`generated_planet_territory_graphs.dl_bin`, stride 56 B, rows 28,105)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x8B44C705 · f32 -3.789795e-32 |
| 8 | 16 | TerritoryCell (`0x402ADA74`) |  |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x00000200 · f32 7.174648e-43 |
| 32 | 16 | TerritoryEdge (`0x402BEE49`) |  |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x000005FA · f32 2.143987e-42 |

### SolarSystemObjectType  (`generated_planet_types_settings.dl_bin`, stride 24 B, rows 88)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 16 | SolarSystemObjectTypeSettings (`0x0FD71230`) |  |

### PolicySettings  (`generated_policy_settings.dl_bin`, stride 32 B, rows 14)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | PolicySetting (`0x001242EE`) |  |
| 16 | 16 | PolicyUnlockedWeaponList (`0x2702C92B`) |  |

### ProjectileInfo  (`generated_projectile_settings.dl_bin`, stride 272 B, rows 355)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | ProjectileType (`0xA2B5F333`) |  |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x00000163 · f32 4.97461e-43 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0xCAE08F7200000123 · f32 4.07778e-43/-7.35839e+06 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x45683D6B · f32 3715.839 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0xF1CD5269 · f32 nan/inf |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x7D4BC8F5 · f32 nan/inf |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x6A659858 · f32 nan/inf |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x41C80000 · f32 25 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x43960000 · f32 300 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x42C80000 · f32 100 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 60 | 4 | DamageInfoType (`0x39D2F78D`) |  |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 72 | 8 | 0x00000000 (`0x00000000`) | 0x000000F400000000 · f32 0/3.41917e-43 |
| 80 | 8 | 0x00000000 (`0x00000000`) | 0x9FC318BE3E800000 · f32 0.25/-8.26266e-20 |
| 88 | 4 | 0x00000000 (`0x00000000`) | 0xDD8A445D · f32 nan/inf |
| 96 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 104 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 112 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 120 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 128 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 136 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 140 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 144 | 4 | ExplosionType (`0x11BEEE03`) |  |
| 148 | 4 | 0x00000000 (`0x00000000`) | 0x71E52F80 · f32 nan/inf |
| 152 | 4 | 0x00000000 (`0x00000000`) | 0x42B40000 · f32 90 |
| 156 | 4 | ExplosionType (`0x11BEEE03`) |  |
| 160 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 164 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 168 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 172 | 4 | SurfaceImpactType (`0xCF328969`) |  |
| 176 | 4 | SurfaceImpactType (`0xCF328969`) |  |
| 180 | 4 | 0x00000000 (`0x00000000`) | 0xBF800000 · f32 -1 |
| 184 | 4 | 0x00000000 (`0x00000000`) | 0x3DCCCCCD · f32 0.1 |
| 188 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 192 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 196 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 200 | 4 | 0x00000000 (`0x00000000`) | 0x42B40000 · f32 90 |
| 204 | 4 | 0x00000000 (`0x00000000`) | 0x41200000 · f32 10 |
| 208 | 4 | 0x00000000 (`0x00000000`) | 0x3F400000 · f32 0.75 |
| 212 | 4 | 0x00000000 (`0x00000000`) | 0x40A00000 · f32 5 |
| 216 | 4 | 0x00000000 (`0x00000000`) | 0x41A00000 · f32 20 |
| 220 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 224 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 228 | 1 | 0x00000000 (`0x00000000`) | 0x0C |
| 232 | 4 | ProjectileStatusEffectVolumeTemplate (`0xDCC38AB6`) |  |
| 236 | 4 | HitEffectDamageType (`0xB43002D3`) |  |
| 240 | 4 | FireTemplate (`0x1ABF81A2`) |  |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 244 | 2 | 0x00000000 (`0x00000000`) | 0x0000 |
| 248 | 4 | RaycastTemplate (`0xD7658573`) |  |
| 252 | 4 | 0x00000000 (`0x00000000`) | 0x00000003 · f32 4.203895e-45 |
| 256 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 256 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 260 | 12 | CApiVector3 (`0x85B82A43`) |  |

### GenerationRegionSettings  (`generated_region_settings.dl_bin`, stride 3272 B, rows 74)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x9924738AF17B9252 · f32 -1.24572e+30/-8.50193e-24 |
| 8 | 4 | EnvironmentalEffectType (`0x66D2B571`) |  |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x40800000 · f32 4 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0xC3FA0000 · f32 -500 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x43800000 · f32 256 |
| 60 | 4 | 0x00000000 (`0x00000000`) | 0x43800000 · f32 256 |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0x40800000 · f32 4 |
| 68 | 4 | 0x00000000 (`0x00000000`) | 0xBF666666 · f32 -0.9 |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x7F7FFFFF · f32 nan/inf |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0x3E800000 · f32 0.25 |
| 88 | 1 | 0x00000000 (`0x00000000`) | 0x03 |
| 88 | 1 | 0x00000000 (`0x00000000`) | 0x03 |
| 92 | 36 | 0x00000000 (`0x00000000`) | 0000000000000000 |
| 128 | 224 | LevelGenerationSubRegionSpecialSettings (`0xAD5037C4`) |  |
| 352 | 216 | RouteSettingReference (`0xD856775C`) |  |
| 568 | 1088 | SubRegionSettings (`0xB6A8757F`) |  |
| 1656 | 1 | CityLayout (`0x33FEE6B7`) |  |
| 1660 | 4 | 0x00000000 (`0x00000000`) | 0x42B40000 · f32 90 |
| 1664 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 1668 | 524 | 0x4D699EB3 (`0x4D699EB3`) |  |
| 2192 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 2196 | 512 | 0xC4158B6A (`0xC4158B6A`) |  |
| 2708 | 1 | LevelGenerationMode (`0x07527AC9`) |  |
| 2709 | 4 | RegionFlag (`0x2223CDFE`) |  |
| 2716 | 24 | 0x00000000 (`0x00000000`) | 0000803f0000803f |
| 2740 | 512 | SubRegionSettingsOverride (`0x5B4DABFF`) |  |
| 3252 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 3256 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 3257 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 3258 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 3260 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 3264 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 3268 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |

### GenerationRegionGroup  (`generated_region_settings.dl_bin`, stride 64 B, rows 236)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000040 · f32 8.96831e-44/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0xF6FC0114 · f32 nan/inf |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x604040566DB86F01 · f32 7.13493e+27/5.54127e+19 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0E0DC8E24EE42BBA · f32 1.91404e+09/1.74763e-30 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0xB38DC928 · f32 -6.602414e-08 |
| 36 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 48 | 16 | GenerationRegionVariantList (`0x961C02A1`) |  |

### RouteSettings  (`generated_route_settings.dl_bin`, stride 112 B, rows 3)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x80578452 · f32 -8.037156e-39 |
| 8 | 104 | StampGroup (`0xA38290F2`) |  |

### LevelGenerationSatelliteGroup  (`generated_satellite_groups.dl_bin`, stride 24 B, rows 3,429)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0xAEA08931 · f32 -7.300328e-11 |
| 8 | 16 | LevelGenerationSatellite (`0x839EB6AB`) |  |

### ScenarioSettings  (`generated_scenario_settings.dl_bin`, stride 48 B, rows 149)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0xFDC135EF0241CE85 · f32 1.42387e-37/-3.21026e+37 |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x078971E70D425BED · f32 5.98915e-31/2.06804e-34 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x00000000FFFFFFFF · f32 nan/0 |
| 32 | 16 | ScenarioSetting (`0x41CF0ED2`) |  |

### SkySettings  (`generated_sky_settings.dl_bin`, stride 24 B, rows 480)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0xEFC60192FEDFD7CE · f32 -1.48769e+38/-1.2256e+29 |
| 8 | 16 | SkySetting (`0xC96AEF75`) |  |

### SolarSystemSettings  (`generated_solar_system_settings.dl_bin`, stride 24 B, rows 3,822)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x257C4A1807D825FC · f32 3.25224e-34/2.18826e-16 |
| 8 | 16 | SolarSystemSetting (`0xB5F966E4`) |  |

### StampHashEntry  (`generated_stamp_settings.dl_bin`, stride 112 B, rows 4,096)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 104 | Stamp (`0x0E1E2405`) |  |

### StatusEffectInfo  (`generated_status_effect_settings.dl_bin`, stride 160 B, rows 73)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | StatusEffectType (`0x525E8B93`) |  |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000049 · f32 1.02295e-43/0 |
| 16 | 4 | StatusEffectShaderVariablePreset (`0x89FA9121`) |  |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000002DB0 · f32 1.63896e-41/0 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 44 | 4 | DamageInfoType (`0x39D2F78D`) |  |
| 48 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x0000000041000000 · f32 8/0 |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 68 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 88 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 92 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 96 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 100 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 104 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 104 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 104 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 104 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 112 | 16 | 0x17B9083A (`0x17B9083A`) |  |
| 128 | 4 | 0x00000000 (`0x00000000`) | 0xFFFFFFFF · f32 nan/inf |
| 132 | 4 | 0x00000000 (`0x00000000`) | 0xFFFFFFFF · f32 nan/inf |
| 136 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 140 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 144 | 16 | 0x9DDD1BE2 (`0x9DDD1BE2`) |  |

### StatusEffectTemplate  (`generated_status_effect_settings.dl_bin`, stride 40 B, rows 29)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | StatusEffectTemplateType (`0x375DAB6F`) |  |
| 4 | 32 | StatusEffectContinuousEffect (`0x48CEF575`) |  |
| 36 | 1 | 0x00000000 (`0x00000000`) | 0x00 |

### StratagemInfo  (`generated_stratagem_settings.dl_bin`, stride 400 B, rows 153)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | StratagemType (`0x7BDC408A`) |  |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x0000000D · f32 1.821688e-44 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x71B6D7DA00000068 · f32 1.45735e-43/1.81079e+30 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x000000009CD89259 · f32 -1.43315e-21/0 |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000001460 · f32 7.30917e-42/0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x0000147A · f32 7.345607e-42 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x0000149B · f32 7.391849e-42 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x8FA7FCF1 · f32 -1.65649e-29 |
| 60 | 4 | StratagemCategoryType (`0xCBDB3EC8`) |  |
| 64 | 16 | StratagemButtonDirection (`0x561A8A65`) |  |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x000014BC · f32 7.438092e-42 |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 88 | 4 | 0x00000000 (`0x00000000`) | 0x00000006 · f32 8.407791e-45 |
| 92 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 96 | 4 | 0x00000000 (`0x00000000`) | 0xFFFFFFFF · f32 nan/inf |
| 100 | 4 | 0x00000000 (`0x00000000`) | 0x40A00000 · f32 5 |
| 104 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 108 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 112 | 4 | StratagemOriginType (`0xE43FFD52`) |  |
| 116 | 4 | StratagemCallInType (`0xF28148FD`) |  |
| 120 | 2 | StratagemCallInLogic (`0x4216A409`) |  |
| 124 | 4 | StratagemObjectiveDropRequirement (`0x4D883209`) |  |
| 128 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 128 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 136 | 8 | 0x00000000 (`0x00000000`) | 0x00000000000000C0 · f32 2.69049e-43/0 |
| 144 | 1 | 0x00000000 (`0x00000000`) | 0x03 |
| 148 | 4 | StratagemCooldownType (`0x783CA8AF`) |  |
| 152 | 16 | 0x00000000 (`0x00000000`) | 0000000000000000 |
| 168 | 8 | 0x00000000 (`0x00000000`) | 0x00000000000014D8 · f32 7.47733e-42/0 |
| 176 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000002 · f32 2.8026e-45/0 |
| 184 | 4 | StratagemHUDType (`0x7A6E836B`) |  |
| 188 | 4 | 0x00000000 (`0x00000000`) | 0x519980A7 · f32 8.241105e+10 |
| 192 | 1 | 0x00000000 (`0x00000000`) | 0xFD |
| 196 | 4 | StratagemType (`0x7BDC408A`) |  |
| 200 | 4 | StratagemType (`0x7BDC408A`) |  |
| 204 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 208 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 212 | 4 | StratagemBeaconColor (`0xE9BD1A8F`) |  |
| 216 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 220 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 224 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 228 | 4 | 0x00000000 (`0x00000000`) | 0x00000002 · f32 2.802597e-45 |
| 232 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 240 | 8 | 0x00000000 (`0x00000000`) | 0x0000000026A8BCEB · f32 1.17085e-15/0 |
| 248 | 4 | 0x00000000 (`0x00000000`) | 0xC12168C5 · f32 -10.08808 |
| 252 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 256 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 260 | 4 | StratagemInfoFlag (`0x8A0F47AE`) |  |
| 264 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 268 | 4 | StratagemType (`0x7BDC408A`) |  |
| 272 | 1 | StratagemCustomizationTypeInfo (`0xC53E09EF`) |  |
| 280 | 16 | 0xB6CAFF2E (`0xB6CAFF2E`) |  |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0xFF |
| 296 | 1 | 0x00000000 (`0x00000000`) | 0xFF |
| 300 | 4 | 0x00000000 (`0x00000000`) | 0xFFFFFFFF · f32 nan/inf |
| 304 | 16 | CApiVector3 (`0x85B82A43`) |  |
| 320 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 336 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 352 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 368 | 1 | 0x00000000 (`0x00000000`) | 0xFF |
| 368 | 1 | 0x00000000 (`0x00000000`) | 0xFF |
| 372 | 4 | UnitCustomizationCollectionType (`0x57D3AD67`) |  |
| 376 | 16 | 0xB24E0C4B (`0xB24E0C4B`) |  |
| 392 | 4 | 0x6011FA2B (`0x6011FA2B`) |  |

### StratagemCustomizationInfo  (`generated_stratagem_upgrade_settings.dl_bin`, stride 64 B, rows 1)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00000050 · f32 1.121039e-43 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x00000000188C40A6 · f32 3.62544e-24/0 |
| 32 | 4 | StratagemCustomizationType (`0x6F107CC3`) |  |
| 36 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x00000005 · f32 7.006492e-45 |
| 56 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |

### SurfaceEffectInfo  (`generated_surface_effect_settings.dl_bin`, stride 40 B, rows 7,644)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | SurfaceMaterialType (`0x725893BA`) |  |
| 4 | 4 | SurfaceImpactType (`0xCF328969`) |  |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000001DDC · f32 1.07115e-41/0 |
| 16 | 8 | 0x00000000 (`0x00000000`) | 0x0000000100000001 · f32 1.4013e-45/1.4013e-45 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 32 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 32 | 1 | 0x00000000 (`0x00000000`) | 0x00 |

### UnitCustomizationSettings  (`generated_unit_customization_settings.dl_bin`, stride 80 B, rows 339)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x4235A2FB · f32 45.40916 |
| 4 | 4 | UnitCustomizationCollectionType (`0x57D3AD67`) |  |
| 8 | 4 | UnitCustomizationCollectionType (`0x57D3AD67`) |  |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0xBEC9DDD0 · f32 -0.3942704 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0xD0C2442E · f32 -2.607399e+10 |
| 24 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000050 · f32 1.12104e-43/0 |
| 32 | 4 | UnitCustomizationCollectionCategoryType (`0xBDEC38A5`) |  |
| 40 | 16 | UnitCustomizationSetting (`0x1C341B57`) |  |
| 56 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 68 | 12 | CApiVector3 (`0x85B82A43`) |  |

### UnitEffectSetting  (`generated_unit_effect_settings.dl_bin`, stride 112 B, rows 408)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 4 | UnitEffectOrphanStrategy (`0x322F2168`) |  |
| 16 | 16 | EffectSetting (`0x10CEE58B`) |  |
| 32 | 16 | UnitSound (`0xCB0D97E9`) |  |
| 48 | 16 | UnitNodeScale (`0x49D0074E`) |  |
| 64 | 16 | UnitSound (`0xCB0D97E9`) |  |
| 80 | 16 | UnitSound (`0xCB0D97E9`) |  |
| 96 | 16 | WeightedEffectSetting (`0x2F881EFC`) |  |

### VideoFlowSettings  (`generated_video_flow_settings.dl_bin`, stride 32 B, rows 63)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | VideoSegment (`0x5F6F112A`) |  |
| 16 | 16 | VideoSegment (`0x5F6F112A`) |  |

### VideoUIElement  (`generated_video_ui_settings.dl_bin`, stride 120 B, rows 9)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x00000010 · f32 2.242078e-44 |
| 4 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 8 | 4 | FontType (`0x7F2E7339`) |  |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 28 | 4 | 0x00000000 (`0x00000000`) | 0x00000028 · f32 5.605194e-44 |
| 32 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 40 | 8 | 0x00000000 (`0x00000000`) | 0x3F8000003F800000 · f32 1/1 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 60 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 64 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 68 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0x44408000 · f32 770 |
| 88 | 4 | 0x00000000 (`0x00000000`) | 0x00000001 · f32 1.401298e-45 |
| 92 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 96 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 100 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 104 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 108 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 112 | 4 | 0x00000000 (`0x00000000`) | 0x40828F5C · f32 4.08 |
| 116 | 4 | 0x00000000 (`0x00000000`) | 0x40D9999A · f32 6.8 |

### WeaponCustomizableItem  (`generated_weapon_customization_settings.dl_bin`, stride 88 B, rows 252)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000010 · f32 2.24208e-44/0 |
| 8 | 4 | 0x00000000 (`0x00000000`) | 0x00000061 · f32 1.35926e-43 |
| 12 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 16 | 4 | 0x00000000 (`0x00000000`) | 0x00002168 · f32 1.19839e-41 |
| 20 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 24 | 4 | 0x00000000 (`0x00000000`) | 0x5CD7F1BF · f32 nan/inf |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0xCBF63D7F9321CA5B · f32 -2.04208e-27/-3.22752e+07 |
| 40 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 48 | 16 | WeaponCustomizationSlot (`0x62AB45E5`) |  |
| 64 | 16 | CApiVector3 (`0x85B82A43`) |  |
| 80 | 4 | WeaponCustomizationSortGroups (`0x9D292BCB`) |  |

### WeatherColorSet  (`generated_weather_color_set_settings.dl_bin`, stride 196 B, rows 132)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | 0x00000010 · f32 2.242078e-44 |
| 4 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 16 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 28 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 40 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 52 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 64 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 76 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 88 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 100 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 112 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 124 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 136 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 148 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 160 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 172 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 184 | 12 | CApiVector3 (`0x85B82A43`) |  |

### WeatherSettings  (`generated_weather_settings.dl_bin`, stride 648 B, rows 190)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | 0x05C6E34985B0B584 · f32 -1.66176e-35/1.87033e-35 |
| 8 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000288 · f32 9.08041e-43/0 |
| 16 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 20 | 4 | WeatherType (`0x40929612`) |  |
| 24 | 4 | EnvironmentalEffectType (`0x66D2B571`) |  |
| 28 | 1 | 0x00000000 (`0x00000000`) | 0x08 |
| 29 | 1 | 0x00000000 (`0x00000000`) | 0x0C |
| 32 | 8 | 0x00000000 (`0x00000000`) | 0xCB16EB1141DFFE22 · f32 27.9991/-9.89058e+06 |
| 40 | 4 | 0x00000000 (`0x00000000`) | 0x3F333333 · f32 0.7 |
| 44 | 4 | 0x00000000 (`0x00000000`) | 0x3F333333 · f32 0.7 |
| 48 | 4 | 0x00000000 (`0x00000000`) | 0x41A00000 · f32 20 |
| 52 | 4 | 0x00000000 (`0x00000000`) | 0x43C80000 · f32 400 |
| 56 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 60 | 4 | 0x00000000 (`0x00000000`) | 0x40800000 · f32 4 |
| 64 | 8 | CApiVector2 (`0x85B82A42`) |  |
| 72 | 4 | 0x00000000 (`0x00000000`) | 0x3FC00000 · f32 1.5 |
| 76 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 80 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 84 | 4 | 0x00000000 (`0x00000000`) | 0xBF800000 · f32 -1 |
| 88 | 4 | 0x00000000 (`0x00000000`) | 0xBF800000 · f32 -1 |
| 96 | 8 | 0x00000000 (`0x00000000`) | 0xE018F11F8593CC28 · f32 -1.38988e-35/-4.40825e+19 |
| 104 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 112 | 8 | 0x00000000 (`0x00000000`) | 0x9E197ACE3C44307C · f32 0.0119745/-8.12515e-21 |
| 120 | 4 | 0x00000000 (`0x00000000`) | 0x428C0000 · f32 70 |
| 124 | 8 | CApiVector2 (`0x85B82A42`) |  |
| 132 | 4 | 0x00000000 (`0x00000000`) | 0x3DCCCCCD · f32 0.1 |
| 136 | 4 | 0x00000000 (`0x00000000`) | 0x43960000 · f32 300 |
| 140 | 4 | 0x00000000 (`0x00000000`) | 0x3DCCCCCD · f32 0.1 |
| 144 | 4 | 0x00000000 (`0x00000000`) | 0x3E4CCCCD · f32 0.2 |
| 148 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 152 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 156 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 160 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 164 | 4 | 0x00000000 (`0x00000000`) | 0x3E19999A · f32 0.15 |
| 168 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 172 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 176 | 4 | 0x00000000 (`0x00000000`) | 0x3CCCCCCD · f32 0.025 |
| 180 | 4 | 0x00000000 (`0x00000000`) | 0x3C75C28F · f32 0.015 |
| 184 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 188 | 4 | 0x00000000 (`0x00000000`) | 0x11278A45 · f32 1.321658e-28 |
| 192 | 4 | 0x00000000 (`0x00000000`) | 0x3DCCCCCD · f32 0.1 |
| 196 | 4 | 0x00000000 (`0x00000000`) | 0x42200000 · f32 40 |
| 200 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 204 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 208 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 212 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 216 | 4 | 0x00000000 (`0x00000000`) | 0x41800000 · f32 16 |
| 220 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 224 | 4 | 0x00000000 (`0x00000000`) | 0x40800000 · f32 4 |
| 228 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 232 | 4 | 0x00000000 (`0x00000000`) | 0x3D99999A · f32 0.075 |
| 236 | 4 | 0x00000000 (`0x00000000`) | 0x3F4CCCCD · f32 0.8 |
| 240 | 2 | 0x00000000 (`0x00000000`) | 0x0400 |
| 244 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 248 | 4 | 0x00000000 (`0x00000000`) | 0x3A83126F · f32 0.001 |
| 252 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 256 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 260 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 264 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 268 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 272 | 4 | 0x00000000 (`0x00000000`) | 0x44FA0000 · f32 2000 |
| 276 | 4 | 0x00000000 (`0x00000000`) | 0x447A0000 · f32 1000 |
| 280 | 4 | 0x00000000 (`0x00000000`) | 0x457A0000 · f32 4000 |
| 284 | 4 | 0x00000000 (`0x00000000`) | 0xC3480000 · f32 -200 |
| 288 | 4 | 0x00000000 (`0x00000000`) | 0xC3480000 · f32 -200 |
| 292 | 4 | 0x00000000 (`0x00000000`) | 0xC3480000 · f32 -200 |
| 296 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 300 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 304 | 4 | 0x00000000 (`0x00000000`) | 0x3F400000 · f32 0.75 |
| 308 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 312 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 316 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 320 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 328 | 16 | CameraEffect (`0x66925F96`) |  |
| 344 | 16 | DistantWeatherEffects (`0xC7F5CA07`) |  |
| 360 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 364 | 8 | CApiVector2 (`0x85B82A42`) |  |
| 372 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 384 | 4 | 0x00000000 (`0x00000000`) | 0x41233333 · f32 10.2 |
| 388 | 8 | CApiVector2 (`0x85B82A42`) |  |
| 396 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 400 | 1 | BanterEventType (`0x8BE10600`) |  |
| 404 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 408 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 416 | 16 | 0x34F2F276 (`0x34F2F276`) |  |
| 432 | 4 | 0x00000000 (`0x00000000`) | 0xBF800000 · f32 -1 |
| 436 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 440 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 444 | 196 | WeatherColorSet (`0x970B0B5B`) |  |
| 640 | 4 | StatusEffectTemplateType (`0x375DAB6F`) |  |
| 644 | 4 | DangerWarningType (`0x0E8E1A49`) |  |

### ZoneSettings  (`generated_zone_data.dl_bin`, stride 912 B, rows 517)

| offset | size | type | row 0, both readings |
|---:|---:|---|---|
| 0 | 16 | ZoneTag (`0x1EA4DDF8`) |  |
| 16 | 16 | StampGroup (`0xA38290F2`) |  |
| 32 | 16 | ShaderProperties (`0x64744AC4`) |  |
| 48 | 16 | ShaderProperties (`0x64744AC4`) |  |
| 64 | 16 | FogVolumeShaderProperties (`0xACB8CCF8`) |  |
| 80 | 16 | ShaderProperties (`0x64744AC4`) |  |
| 96 | 16 | ShaderProperties (`0x64744AC4`) |  |
| 112 | 16 | ShaderProperties (`0x64744AC4`) |  |
| 128 | 16 | ShaderProperties (`0x64744AC4`) |  |
| 144 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 148 | 12 | CApiVector3 (`0x85B82A43`) |  |
| 160 | 1 | MinimapTerrainType (`0xBCAAB042`) |  |
| 168 | 8 | 0x00000000 (`0x00000000`) | 0xFFFFFFFFFFFFFFFF · f32 nan/nan |
| 176 | 16 | 0x0089AB61 (`0x0089AB61`) |  |
| 192 | 16 | CameraEffect (`0x66925F96`) |  |
| 208 | 8 | WindNoiseSettings (`0x9F4AC541`) |  |
| 216 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 224 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 228 | 4 | 0x00000000 (`0x00000000`) | 0xC3FA8000 · f32 -501 |
| 232 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 236 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 240 | 16 | 0x00000000 (`0x00000000`) | ffffffffffffffff |
| 256 | 8 | 0x00000000 (`0x00000000`) | 0xFFFFFFFFFFFFFFFF · f32 nan/nan |
| 264 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 272 | 24 | QuakeEffectSettings (`0x4105D355`) |  |
| 296 | 1 | ZoneMusicType (`0x07F6109F`) |  |
| 297 | 1 | BanterEventType (`0x8BE10600`) |  |
| 300 | 4 | 0x00000000 (`0x00000000`) | 0xC2C80000 · f32 -100 |
| 304 | 40 | MinimapScatterSet (`0xA2B24BAD`) |  |
| 344 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 348 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 352 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 356 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 360 | 1 | 0x00000000 (`0x00000000`) | 0x20 |
| 360 | 1 | 0x00000000 (`0x00000000`) | 0x20 |
| 360 | 1 | 0x00000000 (`0x00000000`) | 0x20 |
| 360 | 1 | 0x00000000 (`0x00000000`) | 0x20 |
| 360 | 1 | 0x00000000 (`0x00000000`) | 0x20 |
| 360 | 1 | 0x00000000 (`0x00000000`) | 0x20 |
| 364 | 4 | PatrolSetting (`0x18856870`) |  |
| 368 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 372 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 376 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 380 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 384 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 388 | 4 | 0x00000000 (`0x00000000`) | 0x42200000 · f32 40 |
| 392 | 4 | 0x00000000 (`0x00000000`) | 0x40000000 · f32 2 |
| 396 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 400 | 4 | 0x00000000 (`0x00000000`) | 0x40000000 · f32 2 |
| 404 | 4 | 0x00000000 (`0x00000000`) | 0x40000000 · f32 2 |
| 408 | 4 | 0x00000000 (`0x00000000`) | 0x41F00000 · f32 30 |
| 412 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 413 | 1 | 0x00000000 (`0x00000000`) | 0x01 |
| 416 | 4 | CityPlacementHeuristic (`0xA0714582`) |  |
| 420 | 4 | 0xBAC19D46 (`0xBAC19D46`) |  |
| 424 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 428 | 4 | 0x00000000 (`0x00000000`) | 0x00000402 · f32 1.437732e-42 |
| 432 | 24 | CApiVector2 (`0x85B82A42`) |  |
| 456 | 24 | CApiVector2 (`0x85B82A42`) |  |
| 480 | 24 | CApiVector2 (`0x85B82A42`) |  |
| 504 | 4 | 0x00000000 (`0x00000000`) | 0x7F7FFFFF · f32 nan/inf |
| 508 | 4 | 0x00000000 (`0x00000000`) | 0x7F7FFFFF · f32 nan/inf |
| 512 | 4 | 0x00000000 (`0x00000000`) | 0x7F7FFFFF · f32 nan/inf |
| 516 | 4 | 0x00000000 (`0x00000000`) | 0x7F7FFFFF · f32 nan/inf |
| 520 | 4 | LocationFlag (`0x12A4B1D3`) |  |
| 528 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 536 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 544 | 4 | 0x00000000 (`0x00000000`) | 0x40000000 · f32 2 |
| 548 | 4 | 0x00000000 (`0x00000000`) | 0x3DCCCCCD · f32 0.1 |
| 552 | 4 | 0x00000000 (`0x00000000`) | 0x00000002 · f32 2.802597e-45 |
| 560 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 568 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 576 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 584 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 592 | 4 | 0x00000000 (`0x00000000`) | 0x43160000 · f32 150 |
| 596 | 4 | 0x00000000 (`0x00000000`) | 0x3EE66666 · f32 0.45 |
| 600 | 4 | 0x00000000 (`0x00000000`) | 0x41F00000 · f32 30 |
| 604 | 4 | 0x00000000 (`0x00000000`) | 0x3F000000 · f32 0.5 |
| 608 | 4 | 0x00000000 (`0x00000000`) | 0x3FC00000 · f32 1.5 |
| 616 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 624 | 4 | 0x00000000 (`0x00000000`) | 0x41A00000 · f32 20 |
| 628 | 4 | 0x00000000 (`0x00000000`) | 0x40A00000 · f32 5 |
| 632 | 4 | 0x00000000 (`0x00000000`) | 0x43160000 · f32 150 |
| 640 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 648 | 4 | 0x00000000 (`0x00000000`) | 0x40400000 · f32 3 |
| 652 | 4 | 0x00000000 (`0x00000000`) | 0x3E99999A · f32 0.3 |
| 656 | 4 | 0x00000000 (`0x00000000`) | 0x3E000000 · f32 0.125 |
| 660 | 4 | 0x00000000 (`0x00000000`) | 0x41F00000 · f32 30 |
| 664 | 4 | 0x00000000 (`0x00000000`) | 0x40400000 · f32 3 |
| 668 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 672 | 8 | 0x00000000 (`0x00000000`) | 0x0000000000000000 · f32 0/0 |
| 680 | 8 | 0x00000000 (`0x00000000`) | 0xFFFFFFFFFFFFFFFF · f32 nan/nan |
| 688 | 4 | 0x00000000 (`0x00000000`) | 0x3F800000 · f32 1 |
| 692 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 696 | 184 | BoundaryWallSettings (`0x7C9034C5`) |  |
| 880 | 16 | 0x46B8CBC2 (`0x46B8CBC2`) |  |
| 896 | 4 | LevelGenerationTag (`0x8419CD40`) |  |
| 900 | 4 | 0x00000000 (`0x00000000`) | 0x00000000 · f32 0 |
| 904 | 1 | 0x00000000 (`0x00000000`) | 0x00 |
| 904 | 1 | 0x00000000 (`0x00000000`) | 0x00 |

