# 战备的引用链：战备 → 弹丸 → 爆炸（build 25988413）

> 结论先说：**表内只有"弹丸 ↔ 爆炸"这一跳**。战备行**不**引用弹丸行——它存的是
> `StratagemInfo.type` 原生枚举，类型到投送模板的绑定在引擎/资源侧。
> 但整条链仍然闭合了，靠的是**排除法 + 一次官方补丁**（§5）。

## 1. 结论

| 边 | 在表里？ | 字段 | 判定 |
|---|---|---|---|
| 弹丸 → 爆炸（命中） | ✓ | `projectile_settings +144` | ✓ 实测 |
| 弹丸 → 爆炸（过期） | ✓ | `projectile_settings +156` | ✓ 实测 |
| 爆炸 → 伤害 | ✓（待细验） | `explosion_settings +4` | ⚠ 顺序推断 |
| 爆炸 → 破片弹丸 | 语义 ✓ / 编码 ✗ | `explosion +80` 数量、`+84` 类型 | ✓ 数量 / ⚠ 类型编码 |
| **战备 → 弹丸** | **✗ 不在表里** | — | ✗ 否证（见 §4） |

## 2. 弹丸 → 爆炸：`+144` / `+156` 装的是爆炸行的 `+0` id

filediver 的明文 dump（`refs/helldiversdata/`，快照早于本次补丁）给出字符串关系：

```
ProjectileType_Orbital_Cannon_110mm:
    explosion_type_on_impact = ExplosionType_OrbitalShot
    explosion_type_expire    = ExplosionType_OrbitalShot
```

我们这边，`ProjectileType_Orbital_Cannon_110mm` 那一行（弹丸 `+0` = 160）读数是
`+144 = 380`、`+156 = 380`。而爆炸表里 `+0 == 380` 的行只有一条。

**两种解释，只有一种站得住**：

| 解释 | 落点 | 是否吻合 |
|---|---|---|
| `+144` 是爆炸行的 `+0` id | 爆炸表 `rows[141]`：inner 0.2 / outer 0.5 / stagger 4 / shake 80 / audio 580769797 / 破片 12 | ✓ 与 filediver 的 `ExplosionType_OrbitalShot` **六项全中** |
| `+144` 是爆炸表的文件下标 | `rows[380]`：`+0`=132、cone=0、audio=3071971321 | ✗ 什么都不对 |

⇒ `+144` / `+156` 是**爆炸行的 `+0` id**，不是下标。

## 3. 爆炸表的字段（这轮解出来的）

拿 `ExplosionType_OrbitalShot` / `_MK2` 两条记录逐字段比对（filediver 明文 vs 我们的行）：

| 偏移 | 字段 | 判据 |
|---:|---|---|
| `+0` | 行 id（1..424 打乱，全表唯一） | ✓ |
| `+16` | `inner_radius` f32 | ✓ 0.2 = 0.2 |
| `+20` | `outer_radius` f32 | ✓ 0.5 = 0.5 |
| `+24` | `stagger_radius` f32 | ✓ 4 = 4 |
| **`+28`** | **`cone_angle` f32** | ✓ 见 §5 |
| `+32` | `camera_shake_radius` f32 | ✓ 80 = 80 |
| `+40` / `+48` | `shake_assets` 的（偏移, 数量） | ⚠ 形状吻合（数量 2 = 两条资产） |
| `+56` | `particle_effect_path` u64 | ✓ 用 64 位路径反查到唯一行 |
| `+64` | `audio_event` u32 | ✓ 580769797 = 580769797 |
| `+80` | `num_shrapnel_projectiles` u32 | ✓ 12 / 7 = 12 / 7 |
| `+84` | 破片弹丸类型 | ⚠ 语义已由实机验证（写 `+80/+84` 出破片），但编码既不是行 id 也不是枚举下标 |

## 4. 战备 → 弹丸：不在表里（否证）

定向测试：把 15 个轨道系弹丸的 `+0` id 拿去逐槽扫 13 行 `ORBITAL.*` 战备行。
**没有任何一行命中自己的弹丸**——只出现两次，且都落在 `+0`，那是枚举值和别人的小 id 撞车。

原因在 §6：`+0` 不是战备 id，是 `StratagemInfo.type`。类型到"用哪发弹丸"的绑定由
`StratagemTypeDataTemplate` 完成，那是引擎资源侧的事，不在这 55 张表里。

## 5. 链条怎么闭合的：排除法 + 官方补丁

wiki 补丁 **1.007.200（2026-10-20）** 对 Orbital Airburst Strike 写了两条：

```
Decreased cooldown from 100 seconds to 90 seconds.
Decreased explosion cone angle from 35 to 27
```

四条实测事实拼起来就闭合了：

1. **全表只有一条爆炸的锥角变了。** 六项非锥角字段（半径×2 / stagger / shake / audio / 破片数）
   全表匹配 `ExplosionType_OrbitalShot` 的行**只有一条**：`rows[141]`，锥角 **27**
   （filediver 明文写 **35**）。同法匹配 `_MK2` 的唯一行是 `rows[142]`，锥角仍是 **35**——
   即补丁只改了其中一型。
2. **指向这条爆炸的弹丸只有一发。** 弹丸 `+144 == 380` 的行全表唯一：
   `ProjectileType_Orbital_Cannon_110mm`。
3. **那发弹丸就是 110mm 空爆弹**——Orbital Airburst Strike 用的正是它。
4. 补丁把这条变更登记在 Orbital Airburst Strike 名下。

⇒ 战备（Airburst Strike）→ 110mm 空爆弹 → `ExplosionType_OrbitalShot` → 锥角 35→27。
**中间那跳虽然不在表里，但由"唯一性 + 官方补丁归属"两侧夹住了。**

副产品：`explosion_settings +28 = cone_angle` 由此坐实——这是这条链最硬的一个结论，
因为它同时被 filediver（35）、本表（27）、官方补丁（35→27）三方对齐。

## 6. 顺带改正：战备 `+0` 不是"战备 id"，是原生枚举

`uiIcon.nativeTypeValue` 自称来自 `StratagemInfo.type`。把它和我们 `+0` 对表：

| 战备 | 本表 `+0` | catalog | 差 |
|---|---:|---:|---:|
| EAGLE 500KG BOMB / AIRSTRIKE、ORBITAL GATLING / WALKING | 3 / 18 / 4 / 21 | 同 | **0** |
| ORBITAL GAS STRIKE | 42 | 41 | **+1** |
| PRECISION 121/118、AIRBURST 86/83、LASER 110/107、380MM 128/125… | | | **+3** |

低值不动、高值统一 +3 —— 这是**枚举插入**的签名：两个 build 之间 `StratagemType` 多了 3 个成员，
插在值 21 与 41 之间 1 个、41 与 83 之间 2 个。所以 `+0` 是枚举值，不是行 id。
（153 行 153 个不同值只是因为这张表每个枚举值恰好只出现一次。）

## 7. 工具

| 工具 | 作用 |
|---|---|
| `tools/settings_field_align.py` | 用连接键把 filediver 明文的字段名对齐到本表偏移；带"常量字段 / 常量槽"双重排除，避免 0 值互相假匹配 |
| `tools/table_xref_scan.py` | 通用跨表引用扫描（找出源表哪个槽命中目标表的 id 列） |

```bash
# 弹丸表字段对齐（name_upper 是可靠连接键，132 条唯一配对）
python tools/settings_field_align.py --sk <你的>/recipient.sk \
    --table projectile_settings --dump refs/helldiversdata/generated_projectile_settings.json \
    --json-root ProjectileSettings --anchor name_upper=4

# 通用跨表引用扫描
python tools/table_xref_scan.py --sk <你的>/recipient.sk --source stratagem_settings
```

⚠ `settings_field_align.py` 对爆炸表的自动对齐**只配到 11 对**（`particle_effect_path` 大量重复，
且我们的表比 filediver 多 175 条），所以 §3 的爆炸字段图是**人工按字段顺序 + 唯一性验证**得出的，
不是工具自动产出的。

## 8. 出处

* filediver 明文 dump：`refs/helldiversdata/generated_{explosion,projectile}_settings.json`、
  `enums_{ExplosionType,ProjectileType}.json`（MIT）。快照早于补丁，因此保留 35。
* 官方补丁记录：wiki 变更历史，补丁 **1.007.200（2026-10-20）**。
* 本 build 安装时间：`steamapps/appmanifest_553850.acf` → `buildid 25988413`，
  `LastUpdated 1792487737` = 2026-10-20 17:15 本地。
* 攻击树 / 分支名 / 原生类型值：HD2Runtime 0.28.1 `StratagemAuthoringCapabilities.json`（MIT）。
* 字段偏移：本机解密表逐字段实测（§2、§3、§5）。
