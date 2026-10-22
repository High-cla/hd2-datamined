# 全表字典 · build 25988413（只读）

> 这份文档回答一件事：**这个 build 的数据表都有什么、每张表长什么样、字段在哪个偏移。**
> 不涉及改游戏，也不含任何密钥材料——重新生成需要你自己的 `recipient.sk`（见 §用法）。

## 0. 一句话状态

55 张 `generated_*.dl_bin` + 1 个类型库，**全部能解封并解析**；类型库给出 **1,208 个类型 / 7,349
个成员偏移**，配合公开的名字表能还原 **6,696 个类型名**：

| 几何状态 | 表数 | 含义 |
|---|---:|---|
| **完全闭合**（`array`） | 18 | `16 + 行数×步长 == payload`，行数从组头直接读出 |
| 闭合 + 尾块（`array+tail`） | 2 | 行之外还有一段未判型的数据（explosion 的 3,664 B） |
| **hashmap+行** | 5 | 组头里的 count 是**哈希槽数**，行数据跟在槽数组后面 |
| 其它（`raw` / 混合 / 特殊） | 30 | 没有 `0x10` 描述符，或像 entities 那样是 275 个组件块 |

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

## 2. 三层能力（这份字典覆盖第 1 层）

| 层 | 状态 |
|---|---|
| **结构层**：组、行步长、字段偏移、嵌套类型 | ✓ **55/55 张全部可得**（本文档） |
| **语义层**：哪个偏移是伤害 / 半径 / 掉率 | ◐ 只有 5 张表标过（entities 部件、damage、projectile、explosion、weapon_customization） |
| **可改层**：哈希校正空位 + 实机验证 | ◐ 同样 5 张；其余未验证 |

## 3. 已知限制（别把本字典当全知）

1. **`hashmap+rows` 的 count 不是行数**——它是哈希槽数（stamp 4,096、stratagem 153、
   weapon_customization 252、planet_override 44）。真实行数要解析槽数组后才知道。
2. **`raw` 表没有 `0x10` 描述符**，行数是 `payload // 步长` 推的，可能有 ±1 的零头。
3. **entities 不是行表**：275 个组件块，每块是「哈希图 + 行数组」，本字典只给出块与类型。
4. **类型名来自公开哈希表，不是游戏自带**：`dl_library.dl_typelib` 是**去字符串**的（1208 个
   类型、0 个字符串），所以成员**没有名字**，只有偏移、尺寸、类型——语义要靠猜和实测。
5. 未被任何 projectile / fire 表引用的射弹、爆炸行（见各自的文档）仍然存在，本字典只给结构。

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
| `generated_destruction_settings.dl_bin` | 1,643,910 | 1647 | 16,156 | array+raw+raw-array | DestructionSettings×168B, DestructionTemplates×16B, DestructionHashMap×16B |
| `generated_planet_territory_graphs.dl_bin` | 1,574,628 | 11 | 28,105 | raw+raw-array | SavedPlanetTerritoryGraph×56B |
| `generated_stamp_settings.dl_bin` | 678,124 | 1 | 4,096 | hashmap+rows | StampHashEntry×112B |
| `generated_zone_data.dl_bin` | 518,478 | 88 | 517 | raw+raw-array | ZoneSettings×912B |
| `generated_customization_armor_sets.dl_bin` | 453,204 | 422 | 6,821 | raw | HelldiverCustomizationKit×64B |
| `generated_location_groups.dl_bin` | 397,106 | 13 | 7,080 | raw+raw-array | LevelGenerationLocation×56B |
| `generated_planet_data.dl_bin` | 369,540 | 438 | 438 | raw | LevelGenerationPlanetData×624B |
| `generated_credits_settings.dl_bin` | 368,228 | 1 | 4,515 | array+tail | CreditsRowData×64B |
| `generated_entity_deltas.dl_bin` | 352,345 | 1 | 4,403 | raw | ComponentEntityDeltaStorage×80B |
| `generated_surface_effect_settings.dl_bin` | 305,804 | 1 | 7,644 | array | SurfaceEffectInfo×40B |
| `generated_region_settings.dl_bin` | 259,627 | 87 | 310 | raw+raw-array | GenerationRegionSettings×3272B, GenerationRegionGroup×64B |
| `generated_animation_event_trigger_settings.dl_bin` | 165,068 | 1 | 213 | array+tail | AnimationEventTriggerSetting×24B |
| `generated_weather_settings.dl_bin` | 162,908 | 184 | 190 | raw | WeatherSettings×648B |
| `generated_galactic_presence_settings.dl_bin` | 155,853 | 137 | 137 | raw | 0xF8F9EC3E×1000B |
| `generated_projectile_settings.dl_bin` | 96,604 | 1 | 355 | array | ProjectileInfo×272B |
| `generated_solar_system_settings.dl_bin` | 91,764 | 1 | 3,822 | raw | SolarSystemSettings×24B |
| `generated_satellite_groups.dl_bin` | 83,413 | 36 | 3,429 | raw+raw-array | LevelGenerationSatelliteGroup×24B |
| `generated_stratagem_settings.dl_bin` | 82,384 | 12 | 153 | array+tail+hashmap+rows | StratagemInfo×400B |
| `generated_hit_effect_settings.dl_bin` | 72,620 | 1 | 1,512 | array | HitEffectInfo×48B |
| `generated_explosion_settings.dl_bin` | 68,156 | 1 | 424 | array+tail | ExplosionInfo×152B |
| `generated_unit_effect_settings.dl_bin` | 63,004 | 1 | 408 | array+tail | UnitEffectSetting×112B |
| `generated_planet_region_settings.dl_bin` | 61,485 | 369 | 369 | raw | PlanetRegionSettings×128B |
| `generated_damage_settings.dl_bin` | 50,336 | 2 | 662 | array+raw-array | DamageArmorAngles×32B, DamageInfo×76B |
| `generated_planet_override_settings.dl_bin` | 35,474 | 13 | 44 | array+tail+hashmap+rows+unknown | PlanetOverrides×40B |
| `generated_weapon_customization_settings.dl_bin` | 30,824 | 9 | 252 | array+tail+hashmap+rows | WeaponCustomizableItem×88B |
| `generated_unit_customization_settings.dl_bin` | 27,744 | 12 | 339 | raw | UnitCustomizationSettings×80B |
| `generated_weather_color_set_settings.dl_bin` | 25,916 | 1 | 132 | array | WeatherColorSet×196B |
| `generated_planet_types_settings.dl_bin` | 16,844 | 1 | 88 | array+tail | SolarSystemObjectType×24B |
| `generated_collision_event_settings.dl_bin` | 14,444 | 1 | 180 | array | CollisionEventSetting×80B |
| `generated_status_effect_settings.dl_bin` | 14,020 | 2 | 102 | array+array+tail | StatusEffectInfo×160B, StatusEffectTemplate×40B |
| `generated_sky_settings.dl_bin` | 12,484 | 40 | 480 | raw-array | SkySettings×24B |
| `generated_environment_settings.dl_bin` | 10,962 | 17 | 17 | raw | EnvironmentSettings×576B |
| `generated_generation_settings.dl_bin` | 10,396 | 1 | 22 | raw | LevelGenerationSettings×464B |
| `generated_scenario_settings.dl_bin` | 8,092 | 39 | 149 | raw-array | ScenarioSettings×48B |
| `generated_font_settings.dl_bin` | 5,980 | 6 | 50 | raw | FontSettings×112B |
| `generated_customization_passive_bonuses.dl_bin` | 4,016 | 33 | 40 | raw+raw-array | HelldiverCustomizationPassiveBonusSettings×56B |
| `generated_language_settings.dl_bin` | 3,948 | 1 | 15 | array+tail | LanguageListEntry×208B |
| `generated_beam_settings.dl_bin` | 3,404 | 1 | 30 | array | BeamInfo×112B |
| `generated_video_flow_settings.dl_bin` | 2,060 | 1 | 63 | raw | VideoFlowSettings×32B |
| `generated_planet_color_set_settings.dl_bin` | 1,964 | 1 | 30 | array | 0x80EB67CF×64B |
| `generated_modifier_settings.dl_bin` | 1,764 | 15 | 52 | raw+raw-array | Modifier×24B |
| `generated_arc_settings.dl_bin` | 1,708 | 1 | 16 | array | ArcInfo×104B |
| `generated_distant_war_effect_settings.dl_bin` | 1,468 | 7 | 26 | raw+raw-array | DistantWarEffectPool×48B |
| `generated_video_ui_settings.dl_bin` | 1,124 | 1 | 9 | array | VideoUIElement×120B |
| `generated_candidate_descs.dl_bin` | 812 | 1 | 12 | array+tail | CandidateDescription×40B |
| `generated_font_lookup.dl_bin` | 604 | 6 | 19 | raw-array | FontLookup×24B |
| `generated_policy_settings.dl_bin` | 480 | 1 | 14 | raw | PolicySettings×32B |
| `generated_route_settings.dl_bin` | 436 | 3 | 3 | raw-array | RouteSettings×112B |
| `generated_corporation_logos.dl_bin` | 364 | 1 | 8 | array | CorporationLogo×40B |
| `generated_add_resource_dependencies.dl_bin` | 180 | 2 | 6 | array | 0x06F9ABD0×16B |
| `generated_stratagem_upgrade_settings.dl_bin` | 133 | 1 | 1 | hashmap+rows | StratagemCustomizationInfo×64B |
| `generated_body_settings.dl_bin` | 116 | 2 | 2 | raw-array | HelldiverBody×32B |
| `generated_layer_package_indirection_settings.dl_bin` | 108 | 1 | 5 | raw-array | PackageLayerTagIndirection×16B |
| `generated_resource_swap.dl_bin` | 24 | 0 | 0 |  |  |

## Field layouts

### 0x06F9ABD0  (`generated_add_resource_dependencies.dl_bin`, stride 16 B, rows 6)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | 0x1F0B6202 (`0x1F0B6202`) | |

### AnimationEventTriggerSetting  (`generated_animation_event_trigger_settings.dl_bin`, stride 24 B, rows 213)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | AnimationEventTrigger (`0x37B7C916`) | |

### ArcInfo  (`generated_arc_settings.dl_bin`, stride 104 B, rows 16)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | ArcType (`0xA064A858`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | DamageInfoType (`0x39D2F78D`) | |
| 40 | 8 | 0x00000000 (`0x00000000`) | |
| 48 | 8 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 64 | 8 | 0x00000000 (`0x00000000`) | |
| 72 | 4 | HitEffectDamageType (`0xB43002D3`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 8 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | 0x00000000 (`0x00000000`) | |
| 92 | 1 | 0x00000000 (`0x00000000`) | |
| 96 | 4 | 0x00000000 (`0x00000000`) | |
| 100 | 1 | 0x00000000 (`0x00000000`) | |

### BeamInfo  (`generated_beam_settings.dl_bin`, stride 112 B, rows 30)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | BeamType (`0xAD8F0477`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | DamageInfoType (`0x39D2F78D`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | SurfaceImpactType (`0xCF328969`) | |
| 48 | 8 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |
| 64 | 8 | 0x00000000 (`0x00000000`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | RaycastTemplate (`0xD7658573`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | HitEffectDamageType (`0xB43002D3`) | |
| 92 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 4 | ExplosionType (`0x11BEEE03`) | |
| 100 | 1 | 0x00000000 (`0x00000000`) | |
| 104 | 4 | DangerLevel (`0x6A3EC669`) | |
| 108 | 1 | 0x00000000 (`0x00000000`) | |

### HelldiverBody  (`generated_body_settings.dl_bin`, stride 32 B, rows 2)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | HelldiverCustomizationBodyType (`0x793E06A8`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |

### CandidateDescription  (`generated_candidate_descs.dl_bin`, stride 40 B, rows 12)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 16 | CandidateTierSpeech (`0xEF6859E9`) | |

### CollisionEventSetting  (`generated_collision_event_settings.dl_bin`, stride 80 B, rows 180)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 48 | EffectSetting (`0x10CEE58B`) | |
| 72 | 1 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |

### CorporationLogo  (`generated_corporation_logos.dl_bin`, stride 40 B, rows 8)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | Corporation (`0x4102A6B0`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |

### CreditsRowData  (`generated_credits_settings.dl_bin`, stride 64 B, rows 4,515)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | MenuFontStyle (`0x360D7FBD`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 8 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | 0x00000000 (`0x00000000`) | |

### HelldiverCustomizationKit  (`generated_customization_armor_sets.dl_bin`, stride 64 B, rows 6,821)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | HelldiverCustomizationRarity (`0x00818233`) | |
| 28 | 4 | HelldiverCustomizationPassiveBonus (`0x1F938AFA`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | HelldiverCustomizationKitType (`0x089EC682`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 16 | HelldiverBodyTypePieces (`0xBCB00FA8`) | |

### HelldiverCustomizationPassiveBonusSettings  (`generated_customization_passive_bonuses.dl_bin`, stride 56 B, rows 40)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | HelldiverCustomizationPassiveBonus (`0x1F938AFA`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 16 | HelldiverCustomizationPassiveBonusModifier (`0xB5EE1FE9`) | |
| 32 | 16 | HelldiverCustomizationStatModifier (`0xD269EE03`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |

### DamageArmorAngles  (`generated_damage_settings.dl_bin`, stride 32 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | 0x00000000 (`0x00000000`) | |
| 16 | 16 | 0x00000000 (`0x00000000`) | |

### DamageInfo  (`generated_damage_settings.dl_bin`, stride 76 B, rows 661)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | DamageInfoType (`0x39D2F78D`) | |
| 4 | 8 | 0x00000000 (`0x00000000`) | |
| 12 | 16 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | ElementType (`0x86B0A9AC`) | |
| 44 | 32 | DamageStatusEffectInfo (`0xB99AE45C`) | |

### DestructionSettings  (`generated_destruction_settings.dl_bin`, stride 168 B, rows 7,953)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 144 | DestructionEventLevel (`0xF8CBFA8E`) | |
| 144 | 1 | 0x00000000 (`0x00000000`) | |
| 148 | 4 | 0x00000000 (`0x00000000`) | |
| 152 | 1 | 0x00000000 (`0x00000000`) | |
| 152 | 1 | 0x00000000 (`0x00000000`) | |
| 152 | 1 | 0x00000000 (`0x00000000`) | |
| 152 | 1 | 0x00000000 (`0x00000000`) | |
| 156 | 12 | CApiVector3 (`0x85B82A43`) | |

### DestructionTemplates  (`generated_destruction_settings.dl_bin`, stride 16 B, rows 11)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | DestructionTemplate (`0xB247DB30`) | |

### DestructionHashMap  (`generated_destruction_settings.dl_bin`, stride 16 B, rows 8,192)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | DestructionHashEntry (`0x8CE2D12A`) | |

### DistantWarEffectPool  (`generated_distant_war_effect_settings.dl_bin`, stride 48 B, rows 26)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | DistantWarEffectPoolType (`0x744AABCA`) | |
| 4 | 4 | DistantWarEffectPoolLoadType (`0xA3981C2A`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | CApiVector2 (`0x85B82A42`) | |
| 24 | 8 | CApiVector2 (`0x85B82A42`) | |
| 32 | 16 | DistantWarEffect (`0x4304352E`) | |

### EntitySettingsHashmap  (`generated_entities.dl_bin`, stride 131072 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 131072 | EntitySettings (`0xF38A4C8E`) | |

### EntityNetworkDataArray  (`generated_entities.dl_bin`, stride 15072 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 15072 | EntityNetworkData (`0xF6239341`) | |

### VisibilityComponentData  (`generated_entities.dl_bin`, stride 3392 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2464 | ComponentIndexData (`0xFCDFC705`) | |
| 2464 | 924 | VisibilityComponent (`0xB44C147B`) | |

### LocalUnitComponentData  (`generated_entities.dl_bin`, stride 2784 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1856 | ComponentIndexData (`0xFCDFC705`) | |
| 1856 | 928 | LocalUnitComponent (`0xFB5A80FE`) | |

### TagComponentData  (`generated_entities.dl_bin`, stride 326592 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 18144 | ComponentIndexData (`0xFCDFC705`) | |
| 18144 | 308448 | TagComponent (`0x51DF988F`) | |

### WeaponMagazineComponentData  (`generated_entities.dl_bin`, stride 53152 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8832 | ComponentIndexData (`0xFCDFC705`) | |
| 8832 | 44320 | WeaponMagazineComponent (`0xFBA3CBE9`) | |

### 0xD74E6E1A  (`generated_entities.dl_bin`, stride 128 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 96 | 0x08768DE0 (`0x08768DE0`) | |

### GameModeComponentData  (`generated_entities.dl_bin`, stride 2128 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) | |
| 608 | 1520 | GameModeComponent (`0x420B6672`) | |

### RandomSlotComponentData  (`generated_entities.dl_bin`, stride 120 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 24 | RandomSlotComponent (`0xC01586F6`) | |

### PowerGeneratorComponentData  (`generated_entities.dl_bin`, stride 200 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) | |
| 160 | 40 | PowerGeneratorComponent (`0x1B6E25C7`) | |

### HitEffectComponentData  (`generated_entities.dl_bin`, stride 24080 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 9632 | ComponentIndexData (`0xFCDFC705`) | |
| 9632 | 14448 | HitEffectComponent (`0xCEB1EF25`) | |

### 0x295933BE  (`generated_entities.dl_bin`, stride 64 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 32 | 0xE2582184 (`0xE2582184`) | |

### SpawnOnPlayersComponentData  (`generated_entities.dl_bin`, stride 2552 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 928 | ComponentIndexData (`0xFCDFC705`) | |
| 928 | 1624 | SpawnOnPlayersComponent (`0x618C4AF9`) | |

### PowerSwitchTargetComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 12 | PowerSwitchTargetComponent (`0x8352E479`) | |

### ResourceDependencyComponentData  (`generated_entities.dl_bin`, stride 65624 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 65536 | ComponentIndexData (`0xFCDFC705`) | |
| 65536 | 88 | ResourceDependencyComponent (`0x8611A8BA`) | |

### StratagemScramblerComponentData  (`generated_entities.dl_bin`, stride 240 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 112 | StratagemScramblerComponent (`0x665F3DD6`) | |

### ObjectiveWidgetPriorityComponentData  (`generated_entities.dl_bin`, stride 544 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) | |
| 480 | 64 | ObjectiveWidgetPriorityComponent (`0x4FFCA954`) | |

### 0xA43A4273  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 4 | 0x7FDC1DB9 (`0x7FDC1DB9`) | |

### OrbitalTargetPriorityComponentData  (`generated_entities.dl_bin`, stride 288 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 32 | OrbitalTargetPriorityComponent (`0x451F5F69`) | |

### NpcDialogueComponentData  (`generated_entities.dl_bin`, stride 4312 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2464 | ComponentIndexData (`0xFCDFC705`) | |
| 2464 | 1848 | NpcDialogueComponent (`0x9559E9DE`) | |

### ObjectiveVehicleDeliveryComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 8 | ObjectiveVehicleDeliveryComponent (`0xEF1B98B2`) | |

### StratagemBlockerComponentData  (`generated_entities.dl_bin`, stride 368 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) | |
| 224 | 140 | StratagemBlockerComponent (`0xAABFE3FD`) | |

### LoadoutPackageComponentData  (`generated_entities.dl_bin`, stride 35232 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 17600 | ComponentIndexData (`0xFCDFC705`) | |
| 17600 | 17632 | LoadoutPackageComponent (`0x2B9E02D7`) | |

### LoadoutEntryComponentData  (`generated_entities.dl_bin`, stride 13536 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6368 | ComponentIndexData (`0xFCDFC705`) | |
| 6368 | 6368 | LoadoutEntryComponent (`0x838F9D5D`) | |
| 12736 | 796 | 0x00000000 (`0x00000000`) | |

### ReinforcementLocationComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 4 | ReinforcementLocationComponent (`0xBB40DC5D`) | |

### ObjectiveCarryDeployAreaComponentData  (`generated_entities.dl_bin`, stride 176 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 48 | ObjectiveCarryDeployAreaComponent (`0xC81BC175`) | |

### MeleeAttackComponentData  (`generated_entities.dl_bin`, stride 8032 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5344 | ComponentIndexData (`0xFCDFC705`) | |
| 5344 | 2688 | MeleeAttackComponent (`0xDBCED0D3`) | |

### ShipCustomizationComponentData  (`generated_entities.dl_bin`, stride 12368 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 12336 | ShipCustomizationComponent (`0x415F5D20`) | |

### MusicIntensifierComponentData  (`generated_entities.dl_bin`, stride 7336 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4192 | ComponentIndexData (`0xFCDFC705`) | |
| 4192 | 3144 | MusicIntensifierComponent (`0x3467A794`) | |

### LevitationAreaComponentData  (`generated_entities.dl_bin`, stride 96 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 32 | LevitationAreaComponent (`0xF8CA046B`) | |

### PrespawnLocationComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 16 | PrespawnLocationComponent (`0x5B5B149C`) | |

### ObjectiveDeliverableVehicleComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 4 | ObjectiveDeliverableVehicleComponent (`0x9B8A15CD`) | |

### ShipModulesSyncComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 40 | ShipModulesSyncComponent (`0x27085D9D`) | |

### ShipMasterComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 132 | ShipMasterComponent (`0x670FD5D3`) | |

### KillStreakComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 136 | KillStreakComponent (`0x301E5EC9`) | |

### KeypadCodeRevealComponentData  (`generated_entities.dl_bin`, stride 216 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 24 | KeypadCodeRevealComponent (`0x5704118B`) | |

### ObjectiveConvoyComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 8 | ObjectiveConvoyComponent (`0x22A86C2C`) | |

### TutorialComponentData  (`generated_entities.dl_bin`, stride 296 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 260 | TutorialComponent (`0x51F51E27`) | |

### DamagePropagatorComponentData  (`generated_entities.dl_bin`, stride 472 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) | |
| 416 | 52 | DamagePropagatorComponent (`0x6003FF51`) | |

### EffectSwitcherComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 128 | EffectSwitcherComponent (`0xD02E4C49`) | |

### AiSquadMemberComponentData  (`generated_entities.dl_bin`, stride 6648 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4832 | ComponentIndexData (`0xFCDFC705`) | |
| 4832 | 1812 | AiSquadMemberComponent (`0x566AA053`) | |

### BackpackComponentData  (`generated_entities.dl_bin`, stride 1160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1120 | ComponentIndexData (`0xFCDFC705`) | |
| 1120 | 35 | BackpackComponent (`0x2612EF83`) | |

### VehicleCollisionInfoComponentData  (`generated_entities.dl_bin`, stride 6376 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5664 | ComponentIndexData (`0xFCDFC705`) | |
| 5664 | 708 | VehicleCollisionInfoComponent (`0x32D207AB`) | |

### DormancyComponentData  (`generated_entities.dl_bin`, stride 616 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) | |
| 448 | 168 | DormancyComponent (`0x0CBCC690`) | |

### WeaponAttachmentComponentData  (`generated_entities.dl_bin`, stride 400 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 44 | WeaponAttachmentComponent (`0xF2135B86`) | |

### BackblastComponentData  (`generated_entities.dl_bin`, stride 2080 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) | |
| 672 | 1408 | BackblastComponent (`0x91A80A1A`) | |

### WeaponAssistedReloadComponentData  (`generated_entities.dl_bin`, stride 952 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) | |
| 224 | 728 | WeaponAssistedReloadComponent (`0x2D56A994`) | |

### VehicleStorageComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 128 | VehicleStorageComponent (`0xA8DA5E48`) | |

### CharacterVoiceComponentData  (`generated_entities.dl_bin`, stride 112 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 16 | CharacterVoiceComponent (`0x4525A336`) | |

### ExplorationRewardComponentData  (`generated_entities.dl_bin`, stride 336 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 144 | ExplorationRewardComponent (`0x647E42CD`) | |

### EquipmentShowcaseComponentData  (`generated_entities.dl_bin`, stride 20520 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5472 | ComponentIndexData (`0xFCDFC705`) | |
| 5472 | 15048 | EquipmentShowcaseComponent (`0x2C220E88`) | |

### BuoyancyComponentData  (`generated_entities.dl_bin`, stride 2376 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) | |
| 288 | 2088 | BuoyancyComponent (`0x0D74501D`) | |

### VoIntensityComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 124 | VoIntensityComponent (`0x23F8E07F`) | |

### VistaShipPositionComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 48 | VistaShipPositionComponent (`0xF5EF3823`) | |

### WeatherControlComponentData  (`generated_entities.dl_bin`, stride 648 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) | |
| 288 | 360 | WeatherControlComponent (`0x5D3CD804`) | |

### WeaponWindUpComponentData  (`generated_entities.dl_bin`, stride 648 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) | |
| 288 | 360 | WeaponWindUpComponent (`0x600754B4`) | |

### EncyclopediaEntryComponentData  (`generated_entities.dl_bin`, stride 59400 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 21600 | ComponentIndexData (`0xFCDFC705`) | |
| 21600 | 37800 | EncyclopediaEntryComponent (`0x85C25B75`) | |

### EnemyPackageComponentData  (`generated_entities.dl_bin`, stride 10240 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5120 | ComponentIndexData (`0xFCDFC705`) | |
| 5120 | 5120 | EnemyPackageComponent (`0xD2502C9D`) | |

### 0x2CDEC6D5  (`generated_entities.dl_bin`, stride 136 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 100 | 0xF579C11B (`0xF579C11B`) | |

### CorpseDecayerComponentData  (`generated_entities.dl_bin`, stride 2360 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1888 | ComponentIndexData (`0xFCDFC705`) | |
| 1888 | 472 | CorpseDecayerComponent (`0x98269C3C`) | |

### ConvoyComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 12 | ConvoyComponent (`0x2DE556F1`) | |

### EnvironmentalHazardComponentData  (`generated_entities.dl_bin`, stride 680 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) | |
| 416 | 260 | EnvironmentalHazardComponent (`0xC456924F`) | |

### VistaEffectComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 4 | VistaEffectComponent (`0x99B83B87`) | |

### EntityBindComponentData  (`generated_entities.dl_bin`, stride 3240 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2880 | ComponentIndexData (`0xFCDFC705`) | |
| 2880 | 360 | EntityBindComponent (`0xE37B720D`) | |

### EnvironmentalEffectTagComponentData  (`generated_entities.dl_bin`, stride 480 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 384 | ComponentIndexData (`0xFCDFC705`) | |
| 384 | 96 | EnvironmentalEffectTagComponent (`0x2231511E`) | |

### WorldLootManagerComponentData  (`generated_entities.dl_bin`, stride 30024 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) | |
| 608 | 29412 | WorldLootManagerComponent (`0x2A037914`) | |

### StaticPositionComponentData  (`generated_entities.dl_bin`, stride 3832 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 3712 | ComponentIndexData (`0xFCDFC705`) | |
| 3712 | 116 | StaticPositionComponent (`0x15C2CDB0`) | |

### UnitComponentData  (`generated_entities.dl_bin`, stride 288928 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 55008 | ComponentIndexData (`0xFCDFC705`) | |
| 55008 | 233920 | UnitComponent (`0x18ECD593`) | |

### MaterialSwapComponentData  (`generated_entities.dl_bin`, stride 92160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1536 | ComponentIndexData (`0xFCDFC705`) | |
| 1536 | 90624 | MaterialSwapComponent (`0xFB9C3D3D`) | |

### FactionComponentData  (`generated_entities.dl_bin`, stride 98224 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 17056 | ComponentIndexData (`0xFCDFC705`) | |
| 17056 | 81168 | FactionComponent (`0x37DA66D7`) | |

### VehicleComponentData  (`generated_entities.dl_bin`, stride 78424 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 640 | ComponentIndexData (`0xFCDFC705`) | |
| 640 | 77784 | VehicleComponent (`0x6D4CC953`) | |

### ObjectiveComponentData  (`generated_entities.dl_bin`, stride 593712 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6944 | ComponentIndexData (`0xFCDFC705`) | |
| 6944 | 586768 | ObjectiveComponent (`0x4EB42DEE`) | |

### MinefieldComponentData  (`generated_entities.dl_bin`, stride 1032 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) | |
| 416 | 616 | MinefieldComponent (`0xF285D860`) | |

### ShieldComponentData  (`generated_entities.dl_bin`, stride 5984 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) | |
| 480 | 5504 | ShieldComponent (`0x11A2352C`) | |

### OrbitalShipComponentData  (`generated_entities.dl_bin`, stride 568 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) | |
| 544 | 17 | OrbitalShipComponent (`0x03901E14`) | |

### NoiseComponentData  (`generated_entities.dl_bin`, stride 880 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 704 | ComponentIndexData (`0xFCDFC705`) | |
| 704 | 176 | NoiseComponent (`0xD9CFC111`) | |

### SquadTransportComponentData  (`generated_entities.dl_bin`, stride 1200 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 1008 | SquadTransportComponent (`0x0AFBAD9E`) | |

### 0xF34610E9  (`generated_entities.dl_bin`, stride 112 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 12 | 0x12C7212F (`0x12C7212F`) | |

### RechargeComponentData  (`generated_entities.dl_bin`, stride 112 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 16 | RechargeComponent (`0x69900D54`) | |

### InteractableMinigameComponentData  (`generated_entities.dl_bin`, stride 795232 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2400 | ComponentIndexData (`0xFCDFC705`) | |
| 2400 | 792832 | InteractableMinigameComponent (`0x4169A708`) | |

### ObjectiveCarryDeliveryComponentData  (`generated_entities.dl_bin`, stride 952 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) | |
| 544 | 408 | ObjectiveCarryDeliveryComponent (`0xA5B0C973`) | |

### DestructibleComponentData  (`generated_entities.dl_bin`, stride 9872 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 9568 | ComponentIndexData (`0xFCDFC705`) | |
| 9568 | 299 | DestructibleComponent (`0xA4FFE67D`) | |

### EffectReferenceComponentData  (`generated_entities.dl_bin`, stride 2733192 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 22176 | ComponentIndexData (`0xFCDFC705`) | |
| 22176 | 2711016 | EffectReferenceComponent (`0xC98E550F`) | |

### CollisionEventComponentData  (`generated_entities.dl_bin`, stride 30848 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 15424 | ComponentIndexData (`0xFCDFC705`) | |
| 15424 | 15424 | CollisionEventComponent (`0x907000C1`) | |

### PhysicsImpactEffectComponentData  (`generated_entities.dl_bin`, stride 49232 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 11584 | ComponentIndexData (`0xFCDFC705`) | |
| 11584 | 37648 | PhysicsImpactEffectComponent (`0x3F0D9F21`) | |

### PoweredDeathSequenceComponentData  (`generated_entities.dl_bin`, stride 17280 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2880 | ComponentIndexData (`0xFCDFC705`) | |
| 2880 | 14400 | PoweredDeathSequenceComponent (`0xBF027488`) | |

### WeaponScreenComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 8 | WeaponScreenComponent (`0x2B8DF91D`) | |

### PowerSwitchComponentData  (`generated_entities.dl_bin`, stride 1872 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1152 | ComponentIndexData (`0xFCDFC705`) | |
| 1152 | 720 | PowerSwitchComponent (`0x5C13F512`) | |

### WoundableComponentData  (`generated_entities.dl_bin`, stride 6384 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 3648 | ComponentIndexData (`0xFCDFC705`) | |
| 3648 | 2736 | WoundableComponent (`0x432D1854`) | |

### WieldableComponentData  (`generated_entities.dl_bin`, stride 32960 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16480 | ComponentIndexData (`0xFCDFC705`) | |
| 16480 | 16480 | WieldableComponent (`0xC83092BC`) | |

### RemoteTriggerComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 4 | RemoteTriggerComponent (`0x42C6F973`) | |

### WeaponReloadComponentData  (`generated_entities.dl_bin`, stride 28528 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8128 | ComponentIndexData (`0xFCDFC705`) | |
| 8128 | 20400 | WeaponReloadComponent (`0xCE31EB14`) | |

### RagdollSyncComponentData  (`generated_entities.dl_bin`, stride 136136 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2464 | ComponentIndexData (`0xFCDFC705`) | |
| 2464 | 133672 | RagdollSyncComponent (`0xDF297875`) | |

### WeaponLinkerComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 48 | WeaponLinkerComponent (`0x107DA162`) | |

### WarHologramComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 44 | WarHologramComponent (`0xF84673F6`) | |

### WeaponRoundsComponentData  (`generated_entities.dl_bin`, stride 4336 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 800 | ComponentIndexData (`0xFCDFC705`) | |
| 800 | 3536 | WeaponRoundsComponent (`0x84CCC438`) | |

### ProjectileClusterComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 16 | ProjectileClusterComponent (`0x77A73C46`) | |

### StanceComponentData  (`generated_entities.dl_bin`, stride 5984 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 704 | ComponentIndexData (`0xFCDFC705`) | |
| 704 | 5280 | StanceComponent (`0x6A0316F1`) | |

### SquadTransportFormationComponentData  (`generated_entities.dl_bin`, stride 7200 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2880 | ComponentIndexData (`0xFCDFC705`) | |
| 2880 | 4320 | SquadTransportFormationComponent (`0xD829390D`) | |

### StatusEffectVolumeComponentData  (`generated_entities.dl_bin`, stride 6176 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 5920 | StatusEffectVolumeComponent (`0x6FE5E9DC`) | |

### SpawnLinkComponentData  (`generated_entities.dl_bin`, stride 1800 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 960 | ComponentIndexData (`0xFCDFC705`) | |
| 960 | 840 | SpawnLinkComponent (`0x2E612FAA`) | |

### SpottableComponentData  (`generated_entities.dl_bin`, stride 72800 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 22400 | ComponentIndexData (`0xFCDFC705`) | |
| 22400 | 50400 | SpottableComponent (`0x5C1FBB21`) | |

### TargetableFleetShipComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 16 | TargetableFleetShipComponent (`0xA613E132`) | |

### TrampleComponentData  (`generated_entities.dl_bin`, stride 13816 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5024 | ComponentIndexData (`0xFCDFC705`) | |
| 5024 | 8792 | TrampleComponent (`0xBA9960E8`) | |

### TriggerAreaLogicComponentData  (`generated_entities.dl_bin`, stride 768 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 512 | TriggerAreaLogicComponent (`0xC98D5D6E`) | |

### StratagemFiresupportComponentData  (`generated_entities.dl_bin`, stride 616 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) | |
| 544 | 68 | StratagemFiresupportComponent (`0xABC88BDE`) | |

### TransportComponentData  (`generated_entities.dl_bin`, stride 1008 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) | |
| 448 | 560 | TransportComponent (`0x35CCCFC0`) | |

### VehicleShuttleComponentData  (`generated_entities.dl_bin`, stride 664 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 308 | VehicleShuttleComponent (`0x40A01E7C`) | |

### ShipCustomizationTargetComponentData  (`generated_entities.dl_bin`, stride 504 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) | |
| 160 | 340 | ShipCustomizationTargetComponent (`0xD33B9F07`) | |

### ShieldControllerComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 8 | ShieldControllerComponent (`0xC7041FD0`) | |

### SensorDangerComponentData  (`generated_entities.dl_bin`, stride 8408 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6112 | ComponentIndexData (`0xFCDFC705`) | |
| 6112 | 2292 | SensorDangerComponent (`0x0A6D35FE`) | |

### ShowOnMapComponentData  (`generated_entities.dl_bin`, stride 2080 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 832 | ComponentIndexData (`0xFCDFC705`) | |
| 832 | 1248 | ShowOnMapComponent (`0x9433E54F`) | |

### TutorialTargetRangeComponentData  (`generated_entities.dl_bin`, stride 312 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 248 | TutorialTargetRangeComponent (`0x1B78079B`) | |

### ShipPropVisibilityComponentData  (`generated_entities.dl_bin`, stride 1160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) | |
| 544 | 612 | ShipPropVisibilityComponent (`0x83724730`) | |

### ShipTeleporterComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 12 | ShipTeleporterComponent (`0xCD6AB78D`) | |

### FireSourceComponentData  (`generated_entities.dl_bin`, stride 104 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 40 | FireSourceComponent (`0x0C33606A`) | |

### 0xCE728CA9  (`generated_entities.dl_bin`, stride 256 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 192 | 0x298BBCEF (`0x298BBCEF`) | |

### FakeGravityMotionComponentData  (`generated_entities.dl_bin`, stride 360 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 168 | FakeGravityMotionComponent (`0xC6AC7AC6`) | |

### MaterialVariablesComponentData  (`generated_entities.dl_bin`, stride 119072 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1952 | ComponentIndexData (`0xFCDFC705`) | |
| 1952 | 117120 | MaterialVariablesComponent (`0x6B91FB5B`) | |

### LootDropComponentData  (`generated_entities.dl_bin`, stride 1664 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 832 | ComponentIndexData (`0xFCDFC705`) | |
| 832 | 832 | LootDropComponent (`0x3A79E786`) | |

### GameEventShipComponentData  (`generated_entities.dl_bin`, stride 7976 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 7944 | GameEventShipComponent (`0x0C1C32E3`) | |

### FogMachineComponentData  (`generated_entities.dl_bin`, stride 1584 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 704 | ComponentIndexData (`0xFCDFC705`) | |
| 704 | 880 | FogMachineComponent (`0x4DDF3CE4`) | |

### ExtractionZoneComponentData  (`generated_entities.dl_bin`, stride 104 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 6 | ExtractionZoneComponent (`0x37340A30`) | |

### MinigameStratagemArcadeComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 44 | MinigameStratagemArcadeComponent (`0xA77CF722`) | |

### MinigameWaitComponentData  (`generated_entities.dl_bin`, stride 6960 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1856 | ComponentIndexData (`0xFCDFC705`) | |
| 1856 | 5104 | MinigameWaitComponent (`0x8B438E0F`) | |

### MinigameExternalSwitchesComponentData  (`generated_entities.dl_bin`, stride 2856 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) | |
| 672 | 2184 | MinigameExternalSwitchesComponent (`0xCBE67607`) | |

### DynamicLightComponentData  (`generated_entities.dl_bin`, stride 488 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 132 | DynamicLightComponent (`0xE14B4B70`) | |

### HellpodRackComponentData  (`generated_entities.dl_bin`, stride 43768 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2304 | ComponentIndexData (`0xFCDFC705`) | |
| 2304 | 41464 | HellpodRackComponent (`0x817B931C`) | |

### InteractableObjectiveTerminalComponentData  (`generated_entities.dl_bin`, stride 9640 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2336 | ComponentIndexData (`0xFCDFC705`) | |
| 2336 | 7300 | InteractableObjectiveTerminalComponent (`0x89F44898`) | |

### InteractableStateSwitchComponentData  (`generated_entities.dl_bin`, stride 7400 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 800 | ComponentIndexData (`0xFCDFC705`) | |
| 800 | 6600 | InteractableStateSwitchComponent (`0x1B0491B4`) | |

### AnimationComponentData  (`generated_entities.dl_bin`, stride 110880 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 24640 | ComponentIndexData (`0xFCDFC705`) | |
| 24640 | 86240 | AnimationComponent (`0x4210E273`) | |

### HitReactComponentData  (`generated_entities.dl_bin`, stride 954128 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6272 | ComponentIndexData (`0xFCDFC705`) | |
| 6272 | 947856 | HitReactComponent (`0xC299C547`) | |

### HintTriggerComponentData  (`generated_entities.dl_bin`, stride 8640 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 3840 | ComponentIndexData (`0xFCDFC705`) | |
| 3840 | 4800 | HintTriggerComponent (`0x43AB1F7A`) | |

### HellpodPayloadComponentData  (`generated_entities.dl_bin`, stride 5160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 3744 | ComponentIndexData (`0xFCDFC705`) | |
| 3744 | 1416 | HellpodPayloadComponent (`0x4B889585`) | |

### AttackPatternComponentData  (`generated_entities.dl_bin`, stride 2208 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 2176 | AttackPatternComponent (`0xCE83B069`) | |

### LootContainerComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 8 | LootContainerComponent (`0x93703274`) | |

### GibEntityComponentData  (`generated_entities.dl_bin`, stride 1264 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) | |
| 480 | 780 | GibEntityComponent (`0xE93DC9C2`) | |

### LaserDesignatorComponentData  (`generated_entities.dl_bin`, stride 384 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 256 | LaserDesignatorComponent (`0xB7D3043A`) | |

### ObjectiveRescuePointComponentData  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 128 | ObjectiveRescuePointComponent (`0x6082C7BF`) | |

### ObjectiveSecureAreaComponentData  (`generated_entities.dl_bin`, stride 472 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 340 | ObjectiveSecureAreaComponent (`0xE656A5CE`) | |

### CarryEffectComponentData  (`generated_entities.dl_bin`, stride 264 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) | |
| 160 | 100 | CarryEffectComponent (`0xFD2E3F41`) | |

### ObjectiveOilRigComponentData  (`generated_entities.dl_bin`, stride 256 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 128 | ObjectiveOilRigComponent (`0x7C9E8EF4`) | |

### ObjectivePreventInvasionComponentData  (`generated_entities.dl_bin`, stride 376 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 344 | ObjectivePreventInvasionComponent (`0xDF5D1959`) | |

### 0x430CA328  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 16 | 0x29786BEE (`0x29786BEE`) | |

### ObjectiveShellComponentData  (`generated_entities.dl_bin`, stride 512 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 256 | ObjectiveShellComponent (`0x05330626`) | |

### ObstacleComponentData  (`generated_entities.dl_bin`, stride 704 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) | |
| 224 | 476 | ObstacleComponent (`0x446996E0`) | |

### DangerWarningComponentData  (`generated_entities.dl_bin`, stride 1456 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1056 | ComponentIndexData (`0xFCDFC705`) | |
| 1056 | 396 | DangerWarningComponent (`0xF3B0BFBA`) | |

### DepositComponentData  (`generated_entities.dl_bin`, stride 5672 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 960 | ComponentIndexData (`0xFCDFC705`) | |
| 960 | 4712 | DepositComponent (`0x038A5CCB`) | |

### ObjectiveShellRackComponentData  (`generated_entities.dl_bin`, stride 48 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 12 | ObjectiveShellRackComponent (`0x54FF6027`) | |

### ObjectiveShuttleControllerComponentData  (`generated_entities.dl_bin`, stride 480 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) | |
| 160 | 320 | ObjectiveShuttleControllerComponent (`0x2D347B1B`) | |

### NetworkPhysicsComponentData  (`generated_entities.dl_bin`, stride 14064 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 9376 | ComponentIndexData (`0xFCDFC705`) | |
| 9376 | 4688 | NetworkPhysicsComponent (`0x2C6F4C60`) | |

### 0x88630F9F  (`generated_entities.dl_bin`, stride 56 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 24 | 0x3C3534E5 (`0x3C3534E5`) | |

### AiSpawnerComponentData  (`generated_entities.dl_bin`, stride 7528 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1056 | ComponentIndexData (`0xFCDFC705`) | |
| 1056 | 6468 | AiSpawnerComponent (`0xFE7D9FBD`) | |

### BurrowerComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 72 | BurrowerComponent (`0x56B9460B`) | |

### ObjectiveEncounterTriggerComponentData  (`generated_entities.dl_bin`, stride 816 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) | |
| 224 | 588 | ObjectiveEncounterTriggerComponent (`0x9BF2F6F5`) | |

### 0xF57457DA  (`generated_entities.dl_bin`, stride 107744 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) | |
| 416 | 107328 | 0x32AD97A0 (`0x32AD97A0`) | |

### ObjectiveDynamicLinkComponentData  (`generated_entities.dl_bin`, stride 1984 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1440 | ComponentIndexData (`0xFCDFC705`) | |
| 1440 | 540 | ObjectiveDynamicLinkComponent (`0xCE273501`) | |

### ObjectiveCarryComponentData  (`generated_entities.dl_bin`, stride 6400 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1280 | ComponentIndexData (`0xFCDFC705`) | |
| 1280 | 5120 | ObjectiveCarryComponent (`0xF6A785AF`) | |

### ObjectiveCollectResourcesComponentData  (`generated_entities.dl_bin`, stride 96 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 32 | ObjectiveCollectResourcesComponent (`0xCE4458AF`) | |

### 0xF087811C  (`generated_entities.dl_bin`, stride 160 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 96 | 0x666A6FE2 (`0x666A6FE2`) | |

### SensorEyeComponentData  (`generated_entities.dl_bin`, stride 23984 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 10080 | ComponentIndexData (`0xFCDFC705`) | |
| 10080 | 13904 | SensorEyeComponent (`0xB4789330`) | |

### SensorEarComponentData  (`generated_entities.dl_bin`, stride 8976 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5984 | ComponentIndexData (`0xFCDFC705`) | |
| 5984 | 2992 | SensorEarComponent (`0x6850F3C5`) | |

### BombardmentComponentData  (`generated_entities.dl_bin`, stride 5344 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) | |
| 736 | 4608 | BombardmentComponent (`0x0793349E`) | |

### ShieldHitFilterComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 4 | ShieldHitFilterComponent (`0x81976017`) | |

### SensorProximityComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 16 | SensorProximityComponent (`0x48572122`) | |

### SeekingMissileComponentData  (`generated_entities.dl_bin`, stride 8816 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 928 | ComponentIndexData (`0xFCDFC705`) | |
| 928 | 7888 | SeekingMissileComponent (`0x2DD927CF`) | |

### CharacterTemplateComponentData  (`generated_entities.dl_bin`, stride 1928 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1184 | ComponentIndexData (`0xFCDFC705`) | |
| 1184 | 740 | CharacterTemplateComponent (`0x791CC75C`) | |

### VisibilityMaskComponentData  (`generated_entities.dl_bin`, stride 184128 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8768 | ComponentIndexData (`0xFCDFC705`) | |
| 8768 | 175360 | VisibilityMaskComponent (`0xB4E1B587`) | |

### MineSpawnerComponentData  (`generated_entities.dl_bin`, stride 512 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 256 | MineSpawnerComponent (`0xC57D209C`) | |

### DecorationComponentData  (`generated_entities.dl_bin`, stride 672 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 640 | DecorationComponent (`0xB662B2FB`) | |

### LandingZoneBeaconComponentData  (`generated_entities.dl_bin`, stride 104 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 3 | LandingZoneBeaconComponent (`0xBEA608B4`) | |

### WeaponFlashlightComponentData  (`generated_entities.dl_bin`, stride 592 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 224 | ComponentIndexData (`0xFCDFC705`) | |
| 224 | 364 | WeaponFlashlightComponent (`0x0CDB8E03`) | |

### WeaponChargeComponentData  (`generated_entities.dl_bin`, stride 2696 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 320 | ComponentIndexData (`0xFCDFC705`) | |
| 320 | 2376 | WeaponChargeComponent (`0x3CBEA9E7`) | |

### HellpodComponentData  (`generated_entities.dl_bin`, stride 1088 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 832 | HellpodComponent (`0xA5EA069B`) | |

### UnitCustomizationComponentData  (`generated_entities.dl_bin`, stride 107832 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 3072 | ComponentIndexData (`0xFCDFC705`) | |
| 3072 | 104760 | UnitCustomizationComponent (`0xC90D306C`) | |

### NavigationComponentData  (`generated_entities.dl_bin`, stride 10960 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 7968 | ComponentIndexData (`0xFCDFC705`) | |
| 7968 | 2988 | NavigationComponent (`0x7F6D5483`) | |

### RaycastSchedulerComponentData  (`generated_entities.dl_bin`, stride 352 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 320 | RaycastSchedulerComponent (`0x6CC37AA9`) | |

### GuardForceComponentData  (`generated_entities.dl_bin`, stride 1008 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) | |
| 672 | 336 | GuardForceComponent (`0x428D2095`) | |

### GameModeMissionComponentData  (`generated_entities.dl_bin`, stride 648 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) | |
| 544 | 102 | GameModeMissionComponent (`0xBD4E2734`) | |

### HiveMindComponentData  (`generated_entities.dl_bin`, stride 22288 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) | |
| 608 | 21680 | HiveMindComponent (`0xFFF1A667`) | |

### TruthTransmitterFactionComponentData  (`generated_entities.dl_bin`, stride 416 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 384 | TruthTransmitterFactionComponent (`0x960B7A2B`) | |

### EncounterComponentData  (`generated_entities.dl_bin`, stride 64 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 32 | EncounterComponent (`0xB183DDE6`) | |

### BugholeComponentData  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 80 | BugholeComponent (`0x6E65CD39`) | |

### 0xE3F485C7  (`generated_entities.dl_bin`, stride 144 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 112 | 0xE371D70D (`0xE371D70D`) | |

### GroundCheckComponentData  (`generated_entities.dl_bin`, stride 12952 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 7968 | ComponentIndexData (`0xFCDFC705`) | |
| 7968 | 4980 | GroundCheckComponent (`0x7A8BC440`) | |

### GuidanceTargetComponentData  (`generated_entities.dl_bin`, stride 1528 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) | |
| 288 | 1240 | GuidanceTargetComponent (`0x4E6C92FA`) | |

### MovingHazardComponentData  (`generated_entities.dl_bin`, stride 384 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 192 | MovingHazardComponent (`0xEB79BE1D`) | |

### SearchlightEnemyComponentData  (`generated_entities.dl_bin`, stride 192 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 128 | SearchlightEnemyComponent (`0x87D0A7BF`) | |

### OverlapDamageComponentData  (`generated_entities.dl_bin`, stride 100864 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2048 | ComponentIndexData (`0xFCDFC705`) | |
| 2048 | 98816 | OverlapDamageComponent (`0xF38A964B`) | |

### HealthComponentData  (`generated_entities.dl_bin`, stride 11218864 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16192 | ComponentIndexData (`0xFCDFC705`) | |
| 16192 | 11202672 | HealthComponent (`0x728F0129`) | |

### VehicleMotionComponentData  (`generated_entities.dl_bin`, stride 6832 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) | |
| 448 | 6384 | VehicleMotionComponent (`0x48F7C789`) | |

### MeleeShieldComponentData  (`generated_entities.dl_bin`, stride 176 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 108 | MeleeShieldComponent (`0x7E824934`) | |

### DamageZoneShieldComponentData  (`generated_entities.dl_bin`, stride 35136 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 34944 | DamageZoneShieldComponent (`0x868B11A7`) | |

### GoreComponentData  (`generated_entities.dl_bin`, stride 7039200 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6720 | ComponentIndexData (`0xFCDFC705`) | |
| 6720 | 7032480 | GoreComponent (`0x66518C40`) | |

### VehicleElectricsComponentData  (`generated_entities.dl_bin`, stride 34112 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 416 | ComponentIndexData (`0xFCDFC705`) | |
| 416 | 33696 | VehicleElectricsComponent (`0x5322DCD1`) | |

### AvatarComponentData  (`generated_entities.dl_bin`, stride 1736 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 1704 | AvatarComponent (`0xB501F712`) | |

### EquipmentComponentData  (`generated_entities.dl_bin`, stride 92896 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 11232 | ComponentIndexData (`0xFCDFC705`) | |
| 11232 | 81664 | EquipmentComponent (`0xD4967A6B`) | |

### TargetingComponentData  (`generated_entities.dl_bin`, stride 28512 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 9504 | ComponentIndexData (`0xFCDFC705`) | |
| 9504 | 19008 | TargetingComponent (`0x5E30EC98`) | |

### WeaponWielderComponentData  (`generated_entities.dl_bin`, stride 15032 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 7072 | ComponentIndexData (`0xFCDFC705`) | |
| 7072 | 7956 | WeaponWielderComponent (`0x967FB669`) | |

### WeaponDataComponentData  (`generated_entities.dl_bin`, stride 475696 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 11936 | ComponentIndexData (`0xFCDFC705`) | |
| 11936 | 463760 | WeaponDataComponent (`0xD25FC7F7`) | |

### InventoryComponentData  (`generated_entities.dl_bin`, stride 15280 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2752 | ComponentIndexData (`0xFCDFC705`) | |
| 2752 | 12528 | InventoryComponent (`0x1BBAEB81`) | |

### MultiTargetComponentData  (`generated_entities.dl_bin`, stride 22016 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1024 | ComponentIndexData (`0xFCDFC705`) | |
| 1024 | 20988 | MultiTargetComponent (`0x23A58AC5`) | |

### InteractorComponentData  (`generated_entities.dl_bin`, stride 80 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 48 | InteractorComponent (`0xB52212CE`) | |

### InteractableComponentData  (`generated_entities.dl_bin`, stride 638432 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 17984 | ComponentIndexData (`0xFCDFC705`) | |
| 17984 | 620448 | InteractableComponent (`0xB6109121`) | |

### RotationSoundPlayerComponentData  (`generated_entities.dl_bin`, stride 832 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) | |
| 288 | 540 | RotationSoundPlayerComponent (`0xB1FA2519`) | |

### WeaponLinkedAmmoComponentData  (`generated_entities.dl_bin`, stride 584 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 392 | WeaponLinkedAmmoComponent (`0xFCBC2A9E`) | |

### StickyComponentData  (`generated_entities.dl_bin`, stride 2056 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 608 | ComponentIndexData (`0xFCDFC705`) | |
| 608 | 1444 | StickyComponent (`0x463F606A`) | |

### TurretComponentData  (`generated_entities.dl_bin`, stride 8072 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2368 | ComponentIndexData (`0xFCDFC705`) | |
| 2368 | 5700 | TurretComponent (`0x98FFC0D9`) | |

### StratagemBallComponentData  (`generated_entities.dl_bin`, stride 248 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 216 | StratagemBallComponent (`0xF3CBDB76`) | |

### ShipInventoryComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 8 | ShipInventoryComponent (`0x42E63ED5`) | |

### TwoPointChainAttachTargetComponentData  (`generated_entities.dl_bin`, stride 120 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 24 | TwoPointChainAttachTargetComponent (`0x1CD16F16`) | |

### TwoPointChainComponentData  (`generated_entities.dl_bin`, stride 504 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 408 | TwoPointChainComponent (`0x953D943A`) | |

### UploadDiscoveryComponentData  (`generated_entities.dl_bin`, stride 880 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 528 | UploadDiscoveryComponent (`0x596D1B70`) | |

### ExplosiveComponentData  (`generated_entities.dl_bin`, stride 28192 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2272 | ComponentIndexData (`0xFCDFC705`) | |
| 2272 | 25920 | ExplosiveComponent (`0xD866D252`) | |

### CharacterNameComponentData  (`generated_entities.dl_bin`, stride 4368 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 2912 | ComponentIndexData (`0xFCDFC705`) | |
| 2912 | 1456 | CharacterNameComponent (`0x8EDCA0C1`) | |

### ThrowerComponentData  (`generated_entities.dl_bin`, stride 4672 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) | |
| 160 | 4512 | ThrowerComponent (`0xCD78F59E`) | |

### ThrowableComponentData  (`generated_entities.dl_bin`, stride 18032 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1472 | ComponentIndexData (`0xFCDFC705`) | |
| 1472 | 16560 | ThrowableComponent (`0x5961C6FB`) | |

### WeatheringComponentData  (`generated_entities.dl_bin`, stride 2656 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 544 | ComponentIndexData (`0xFCDFC705`) | |
| 544 | 2108 | WeatheringComponent (`0x39C02001`) | |

### InteractableMenuScreenComponentData  (`generated_entities.dl_bin`, stride 1120 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) | |
| 448 | 672 | InteractableMenuScreenComponent (`0x73B8EA16`) | |

### AttachableComponentData  (`generated_entities.dl_bin`, stride 77952 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 25984 | ComponentIndexData (`0xFCDFC705`) | |
| 25984 | 51968 | AttachableComponent (`0xCB1718DC`) | |

### FriendlyNpcComponentData  (`generated_entities.dl_bin`, stride 77760 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 864 | ComponentIndexData (`0xFCDFC705`) | |
| 864 | 76896 | FriendlyNpcComponent (`0xEE5DCCF1`) | |

### JumppackComponentData  (`generated_entities.dl_bin`, stride 1216 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 1120 | JumppackComponent (`0x3A145ECE`) | |

### ArcWeaponComponentData  (`generated_entities.dl_bin`, stride 1200 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 320 | ComponentIndexData (`0xFCDFC705`) | |
| 320 | 880 | ArcWeaponComponent (`0x9BB0D833`) | |

### WeaponHeatComponentData  (`generated_entities.dl_bin`, stride 19312 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 960 | ComponentIndexData (`0xFCDFC705`) | |
| 960 | 18352 | WeaponHeatComponent (`0x3A90B51F`) | |

### AbilityWeaponComponentData  (`generated_entities.dl_bin`, stride 1080 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 288 | ComponentIndexData (`0xFCDFC705`) | |
| 288 | 792 | AbilityWeaponComponent (`0x6EC1CEAB`) | |

### MeleeWeaponComponentData  (`generated_entities.dl_bin`, stride 2464 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 2112 | MeleeWeaponComponent (`0xB1DBD585`) | |

### PhysicsWeaponComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 8 | PhysicsWeaponComponent (`0x9BDCD9A0`) | |

### BeamWeaponComponentData  (`generated_entities.dl_bin`, stride 3616 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) | |
| 736 | 2880 | BeamWeaponComponent (`0x3DA202F2`) | |

### WeaponCustomizationComponentData  (`generated_entities.dl_bin`, stride 966056 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6272 | ComponentIndexData (`0xFCDFC705`) | |
| 6272 | 959784 | WeaponCustomizationComponent (`0xB976A896`) | |

### EagleSpawnerComponentData  (`generated_entities.dl_bin`, stride 168 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 72 | EagleSpawnerComponent (`0x0CDA64D1`) | |

### FoleySoundComponentData  (`generated_entities.dl_bin`, stride 637264 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6240 | ComponentIndexData (`0xFCDFC705`) | |
| 6240 | 631020 | FoleySoundComponent (`0x5EC1F5FB`) | |

### DisplacementComponentData  (`generated_entities.dl_bin`, stride 1296 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 1264 | DisplacementComponent (`0x56EC9F0C`) | |

### AiCoverComponentData  (`generated_entities.dl_bin`, stride 496 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 480 | ComponentIndexData (`0xFCDFC705`) | |
| 480 | 15 | AiCoverComponent (`0x7710A1BC`) | |

### CurveNavigationComponentData  (`generated_entities.dl_bin`, stride 784 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 752 | CurveNavigationComponent (`0x46E9D628`) | |

### VehicleCollisionDamageComponentData  (`generated_entities.dl_bin`, stride 3360 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 448 | ComponentIndexData (`0xFCDFC705`) | |
| 448 | 2912 | VehicleCollisionDamageComponent (`0x76CC175E`) | |

### FootstepEventComponentData  (`generated_entities.dl_bin`, stride 685560 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6304 | ComponentIndexData (`0xFCDFC705`) | |
| 6304 | 679256 | FootstepEventComponent (`0xF7689E09`) | |

### ExpandableCoverComponentData  (`generated_entities.dl_bin`, stride 392 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 328 | ExpandableCoverComponent (`0x4FA9D4E6`) | |

### DetectorComponentData  (`generated_entities.dl_bin`, stride 17976 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 10272 | ComponentIndexData (`0xFCDFC705`) | |
| 10272 | 7704 | DetectorComponent (`0xE7B724AD`) | |

### MountComponentData  (`generated_entities.dl_bin`, stride 25048 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5248 | ComponentIndexData (`0xFCDFC705`) | |
| 5248 | 19800 | MountComponent (`0x8BC6DEA6`) | |

### BehaviorComponentData  (`generated_entities.dl_bin`, stride 43704 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 31776 | ComponentIndexData (`0xFCDFC705`) | |
| 31776 | 11928 | BehaviorComponent (`0xF7420683`) | |

### RouteNavigationComponentData  (`generated_entities.dl_bin`, stride 832 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) | |
| 736 | 92 | RouteNavigationComponent (`0x6B40FFB2`) | |

### SeatCollectionComponentData  (`generated_entities.dl_bin`, stride 25536 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1792 | ComponentIndexData (`0xFCDFC705`) | |
| 1792 | 23744 | SeatCollectionComponent (`0xE014C64C`) | |

### IdleAbilityComponentData  (`generated_entities.dl_bin`, stride 13568 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 3392 | ComponentIndexData (`0xFCDFC705`) | |
| 3392 | 10176 | IdleAbilityComponent (`0xE3AFA17F`) | |

### LoopingSurfaceEffectsComponentData  (`generated_entities.dl_bin`, stride 400 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 44 | LoopingSurfaceEffectsComponent (`0x3C4A0034`) | |

### AbilityComponentData  (`generated_entities.dl_bin`, stride 63616 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 31808 | ComponentIndexData (`0xFCDFC705`) | |
| 31808 | 31808 | AbilityComponent (`0x4DE4EBA1`) | |

### CommanderComponentData  (`generated_entities.dl_bin`, stride 136 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 128 | ComponentIndexData (`0xFCDFC705`) | |
| 128 | 4 | CommanderComponent (`0xEB7BC449`) | |

### ShipHellpodComponentData  (`generated_entities.dl_bin`, stride 72 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 8 | ShipHellpodComponent (`0x7DC074EF`) | |

### HiveLordComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 8 | HiveLordComponent (`0xEBB9A230`) | |

### ShipComponentData  (`generated_entities.dl_bin`, stride 40 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 8 | ShipComponent (`0x44504DC7`) | |

### StoryInteractableComponentData  (`generated_entities.dl_bin`, stride 5280 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1920 | ComponentIndexData (`0xFCDFC705`) | |
| 1920 | 3360 | StoryInteractableComponent (`0xFCA9E402`) | |

### LootComponentData  (`generated_entities.dl_bin`, stride 6688 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1216 | ComponentIndexData (`0xFCDFC705`) | |
| 1216 | 5472 | LootComponent (`0x9FB51CF1`) | |

### BoidsComponentData  (`generated_entities.dl_bin`, stride 4232 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) | |
| 736 | 3496 | BoidsComponent (`0x7AF25E84`) | |

### ThrusterGroupComponentData  (`generated_entities.dl_bin`, stride 10368 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 864 | ComponentIndexData (`0xFCDFC705`) | |
| 864 | 9504 | ThrusterGroupComponent (`0x193D4981`) | |

### VehicleCrashComponentData  (`generated_entities.dl_bin`, stride 31680 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 576 | ComponentIndexData (`0xFCDFC705`) | |
| 576 | 31104 | VehicleCrashComponent (`0xB5418864`) | |

### HoverComponentData  (`generated_entities.dl_bin`, stride 960 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 256 | ComponentIndexData (`0xFCDFC705`) | |
| 256 | 704 | HoverComponent (`0xDC219A57`) | |

### AiEnemyComponentData  (`generated_entities.dl_bin`, stride 122880 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 5120 | ComponentIndexData (`0xFCDFC705`) | |
| 5120 | 117760 | AiEnemyComponent (`0xA53879FB`) | |

### AiCharacterComponentData  (`generated_entities.dl_bin`, stride 22512 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6432 | ComponentIndexData (`0xFCDFC705`) | |
| 6432 | 16080 | AiCharacterComponent (`0xD23B3E8A`) | |

### AiSquadComponentData  (`generated_entities.dl_bin`, stride 3024 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) | |
| 672 | 2352 | AiSquadComponent (`0x4AD82C9B`) | |

### AiSquadBehaviorComponentData  (`generated_entities.dl_bin`, stride 760 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 672 | ComponentIndexData (`0xFCDFC705`) | |
| 672 | 84 | AiSquadBehaviorComponent (`0xC879B22B`) | |

### AirborneNavigationComponentData  (`generated_entities.dl_bin`, stride 176 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 140 | AirborneNavigationComponent (`0x030B4335`) | |

### StatusEffectReceiverComponentData  (`generated_entities.dl_bin`, stride 15388528 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 10528 | ComponentIndexData (`0xFCDFC705`) | |
| 10528 | 15378000 | StatusEffectReceiverComponent (`0xF23ABD79`) | |

### OrbitalAbilityComponentData  (`generated_entities.dl_bin`, stride 1768 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 64 | ComponentIndexData (`0xFCDFC705`) | |
| 64 | 1704 | OrbitalAbilityComponent (`0xAAFCF4CE`) | |

### DrownableComponentData  (`generated_entities.dl_bin`, stride 5856 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 1952 | ComponentIndexData (`0xFCDFC705`) | |
| 1952 | 3904 | DrownableComponent (`0x14DC6EB1`) | |

### RotationComponentData  (`generated_entities.dl_bin`, stride 78968 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 7232 | ComponentIndexData (`0xFCDFC705`) | |
| 7232 | 71732 | RotationComponent (`0x97646EE3`) | |

### LocomotionComponentData  (`generated_entities.dl_bin`, stride 964592 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 6592 | ComponentIndexData (`0xFCDFC705`) | |
| 6592 | 957996 | LocomotionComponent (`0x97313C56`) | |

### FakeTankVehicleComponentData  (`generated_entities.dl_bin`, stride 224 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 160 | ComponentIndexData (`0xFCDFC705`) | |
| 160 | 60 | FakeTankVehicleComponent (`0x1143C438`) | |

### VehicleLocomotionComponentData  (`generated_entities.dl_bin`, stride 360 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 192 | ComponentIndexData (`0xFCDFC705`) | |
| 192 | 168 | VehicleLocomotionComponent (`0xB18C54B6`) | |

### SprayWeaponComponentData  (`generated_entities.dl_bin`, stride 6112 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 736 | ComponentIndexData (`0xFCDFC705`) | |
| 736 | 5376 | SprayWeaponComponent (`0x516D8AEC`) | |

### 0x1DDF9A2D  (`generated_entities.dl_bin`, stride 64 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 32 | ComponentIndexData (`0xFCDFC705`) | |
| 32 | 32 | IlluminateAttackShipComponent (`0x1626A873`) | |

### VehicleTracksComponentData  (`generated_entities.dl_bin`, stride 3912 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 96 | ComponentIndexData (`0xFCDFC705`) | |
| 96 | 3816 | VehicleTracksComponent (`0x66AC907B`) | |

### MotionComponentData  (`generated_entities.dl_bin`, stride 22848 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 7616 | ComponentIndexData (`0xFCDFC705`) | |
| 7616 | 15232 | MotionComponent (`0xC219DF29`) | |

### EagleComponentData  (`generated_entities.dl_bin`, stride 4384 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 352 | ComponentIndexData (`0xFCDFC705`) | |
| 352 | 4032 | EagleComponent (`0x65EB85D1`) | |

### ProjectileWeaponComponentData  (`generated_entities.dl_bin`, stride 180760 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8896 | ComponentIndexData (`0xFCDFC705`) | |
| 8896 | 171864 | ProjectileWeaponComponent (`0x2290C42E`) | |

### TargetAimConstraintComponentData  (`generated_entities.dl_bin`, stride 31144 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 7328 | ComponentIndexData (`0xFCDFC705`) | |
| 7328 | 23816 | TargetAimConstraintComponent (`0x1700FA36`) | |

### WeaponLaserComponentData  (`generated_entities.dl_bin`, stride 560 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 320 | ComponentIndexData (`0xFCDFC705`) | |
| 320 | 240 | WeaponLaserComponent (`0x896AE274`) | |

### ComponentEntityDeltaStorage  (`generated_entity_deltas.dl_bin`, stride 80 B, rows 4,403)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | EntityDeltaTypeData (`0x4AEE4D43`) | |
| 16 | 16 | EntityDeltaSettings (`0x65984B18`) | |
| 32 | 16 | ComponentDeltaSettings (`0x9A66FB2E`) | |
| 48 | 16 | ComponentModificationDelta (`0x5D407DF3`) | |
| 64 | 16 | 0x00000000 (`0x00000000`) | |

### EnvironmentSettings  (`generated_environment_settings.dl_bin`, stride 576 B, rows 17)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | PlanetType (`0x29EED886`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 8 | 0x00000000 (`0x00000000`) | |
| 48 | 8 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |
| 64 | 8 | 0x00000000 (`0x00000000`) | |
| 72 | 8 | 0x00000000 (`0x00000000`) | |
| 80 | 12 | CApiVector3 (`0x85B82A43`) | |
| 92 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 12 | CApiVector3 (`0x85B82A43`) | |
| 108 | 12 | CApiVector3 (`0x85B82A43`) | |
| 120 | 12 | CApiVector3 (`0x85B82A43`) | |
| 136 | 8 | 0x00000000 (`0x00000000`) | |
| 144 | 360 | LevelGenerationPathSettings (`0x6D91F262`) | |
| 504 | 16 | 0x00000000 (`0x00000000`) | |
| 520 | 4 | 0x00000000 (`0x00000000`) | |
| 528 | 8 | 0x00000000 (`0x00000000`) | |
| 536 | 8 | 0x00000000 (`0x00000000`) | |
| 544 | 4 | 0x00000000 (`0x00000000`) | |
| 548 | 4 | 0x00000000 (`0x00000000`) | |
| 552 | 4 | 0x00000000 (`0x00000000`) | |
| 556 | 4 | 0x00000000 (`0x00000000`) | |
| 560 | 8 | 0x00000000 (`0x00000000`) | |
| 568 | 4 | 0x00000000 (`0x00000000`) | |

### ExplosionInfo  (`generated_explosion_settings.dl_bin`, stride 152 B, rows 424)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | ExplosionType (`0x11BEEE03`) | |
| 4 | 4 | DamageInfoType (`0x39D2F78D`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 1 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 16 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 68 | 1 | TerrainDeformationType (`0xC801688F`) | |
| 72 | 4 | SurfaceImpactType (`0xCF328969`) | |
| 76 | 4 | HitEffectDamageType (`0xB43002D3`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | ProjectileType (`0xA2B5F333`) | |
| 88 | 1 | NoiseTemplate (`0x39117D3A`) | |
| 92 | 4 | WindEffectTemplate (`0x8436CA1B`) | |
| 96 | 4 | FireTemplate (`0x1ABF81A2`) | |
| 100 | 4 | StatusEffectTemplateType (`0x375DAB6F`) | |
| 104 | 4 | 0x00000000 (`0x00000000`) | |
| 108 | 4 | 0x00000000 (`0x00000000`) | |
| 112 | 4 | 0x00000000 (`0x00000000`) | |
| 116 | 1 | 0x00000000 (`0x00000000`) | |
| 116 | 1 | 0x00000000 (`0x00000000`) | |
| 116 | 1 | 0x00000000 (`0x00000000`) | |
| 116 | 1 | 0x00000000 (`0x00000000`) | |
| 116 | 1 | 0x00000000 (`0x00000000`) | |
| 116 | 1 | 0x00000000 (`0x00000000`) | |
| 120 | 4 | ArcType (`0xA064A858`) | |
| 124 | 1 | 0x00000000 (`0x00000000`) | |
| 124 | 1 | 0x00000000 (`0x00000000`) | |
| 128 | 4 | 0x00000000 (`0x00000000`) | |
| 132 | 1 | 0x00000000 (`0x00000000`) | |
| 132 | 1 | 0x00000000 (`0x00000000`) | |
| 136 | 4 | 0x00000000 (`0x00000000`) | |
| 140 | 1 | 0x00000000 (`0x00000000`) | |
| 140 | 1 | 0x00000000 (`0x00000000`) | |
| 144 | 4 | 0x22C3CE6D (`0x22C3CE6D`) | |

### FontLookup  (`generated_font_lookup.dl_bin`, stride 24 B, rows 19)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | FontLookupEntry (`0x0AF4AC23`) | |

### FontSettings  (`generated_font_settings.dl_bin`, stride 112 B, rows 50)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 16 | 0x00000000 (`0x00000000`) | |
| 48 | 16 | 0x00000000 (`0x00000000`) | |
| 64 | 16 | UiFontSettingsEntry (`0xAB967758`) | |
| 80 | 16 | UiHudFontStyleEntry (`0x7E330F19`) | |
| 96 | 16 | UiMenuFontStyleEntry (`0xA50E2E2D`) | |

### 0xF8F9EC3E  (`generated_galactic_presence_settings.dl_bin`, stride 1000 B, rows 137)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 1 | 0x00000000 (`0x00000000`) | |
| 16 | 1 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x8BCB853B (`0x8BCB853B`) | |
| 24 | 1 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | RaceType (`0x41DCECBD`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 8 | 0x00000000 (`0x00000000`) | |
| 48 | 1 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 68 | 4 | 0x1C8FF028 (`0x1C8FF028`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 1 | 0x00000000 (`0x00000000`) | |
| 76 | 1 | 0x00000000 (`0x00000000`) | |
| 76 | 1 | 0x00000000 (`0x00000000`) | |
| 80 | 16 | VoTag (`0x0E5176C1`) | |
| 96 | 16 | OperationTag (`0xA73A9FED`) | |
| 112 | 4 | 0x735440CC (`0x735440CC`) | |
| 120 | 8 | 0x00000000 (`0x00000000`) | |
| 128 | 4 | 0x00000000 (`0x00000000`) | |
| 136 | 8 | 0x00000000 (`0x00000000`) | |
| 144 | 8 | 0x00000000 (`0x00000000`) | |
| 152 | 4 | 0xCBDB4E2A (`0xCBDB4E2A`) | |
| 156 | 12 | CApiVector3 (`0x85B82A43`) | |
| 168 | 1 | 0x00000000 (`0x00000000`) | |
| 172 | 4 | 0x00000000 (`0x00000000`) | |
| 176 | 8 | 0x00000000 (`0x00000000`) | |
| 184 | 1 | 0x00000000 (`0x00000000`) | |
| 184 | 1 | 0x00000000 (`0x00000000`) | |
| 188 | 4 | 0x00000000 (`0x00000000`) | |
| 192 | 8 | 0x00000000 (`0x00000000`) | |
| 200 | 4 | 0x00000000 (`0x00000000`) | |
| 204 | 4 | 0x00000000 (`0x00000000`) | |
| 208 | 16 | MaterialVariableSetting (`0x66AC0E33`) | |
| 224 | 4 | 0x68F0ABB4 (`0x68F0ABB4`) | |
| 228 | 4 | 0x00000000 (`0x00000000`) | |
| 232 | 4 | 0x00000000 (`0x00000000`) | |
| 240 | 16 | ResourceOverride (`0xB950E768`) | |
| 256 | 4 | 0x00000000 (`0x00000000`) | |
| 260 | 4 | 0x00000000 (`0x00000000`) | |
| 264 | 4 | 0x00000000 (`0x00000000`) | |
| 268 | 4 | 0x4EA41426 (`0x4EA41426`) | |
| 272 | 1 | 0x00000000 (`0x00000000`) | |
| 276 | 4 | PlanetSelectableType (`0x4E8E449A`) | |
| 280 | 16 | DistantWarEffectPoolType (`0x744AABCA`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 300 | 12 | CApiVector3 (`0x85B82A43`) | |
| 312 | 4 | 0x00000000 (`0x00000000`) | |
| 316 | 1 | 0x00000000 (`0x00000000`) | |
| 320 | 4 | 0x00000000 (`0x00000000`) | |
| 324 | 4 | 0x00000000 (`0x00000000`) | |
| 328 | 1 | 0x00000000 (`0x00000000`) | |
| 332 | 12 | CApiVector3 (`0x85B82A43`) | |
| 344 | 1 | 0x00000000 (`0x00000000`) | |
| 348 | 12 | CApiVector3 (`0x85B82A43`) | |
| 360 | 12 | CApiVector3 (`0x85B82A43`) | |
| 372 | 12 | CApiVector3 (`0x85B82A43`) | |
| 384 | 16 | MaterialVariableSetting (`0x66AC0E33`) | |
| 400 | 8 | 0x00000000 (`0x00000000`) | |
| 408 | 8 | 0x00000000 (`0x00000000`) | |
| 416 | 8 | 0x00000000 (`0x00000000`) | |
| 424 | 8 | 0x00000000 (`0x00000000`) | |
| 432 | 4 | 0x00000000 (`0x00000000`) | |
| 440 | 16 | WeatherType (`0x40929612`) | |
| 456 | 8 | 0x00000000 (`0x00000000`) | |
| 464 | 16 | 0x5C708081 (`0x5C708081`) | |
| 480 | 16 | 0x00000000 (`0x00000000`) | |
| 496 | 8 | 0x00000000 (`0x00000000`) | |
| 504 | 16 | 0x00000000 (`0x00000000`) | |
| 520 | 8 | 0x00000000 (`0x00000000`) | |
| 528 | 16 | 0x00000000 (`0x00000000`) | |
| 544 | 1 | 0x00000000 (`0x00000000`) | |
| 548 | 4 | 0x00000000 (`0x00000000`) | |
| 552 | 12 | CApiVector3 (`0x85B82A43`) | |
| 564 | 12 | CApiVector3 (`0x85B82A43`) | |
| 576 | 1 | 0x00000000 (`0x00000000`) | |
| 580 | 4 | 0x00000000 (`0x00000000`) | |
| 584 | 4 | 0x00000000 (`0x00000000`) | |
| 588 | 4 | 0x00000000 (`0x00000000`) | |
| 592 | 4 | 0x00000000 (`0x00000000`) | |
| 596 | 4 | 0x00000000 (`0x00000000`) | |
| 600 | 4 | 0x00000000 (`0x00000000`) | |
| 604 | 4 | 0x00000000 (`0x00000000`) | |
| 608 | 4 | 0x00000000 (`0x00000000`) | |
| 612 | 4 | 0x00000000 (`0x00000000`) | |
| 616 | 16 | 0x00000000 (`0x00000000`) | |
| 632 | 1 | 0x00000000 (`0x00000000`) | |
| 640 | 16 | SubRegionSettingsOverride (`0x5B4DABFF`) | |
| 656 | 16 | 0x645E23F8 (`0x645E23F8`) | |
| 672 | 16 | 0xB1185137 (`0xB1185137`) | |
| 688 | 16 | 0x00000000 (`0x00000000`) | |
| 704 | 16 | 0x00000000 (`0x00000000`) | |
| 720 | 16 | 0x00000000 (`0x00000000`) | |
| 736 | 4 | 0x00000000 (`0x00000000`) | |
| 740 | 4 | 0x00000000 (`0x00000000`) | |
| 744 | 8 | 0x00000000 (`0x00000000`) | |
| 752 | 104 | 0x8BD8F3DE (`0x8BD8F3DE`) | |
| 856 | 60 | 0x69413FE8 (`0x69413FE8`) | |
| 920 | 8 | 0x00000000 (`0x00000000`) | |
| 928 | 8 | 0x00000000 (`0x00000000`) | |
| 936 | 8 | 0x00000000 (`0x00000000`) | |
| 944 | 8 | 0x00000000 (`0x00000000`) | |
| 952 | 8 | 0x00000000 (`0x00000000`) | |
| 960 | 8 | 0x00000000 (`0x00000000`) | |
| 968 | 8 | 0x00000000 (`0x00000000`) | |
| 976 | 4 | 0x00000000 (`0x00000000`) | |
| 984 | 16 | 0x9B4E7037 (`0x9B4E7037`) | |

### LevelGenerationSettings  (`generated_generation_settings.dl_bin`, stride 464 B, rows 22)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | 0x00000000 (`0x00000000`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 68 | 4 | 0x00000000 (`0x00000000`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 8 | 0x00000000 (`0x00000000`) | |
| 96 | 1 | 0x00000000 (`0x00000000`) | |
| 104 | 40 | ExplorationSettings (`0xDE9425C6`) | |
| 144 | 16 | CacheLootTable (`0xCFE4197A`) | |
| 160 | 96 | LocationFlagSettings (`0x0E20FFC4`) | |
| 256 | 96 | RegionLightingSettings (`0x3F75D8EB`) | |
| 352 | 16 | CityLayoutTemplate (`0xCAEA9E93`) | |
| 368 | 16 | 0xB1814DA3 (`0xB1814DA3`) | |
| 384 | 16 | PlanetAffiliationTemplate (`0x9A26D6E6`) | |
| 400 | 16 | CityLayoutTemplate (`0xCAEA9E93`) | |
| 416 | 16 | 0x29A36DB0 (`0x29A36DB0`) | |
| 432 | 16 | 0x8D0A3882 (`0x8D0A3882`) | |
| 448 | 16 | 0xED8AA652 (`0xED8AA652`) | |

### HitEffectInfo  (`generated_hit_effect_settings.dl_bin`, stride 48 B, rows 1,512)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | HitEffectDamageType (`0xB43002D3`) | |
| 4 | 4 | HitEffectReceiverType (`0x091B24E9`) | |
| 8 | 4 | HitEffectLevel (`0x796C944A`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |

### LanguageListEntry  (`generated_language_settings.dl_bin`, stride 208 B, rows 15)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 1 | 0x00000000 (`0x00000000`) | |
| 46 | 2 | 0x00000000 (`0x00000000`) | |
| 48 | 8 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |
| 64 | 64 | LanguageLocaleInfo (`0x59CF9D40`) | |
| 128 | 72 | LanguageListSettingsInfo (`0xCC6AA6FD`) | |
| 200 | 8 | 0x00000000 (`0x00000000`) | |

### PackageLayerTagIndirection  (`generated_layer_package_indirection_settings.dl_bin`, stride 16 B, rows 5)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | PackageLayerTagIndirectionPair (`0xA073D889`) | |

### LevelGenerationLocation  (`generated_location_groups.dl_bin`, stride 56 B, rows 7,080)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 1 | LocationFlags (`0x673D8D46`) | |
| 40 | 16 | LevelGenerationLocationGroup (`0xBBFEA78A`) | |

### Modifier  (`generated_modifier_settings.dl_bin`, stride 24 B, rows 52)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 1 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | ModifierGroup (`0x05238A1C`) | |

### 0x80EB67CF  (`generated_planet_color_set_settings.dl_bin`, stride 64 B, rows 30)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 12 | CApiVector3 (`0x85B82A43`) | |
| 16 | 12 | CApiVector3 (`0x85B82A43`) | |
| 28 | 12 | CApiVector3 (`0x85B82A43`) | |
| 40 | 12 | CApiVector3 (`0x85B82A43`) | |
| 52 | 12 | CApiVector3 (`0x85B82A43`) | |

### LevelGenerationPlanetData  (`generated_planet_data.dl_bin`, stride 624 B, rows 438)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 8 | 0x00000000 (`0x00000000`) | |
| 48 | 8 | 0x00000000 (`0x00000000`) | |
| 56 | 16 | OperationTag (`0xA73A9FED`) | |
| 72 | 16 | ResourceOverride (`0xB950E768`) | |
| 88 | 8 | 0x00000000 (`0x00000000`) | |
| 96 | 40 | LevelGenerationRegion (`0x312C4148`) | |
| 136 | 40 | LevelGenerationRegion (`0x312C4148`) | |
| 176 | 112 | LevelGenerationPaletteGroup (`0xC0C75C00`) | |
| 288 | 112 | LevelGenerationPaletteGroup (`0xC0C75C00`) | |
| 400 | 8 | 0x00000000 (`0x00000000`) | |
| 408 | 8 | 0x00000000 (`0x00000000`) | |
| 416 | 1 | 0x12FDF387 (`0x12FDF387`) | |
| 424 | 16 | 0x00000000 (`0x00000000`) | |
| 440 | 4 | PlanetType (`0x29EED886`) | |
| 444 | 4 | 0x00000000 (`0x00000000`) | |
| 448 | 16 | NatureLocationTag (`0x56635484`) | |
| 464 | 4 | 0x00000000 (`0x00000000`) | |
| 472 | 8 | 0x00000000 (`0x00000000`) | |
| 480 | 8 | 0x00000000 (`0x00000000`) | |
| 488 | 8 | 0x00000000 (`0x00000000`) | |
| 496 | 8 | 0x00000000 (`0x00000000`) | |
| 504 | 8 | 0x00000000 (`0x00000000`) | |
| 512 | 16 | 0x00000000 (`0x00000000`) | |
| 528 | 16 | SampleType (`0xF104D1C4`) | |
| 544 | 4 | 0x00000000 (`0x00000000`) | |
| 548 | 4 | 0x00000000 (`0x00000000`) | |
| 552 | 8 | 0x00000000 (`0x00000000`) | |
| 560 | 8 | 0x00000000 (`0x00000000`) | |
| 568 | 16 | 0x62FECBF9 (`0x62FECBF9`) | |
| 584 | 8 | 0x00000000 (`0x00000000`) | |
| 592 | 8 | 0x00000000 (`0x00000000`) | |
| 600 | 8 | 0x00000000 (`0x00000000`) | |
| 608 | 8 | 0x00000000 (`0x00000000`) | |
| 616 | 4 | 0x00000000 (`0x00000000`) | |

### PlanetOverrides  (`generated_planet_override_settings.dl_bin`, stride 40 B, rows 44)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 16 | ResourceOverride (`0xB950E768`) | |

### PlanetRegionSettings  (`generated_planet_region_settings.dl_bin`, stride 128 B, rows 369)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | RaceType (`0x41DCECBD`) | |
| 32 | 16 | OperationTag (`0xA73A9FED`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | OperationType (`0x8E91A5D3`) | |
| 64 | 16 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | 0xA1CDD14D (`0xA1CDD14D`) | |
| 88 | 16 | 0x00000000 (`0x00000000`) | |
| 104 | 16 | 0xB1185137 (`0xB1185137`) | |
| 120 | 4 | 0x00000000 (`0x00000000`) | |

### SavedPlanetTerritoryGraph  (`generated_planet_territory_graphs.dl_bin`, stride 56 B, rows 28,105)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | TerritoryCell (`0x402ADA74`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 16 | TerritoryEdge (`0x402BEE49`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |

### SolarSystemObjectType  (`generated_planet_types_settings.dl_bin`, stride 24 B, rows 88)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | SolarSystemObjectTypeSettings (`0x0FD71230`) | |

### PolicySettings  (`generated_policy_settings.dl_bin`, stride 32 B, rows 14)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | PolicySetting (`0x001242EE`) | |
| 16 | 16 | PolicyUnlockedWeaponList (`0x2702C92B`) | |

### ProjectileInfo  (`generated_projectile_settings.dl_bin`, stride 272 B, rows 355)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | ProjectileType (`0xA2B5F333`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | DamageInfoType (`0x39D2F78D`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 72 | 8 | 0x00000000 (`0x00000000`) | |
| 80 | 8 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 8 | 0x00000000 (`0x00000000`) | |
| 104 | 8 | 0x00000000 (`0x00000000`) | |
| 112 | 8 | 0x00000000 (`0x00000000`) | |
| 120 | 8 | 0x00000000 (`0x00000000`) | |
| 128 | 8 | 0x00000000 (`0x00000000`) | |
| 136 | 4 | 0x00000000 (`0x00000000`) | |
| 140 | 1 | 0x00000000 (`0x00000000`) | |
| 144 | 4 | ExplosionType (`0x11BEEE03`) | |
| 148 | 4 | 0x00000000 (`0x00000000`) | |
| 152 | 4 | 0x00000000 (`0x00000000`) | |
| 156 | 4 | ExplosionType (`0x11BEEE03`) | |
| 160 | 4 | 0x00000000 (`0x00000000`) | |
| 164 | 4 | 0x00000000 (`0x00000000`) | |
| 168 | 4 | 0x00000000 (`0x00000000`) | |
| 172 | 4 | SurfaceImpactType (`0xCF328969`) | |
| 176 | 4 | SurfaceImpactType (`0xCF328969`) | |
| 180 | 4 | 0x00000000 (`0x00000000`) | |
| 184 | 4 | 0x00000000 (`0x00000000`) | |
| 188 | 4 | 0x00000000 (`0x00000000`) | |
| 192 | 4 | 0x00000000 (`0x00000000`) | |
| 196 | 4 | 0x00000000 (`0x00000000`) | |
| 200 | 4 | 0x00000000 (`0x00000000`) | |
| 204 | 4 | 0x00000000 (`0x00000000`) | |
| 208 | 4 | 0x00000000 (`0x00000000`) | |
| 212 | 4 | 0x00000000 (`0x00000000`) | |
| 216 | 4 | 0x00000000 (`0x00000000`) | |
| 220 | 4 | 0x00000000 (`0x00000000`) | |
| 224 | 4 | 0x00000000 (`0x00000000`) | |
| 228 | 1 | 0x00000000 (`0x00000000`) | |
| 232 | 4 | ProjectileStatusEffectVolumeTemplate (`0xDCC38AB6`) | |
| 236 | 4 | HitEffectDamageType (`0xB43002D3`) | |
| 240 | 4 | FireTemplate (`0x1ABF81A2`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 2 | 0x00000000 (`0x00000000`) | |
| 248 | 4 | RaycastTemplate (`0xD7658573`) | |
| 252 | 4 | 0x00000000 (`0x00000000`) | |
| 256 | 1 | 0x00000000 (`0x00000000`) | |
| 256 | 1 | 0x00000000 (`0x00000000`) | |
| 260 | 12 | CApiVector3 (`0x85B82A43`) | |

### GenerationRegionSettings  (`generated_region_settings.dl_bin`, stride 3272 B, rows 74)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | EnvironmentalEffectType (`0x66D2B571`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | 0x00000000 (`0x00000000`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 68 | 4 | 0x00000000 (`0x00000000`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 1 | 0x00000000 (`0x00000000`) | |
| 88 | 1 | 0x00000000 (`0x00000000`) | |
| 92 | 36 | 0x00000000 (`0x00000000`) | |
| 128 | 224 | LevelGenerationSubRegionSpecialSettings (`0xAD5037C4`) | |
| 352 | 216 | RouteSettingReference (`0xD856775C`) | |
| 568 | 1088 | SubRegionSettings (`0xB6A8757F`) | |
| 1656 | 1 | CityLayout (`0x33FEE6B7`) | |
| 1660 | 4 | 0x00000000 (`0x00000000`) | |
| 1664 | 4 | 0x00000000 (`0x00000000`) | |
| 1668 | 524 | 0x4D699EB3 (`0x4D699EB3`) | |
| 2192 | 4 | 0x00000000 (`0x00000000`) | |
| 2196 | 512 | 0xC4158B6A (`0xC4158B6A`) | |
| 2708 | 1 | LevelGenerationMode (`0x07527AC9`) | |
| 2709 | 4 | RegionFlag (`0x2223CDFE`) | |
| 2716 | 24 | 0x00000000 (`0x00000000`) | |
| 2740 | 512 | SubRegionSettingsOverride (`0x5B4DABFF`) | |
| 3252 | 4 | 0x00000000 (`0x00000000`) | |
| 3256 | 1 | 0x00000000 (`0x00000000`) | |
| 3257 | 1 | 0x00000000 (`0x00000000`) | |
| 3258 | 1 | 0x00000000 (`0x00000000`) | |
| 3260 | 4 | 0x00000000 (`0x00000000`) | |
| 3264 | 4 | 0x00000000 (`0x00000000`) | |
| 3268 | 4 | 0x00000000 (`0x00000000`) | |

### GenerationRegionGroup  (`generated_region_settings.dl_bin`, stride 64 B, rows 236)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 12 | CApiVector3 (`0x85B82A43`) | |
| 48 | 16 | GenerationRegionVariantList (`0x961C02A1`) | |

### RouteSettings  (`generated_route_settings.dl_bin`, stride 112 B, rows 3)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 104 | StampGroup (`0xA38290F2`) | |

### LevelGenerationSatelliteGroup  (`generated_satellite_groups.dl_bin`, stride 24 B, rows 3,429)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | LevelGenerationSatellite (`0x839EB6AB`) | |

### ScenarioSettings  (`generated_scenario_settings.dl_bin`, stride 48 B, rows 149)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 16 | ScenarioSetting (`0x41CF0ED2`) | |

### SkySettings  (`generated_sky_settings.dl_bin`, stride 24 B, rows 480)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | SkySetting (`0xC96AEF75`) | |

### SolarSystemSettings  (`generated_solar_system_settings.dl_bin`, stride 24 B, rows 3,822)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 16 | SolarSystemSetting (`0xB5F966E4`) | |

### StampHashEntry  (`generated_stamp_settings.dl_bin`, stride 112 B, rows 4,096)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 104 | Stamp (`0x0E1E2405`) | |

### StatusEffectInfo  (`generated_status_effect_settings.dl_bin`, stride 160 B, rows 73)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | StatusEffectType (`0x525E8B93`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | StatusEffectShaderVariablePreset (`0x89FA9121`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | DamageInfoType (`0x39D2F78D`) | |
| 48 | 1 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 68 | 4 | 0x00000000 (`0x00000000`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | 0x00000000 (`0x00000000`) | |
| 92 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 4 | 0x00000000 (`0x00000000`) | |
| 100 | 4 | 0x00000000 (`0x00000000`) | |
| 104 | 1 | 0x00000000 (`0x00000000`) | |
| 104 | 1 | 0x00000000 (`0x00000000`) | |
| 104 | 1 | 0x00000000 (`0x00000000`) | |
| 104 | 1 | 0x00000000 (`0x00000000`) | |
| 112 | 16 | 0x17B9083A (`0x17B9083A`) | |
| 128 | 4 | 0x00000000 (`0x00000000`) | |
| 132 | 4 | 0x00000000 (`0x00000000`) | |
| 136 | 1 | 0x00000000 (`0x00000000`) | |
| 140 | 4 | 0x00000000 (`0x00000000`) | |
| 144 | 16 | 0x9DDD1BE2 (`0x9DDD1BE2`) | |

### StatusEffectTemplate  (`generated_status_effect_settings.dl_bin`, stride 40 B, rows 29)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | StatusEffectTemplateType (`0x375DAB6F`) | |
| 4 | 32 | StatusEffectContinuousEffect (`0x48CEF575`) | |
| 36 | 1 | 0x00000000 (`0x00000000`) | |

### StratagemInfo  (`generated_stratagem_settings.dl_bin`, stride 400 B, rows 153)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | StratagemType (`0x7BDC408A`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | StratagemCategoryType (`0xCBDB3EC8`) | |
| 64 | 16 | StratagemButtonDirection (`0x561A8A65`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | 0x00000000 (`0x00000000`) | |
| 92 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 4 | 0x00000000 (`0x00000000`) | |
| 100 | 4 | 0x00000000 (`0x00000000`) | |
| 104 | 4 | 0x00000000 (`0x00000000`) | |
| 108 | 4 | 0x00000000 (`0x00000000`) | |
| 112 | 4 | StratagemOriginType (`0xE43FFD52`) | |
| 116 | 4 | StratagemCallInType (`0xF28148FD`) | |
| 120 | 2 | StratagemCallInLogic (`0x4216A409`) | |
| 124 | 4 | StratagemObjectiveDropRequirement (`0x4D883209`) | |
| 128 | 1 | 0x00000000 (`0x00000000`) | |
| 128 | 1 | 0x00000000 (`0x00000000`) | |
| 136 | 8 | 0x00000000 (`0x00000000`) | |
| 144 | 1 | 0x00000000 (`0x00000000`) | |
| 148 | 4 | StratagemCooldownType (`0x783CA8AF`) | |
| 152 | 16 | 0x00000000 (`0x00000000`) | |
| 168 | 8 | 0x00000000 (`0x00000000`) | |
| 176 | 8 | 0x00000000 (`0x00000000`) | |
| 184 | 4 | StratagemHUDType (`0x7A6E836B`) | |
| 188 | 4 | 0x00000000 (`0x00000000`) | |
| 192 | 1 | 0x00000000 (`0x00000000`) | |
| 196 | 4 | StratagemType (`0x7BDC408A`) | |
| 200 | 4 | StratagemType (`0x7BDC408A`) | |
| 204 | 4 | 0x00000000 (`0x00000000`) | |
| 208 | 1 | 0x00000000 (`0x00000000`) | |
| 212 | 4 | StratagemBeaconColor (`0xE9BD1A8F`) | |
| 216 | 1 | 0x00000000 (`0x00000000`) | |
| 220 | 4 | 0x00000000 (`0x00000000`) | |
| 224 | 4 | 0x00000000 (`0x00000000`) | |
| 228 | 4 | 0x00000000 (`0x00000000`) | |
| 232 | 4 | 0x00000000 (`0x00000000`) | |
| 240 | 8 | 0x00000000 (`0x00000000`) | |
| 248 | 4 | 0x00000000 (`0x00000000`) | |
| 252 | 4 | 0x00000000 (`0x00000000`) | |
| 256 | 1 | 0x00000000 (`0x00000000`) | |
| 260 | 4 | StratagemInfoFlag (`0x8A0F47AE`) | |
| 264 | 4 | 0x00000000 (`0x00000000`) | |
| 268 | 4 | StratagemType (`0x7BDC408A`) | |
| 272 | 1 | StratagemCustomizationTypeInfo (`0xC53E09EF`) | |
| 280 | 16 | 0xB6CAFF2E (`0xB6CAFF2E`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 296 | 1 | 0x00000000 (`0x00000000`) | |
| 300 | 4 | 0x00000000 (`0x00000000`) | |
| 304 | 16 | CApiVector3 (`0x85B82A43`) | |
| 320 | 16 | 0x00000000 (`0x00000000`) | |
| 336 | 16 | 0x00000000 (`0x00000000`) | |
| 352 | 16 | 0x00000000 (`0x00000000`) | |
| 368 | 1 | 0x00000000 (`0x00000000`) | |
| 368 | 1 | 0x00000000 (`0x00000000`) | |
| 372 | 4 | UnitCustomizationCollectionType (`0x57D3AD67`) | |
| 376 | 16 | 0xB24E0C4B (`0xB24E0C4B`) | |
| 392 | 4 | 0x6011FA2B (`0x6011FA2B`) | |

### StratagemCustomizationInfo  (`generated_stratagem_upgrade_settings.dl_bin`, stride 64 B, rows 1)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | StratagemCustomizationType (`0x6F107CC3`) | |
| 36 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 8 | 0x00000000 (`0x00000000`) | |

### SurfaceEffectInfo  (`generated_surface_effect_settings.dl_bin`, stride 40 B, rows 7,644)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | SurfaceMaterialType (`0x725893BA`) | |
| 4 | 4 | SurfaceImpactType (`0xCF328969`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 8 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 1 | 0x00000000 (`0x00000000`) | |
| 32 | 1 | 0x00000000 (`0x00000000`) | |

### UnitCustomizationSettings  (`generated_unit_customization_settings.dl_bin`, stride 80 B, rows 339)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 4 | UnitCustomizationCollectionType (`0x57D3AD67`) | |
| 8 | 4 | UnitCustomizationCollectionType (`0x57D3AD67`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 8 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | UnitCustomizationCollectionCategoryType (`0xBDEC38A5`) | |
| 40 | 16 | UnitCustomizationSetting (`0x1C341B57`) | |
| 56 | 12 | CApiVector3 (`0x85B82A43`) | |
| 68 | 12 | CApiVector3 (`0x85B82A43`) | |

### UnitEffectSetting  (`generated_unit_effect_settings.dl_bin`, stride 112 B, rows 408)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | UnitEffectOrphanStrategy (`0x322F2168`) | |
| 16 | 16 | EffectSetting (`0x10CEE58B`) | |
| 32 | 16 | UnitSound (`0xCB0D97E9`) | |
| 48 | 16 | UnitNodeScale (`0x49D0074E`) | |
| 64 | 16 | UnitSound (`0xCB0D97E9`) | |
| 80 | 16 | UnitSound (`0xCB0D97E9`) | |
| 96 | 16 | WeightedEffectSetting (`0x2F881EFC`) | |

### VideoFlowSettings  (`generated_video_flow_settings.dl_bin`, stride 32 B, rows 63)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | VideoSegment (`0x5F6F112A`) | |
| 16 | 16 | VideoSegment (`0x5F6F112A`) | |

### VideoUIElement  (`generated_video_ui_settings.dl_bin`, stride 120 B, rows 9)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 4 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | FontType (`0x7F2E7339`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 12 | CApiVector3 (`0x85B82A43`) | |
| 28 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 4 | 0x00000000 (`0x00000000`) | |
| 40 | 8 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | 0x00000000 (`0x00000000`) | |
| 64 | 4 | 0x00000000 (`0x00000000`) | |
| 68 | 4 | 0x00000000 (`0x00000000`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | 0x00000000 (`0x00000000`) | |
| 92 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 4 | 0x00000000 (`0x00000000`) | |
| 100 | 4 | 0x00000000 (`0x00000000`) | |
| 104 | 4 | 0x00000000 (`0x00000000`) | |
| 108 | 4 | 0x00000000 (`0x00000000`) | |
| 112 | 4 | 0x00000000 (`0x00000000`) | |
| 116 | 4 | 0x00000000 (`0x00000000`) | |

### WeaponCustomizableItem  (`generated_weapon_customization_settings.dl_bin`, stride 88 B, rows 252)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 4 | 0x00000000 (`0x00000000`) | |
| 12 | 4 | 0x00000000 (`0x00000000`) | |
| 16 | 4 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | 0x00000000 (`0x00000000`) | |
| 24 | 4 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 8 | 0x00000000 (`0x00000000`) | |
| 48 | 16 | WeaponCustomizationSlot (`0x62AB45E5`) | |
| 64 | 16 | CApiVector3 (`0x85B82A43`) | |
| 80 | 4 | WeaponCustomizationSortGroups (`0x9D292BCB`) | |

### WeatherColorSet  (`generated_weather_color_set_settings.dl_bin`, stride 196 B, rows 132)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 4 | 0x00000000 (`0x00000000`) | |
| 4 | 12 | CApiVector3 (`0x85B82A43`) | |
| 16 | 12 | CApiVector3 (`0x85B82A43`) | |
| 28 | 12 | CApiVector3 (`0x85B82A43`) | |
| 40 | 12 | CApiVector3 (`0x85B82A43`) | |
| 52 | 12 | CApiVector3 (`0x85B82A43`) | |
| 64 | 12 | CApiVector3 (`0x85B82A43`) | |
| 76 | 12 | CApiVector3 (`0x85B82A43`) | |
| 88 | 12 | CApiVector3 (`0x85B82A43`) | |
| 100 | 12 | CApiVector3 (`0x85B82A43`) | |
| 112 | 12 | CApiVector3 (`0x85B82A43`) | |
| 124 | 12 | CApiVector3 (`0x85B82A43`) | |
| 136 | 12 | CApiVector3 (`0x85B82A43`) | |
| 148 | 12 | CApiVector3 (`0x85B82A43`) | |
| 160 | 12 | CApiVector3 (`0x85B82A43`) | |
| 172 | 12 | CApiVector3 (`0x85B82A43`) | |
| 184 | 12 | CApiVector3 (`0x85B82A43`) | |

### WeatherSettings  (`generated_weather_settings.dl_bin`, stride 648 B, rows 190)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 8 | 0x00000000 (`0x00000000`) | |
| 8 | 8 | 0x00000000 (`0x00000000`) | |
| 16 | 1 | 0x00000000 (`0x00000000`) | |
| 20 | 4 | WeatherType (`0x40929612`) | |
| 24 | 4 | EnvironmentalEffectType (`0x66D2B571`) | |
| 28 | 1 | 0x00000000 (`0x00000000`) | |
| 29 | 1 | 0x00000000 (`0x00000000`) | |
| 32 | 8 | 0x00000000 (`0x00000000`) | |
| 40 | 4 | 0x00000000 (`0x00000000`) | |
| 44 | 4 | 0x00000000 (`0x00000000`) | |
| 48 | 4 | 0x00000000 (`0x00000000`) | |
| 52 | 4 | 0x00000000 (`0x00000000`) | |
| 56 | 4 | 0x00000000 (`0x00000000`) | |
| 60 | 4 | 0x00000000 (`0x00000000`) | |
| 64 | 8 | CApiVector2 (`0x85B82A42`) | |
| 72 | 4 | 0x00000000 (`0x00000000`) | |
| 76 | 4 | 0x00000000 (`0x00000000`) | |
| 80 | 4 | 0x00000000 (`0x00000000`) | |
| 84 | 4 | 0x00000000 (`0x00000000`) | |
| 88 | 4 | 0x00000000 (`0x00000000`) | |
| 96 | 8 | 0x00000000 (`0x00000000`) | |
| 104 | 4 | 0x00000000 (`0x00000000`) | |
| 112 | 8 | 0x00000000 (`0x00000000`) | |
| 120 | 4 | 0x00000000 (`0x00000000`) | |
| 124 | 8 | CApiVector2 (`0x85B82A42`) | |
| 132 | 4 | 0x00000000 (`0x00000000`) | |
| 136 | 4 | 0x00000000 (`0x00000000`) | |
| 140 | 4 | 0x00000000 (`0x00000000`) | |
| 144 | 4 | 0x00000000 (`0x00000000`) | |
| 148 | 4 | 0x00000000 (`0x00000000`) | |
| 152 | 4 | 0x00000000 (`0x00000000`) | |
| 156 | 4 | 0x00000000 (`0x00000000`) | |
| 160 | 4 | 0x00000000 (`0x00000000`) | |
| 164 | 4 | 0x00000000 (`0x00000000`) | |
| 168 | 4 | 0x00000000 (`0x00000000`) | |
| 172 | 4 | 0x00000000 (`0x00000000`) | |
| 176 | 4 | 0x00000000 (`0x00000000`) | |
| 180 | 4 | 0x00000000 (`0x00000000`) | |
| 184 | 4 | 0x00000000 (`0x00000000`) | |
| 188 | 4 | 0x00000000 (`0x00000000`) | |
| 192 | 4 | 0x00000000 (`0x00000000`) | |
| 196 | 4 | 0x00000000 (`0x00000000`) | |
| 200 | 4 | 0x00000000 (`0x00000000`) | |
| 204 | 4 | 0x00000000 (`0x00000000`) | |
| 208 | 4 | 0x00000000 (`0x00000000`) | |
| 212 | 4 | 0x00000000 (`0x00000000`) | |
| 216 | 4 | 0x00000000 (`0x00000000`) | |
| 220 | 4 | 0x00000000 (`0x00000000`) | |
| 224 | 4 | 0x00000000 (`0x00000000`) | |
| 228 | 4 | 0x00000000 (`0x00000000`) | |
| 232 | 4 | 0x00000000 (`0x00000000`) | |
| 236 | 4 | 0x00000000 (`0x00000000`) | |
| 240 | 2 | 0x00000000 (`0x00000000`) | |
| 244 | 4 | 0x00000000 (`0x00000000`) | |
| 248 | 4 | 0x00000000 (`0x00000000`) | |
| 252 | 4 | 0x00000000 (`0x00000000`) | |
| 256 | 4 | 0x00000000 (`0x00000000`) | |
| 260 | 4 | 0x00000000 (`0x00000000`) | |
| 264 | 4 | 0x00000000 (`0x00000000`) | |
| 268 | 4 | 0x00000000 (`0x00000000`) | |
| 272 | 4 | 0x00000000 (`0x00000000`) | |
| 276 | 4 | 0x00000000 (`0x00000000`) | |
| 280 | 4 | 0x00000000 (`0x00000000`) | |
| 284 | 4 | 0x00000000 (`0x00000000`) | |
| 288 | 4 | 0x00000000 (`0x00000000`) | |
| 292 | 4 | 0x00000000 (`0x00000000`) | |
| 296 | 4 | 0x00000000 (`0x00000000`) | |
| 300 | 4 | 0x00000000 (`0x00000000`) | |
| 304 | 4 | 0x00000000 (`0x00000000`) | |
| 308 | 4 | 0x00000000 (`0x00000000`) | |
| 312 | 4 | 0x00000000 (`0x00000000`) | |
| 316 | 4 | 0x00000000 (`0x00000000`) | |
| 320 | 4 | 0x00000000 (`0x00000000`) | |
| 328 | 16 | CameraEffect (`0x66925F96`) | |
| 344 | 16 | DistantWeatherEffects (`0xC7F5CA07`) | |
| 360 | 4 | 0x00000000 (`0x00000000`) | |
| 364 | 8 | CApiVector2 (`0x85B82A42`) | |
| 372 | 12 | CApiVector3 (`0x85B82A43`) | |
| 384 | 4 | 0x00000000 (`0x00000000`) | |
| 388 | 8 | CApiVector2 (`0x85B82A42`) | |
| 396 | 4 | 0x00000000 (`0x00000000`) | |
| 400 | 1 | BanterEventType (`0x8BE10600`) | |
| 404 | 4 | 0x00000000 (`0x00000000`) | |
| 408 | 4 | 0x00000000 (`0x00000000`) | |
| 416 | 16 | 0x34F2F276 (`0x34F2F276`) | |
| 432 | 4 | 0x00000000 (`0x00000000`) | |
| 436 | 4 | 0x00000000 (`0x00000000`) | |
| 440 | 4 | 0x00000000 (`0x00000000`) | |
| 444 | 196 | WeatherColorSet (`0x970B0B5B`) | |
| 640 | 4 | StatusEffectTemplateType (`0x375DAB6F`) | |
| 644 | 4 | DangerWarningType (`0x0E8E1A49`) | |

### ZoneSettings  (`generated_zone_data.dl_bin`, stride 912 B, rows 517)

| offset | size | type | note |
|---:|---:|---|---|
| 0 | 16 | ZoneTag (`0x1EA4DDF8`) | |
| 16 | 16 | StampGroup (`0xA38290F2`) | |
| 32 | 16 | ShaderProperties (`0x64744AC4`) | |
| 48 | 16 | ShaderProperties (`0x64744AC4`) | |
| 64 | 16 | FogVolumeShaderProperties (`0xACB8CCF8`) | |
| 80 | 16 | ShaderProperties (`0x64744AC4`) | |
| 96 | 16 | ShaderProperties (`0x64744AC4`) | |
| 112 | 16 | ShaderProperties (`0x64744AC4`) | |
| 128 | 16 | ShaderProperties (`0x64744AC4`) | |
| 144 | 4 | 0x00000000 (`0x00000000`) | |
| 148 | 12 | CApiVector3 (`0x85B82A43`) | |
| 160 | 1 | MinimapTerrainType (`0xBCAAB042`) | |
| 168 | 8 | 0x00000000 (`0x00000000`) | |
| 176 | 16 | 0x0089AB61 (`0x0089AB61`) | |
| 192 | 16 | CameraEffect (`0x66925F96`) | |
| 208 | 8 | WindNoiseSettings (`0x9F4AC541`) | |
| 216 | 8 | 0x00000000 (`0x00000000`) | |
| 224 | 4 | 0x00000000 (`0x00000000`) | |
| 228 | 4 | 0x00000000 (`0x00000000`) | |
| 232 | 4 | 0x00000000 (`0x00000000`) | |
| 236 | 4 | 0x00000000 (`0x00000000`) | |
| 240 | 16 | 0x00000000 (`0x00000000`) | |
| 256 | 8 | 0x00000000 (`0x00000000`) | |
| 264 | 4 | 0x00000000 (`0x00000000`) | |
| 272 | 24 | QuakeEffectSettings (`0x4105D355`) | |
| 296 | 1 | ZoneMusicType (`0x07F6109F`) | |
| 297 | 1 | BanterEventType (`0x8BE10600`) | |
| 300 | 4 | 0x00000000 (`0x00000000`) | |
| 304 | 40 | MinimapScatterSet (`0xA2B24BAD`) | |
| 344 | 4 | 0x00000000 (`0x00000000`) | |
| 348 | 4 | 0x00000000 (`0x00000000`) | |
| 352 | 4 | 0x00000000 (`0x00000000`) | |
| 356 | 4 | 0x00000000 (`0x00000000`) | |
| 360 | 1 | 0x00000000 (`0x00000000`) | |
| 360 | 1 | 0x00000000 (`0x00000000`) | |
| 360 | 1 | 0x00000000 (`0x00000000`) | |
| 360 | 1 | 0x00000000 (`0x00000000`) | |
| 360 | 1 | 0x00000000 (`0x00000000`) | |
| 360 | 1 | 0x00000000 (`0x00000000`) | |
| 364 | 4 | PatrolSetting (`0x18856870`) | |
| 368 | 4 | 0x00000000 (`0x00000000`) | |
| 372 | 4 | 0x00000000 (`0x00000000`) | |
| 376 | 4 | 0x00000000 (`0x00000000`) | |
| 380 | 4 | 0x00000000 (`0x00000000`) | |
| 384 | 4 | 0x00000000 (`0x00000000`) | |
| 388 | 4 | 0x00000000 (`0x00000000`) | |
| 392 | 4 | 0x00000000 (`0x00000000`) | |
| 396 | 4 | 0x00000000 (`0x00000000`) | |
| 400 | 4 | 0x00000000 (`0x00000000`) | |
| 404 | 4 | 0x00000000 (`0x00000000`) | |
| 408 | 4 | 0x00000000 (`0x00000000`) | |
| 412 | 1 | 0x00000000 (`0x00000000`) | |
| 413 | 1 | 0x00000000 (`0x00000000`) | |
| 416 | 4 | CityPlacementHeuristic (`0xA0714582`) | |
| 420 | 4 | 0xBAC19D46 (`0xBAC19D46`) | |
| 424 | 4 | 0x00000000 (`0x00000000`) | |
| 428 | 4 | 0x00000000 (`0x00000000`) | |
| 432 | 24 | CApiVector2 (`0x85B82A42`) | |
| 456 | 24 | CApiVector2 (`0x85B82A42`) | |
| 480 | 24 | CApiVector2 (`0x85B82A42`) | |
| 504 | 4 | 0x00000000 (`0x00000000`) | |
| 508 | 4 | 0x00000000 (`0x00000000`) | |
| 512 | 4 | 0x00000000 (`0x00000000`) | |
| 516 | 4 | 0x00000000 (`0x00000000`) | |
| 520 | 4 | LocationFlag (`0x12A4B1D3`) | |
| 528 | 8 | 0x00000000 (`0x00000000`) | |
| 536 | 8 | 0x00000000 (`0x00000000`) | |
| 544 | 4 | 0x00000000 (`0x00000000`) | |
| 548 | 4 | 0x00000000 (`0x00000000`) | |
| 552 | 4 | 0x00000000 (`0x00000000`) | |
| 560 | 8 | 0x00000000 (`0x00000000`) | |
| 568 | 8 | 0x00000000 (`0x00000000`) | |
| 576 | 8 | 0x00000000 (`0x00000000`) | |
| 584 | 8 | 0x00000000 (`0x00000000`) | |
| 592 | 4 | 0x00000000 (`0x00000000`) | |
| 596 | 4 | 0x00000000 (`0x00000000`) | |
| 600 | 4 | 0x00000000 (`0x00000000`) | |
| 604 | 4 | 0x00000000 (`0x00000000`) | |
| 608 | 4 | 0x00000000 (`0x00000000`) | |
| 616 | 8 | 0x00000000 (`0x00000000`) | |
| 624 | 4 | 0x00000000 (`0x00000000`) | |
| 628 | 4 | 0x00000000 (`0x00000000`) | |
| 632 | 4 | 0x00000000 (`0x00000000`) | |
| 640 | 8 | 0x00000000 (`0x00000000`) | |
| 648 | 4 | 0x00000000 (`0x00000000`) | |
| 652 | 4 | 0x00000000 (`0x00000000`) | |
| 656 | 4 | 0x00000000 (`0x00000000`) | |
| 660 | 4 | 0x00000000 (`0x00000000`) | |
| 664 | 4 | 0x00000000 (`0x00000000`) | |
| 668 | 4 | 0x00000000 (`0x00000000`) | |
| 672 | 8 | 0x00000000 (`0x00000000`) | |
| 680 | 8 | 0x00000000 (`0x00000000`) | |
| 688 | 4 | 0x00000000 (`0x00000000`) | |
| 692 | 4 | 0x00000000 (`0x00000000`) | |
| 696 | 184 | BoundaryWallSettings (`0x7C9034C5`) | |
| 880 | 16 | 0x46B8CBC2 (`0x46B8CBC2`) | |
| 896 | 4 | LevelGenerationTag (`0x8419CD40`) | |
| 900 | 4 | 0x00000000 (`0x00000000`) | |
| 904 | 1 | 0x00000000 (`0x00000000`) | |
| 904 | 1 | 0x00000000 (`0x00000000`) | |

