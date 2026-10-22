# wiki 上的数据模块清单（及其对本项目的用处）

> wiki（<https://helldivers.wiki.gg>）的 `Module:` 命名空间下有 276 个页面，其中约 14 个是
> **原始解码数据**，其余是模板/格式化代码。数据不一定准（见 §4），但**结构与字段名**很有用。
> 抓取时间 2026-10-22，原样保存在 `refs/wiki/modules/`。

## 1. 数据模块一览

| 模块 | 大小 | 内容 | 对本项目的用处 |
|---|---:|---|---|
| `Decodedata-Attacks/data.json` | 281 KB | 8 段：damage 426 / projectile 247 / explosion 254 / beam 14 / arc 11 / status_effect 59 / weapon 88 | **六张表的字段名 + 逐条数值** |
| `Decodedata-Attacks-2/data.json` | 295 KB | 同上但字段更全（explosion 多 `shrapnelref`/`projectileid`；projectile 多 `xangle`/`xdelay`） | 更细的字段名 |
| `Decodedata-Attacks/stratagems data.json` | 111 KB | 8 段，含 **`stratagems` 98 条**（每条带 `cooldown`/`uses`/`attacks` 攻击树） | **战备 → 攻击链的直读来源** |
| `Decodedata-Attacks/stratagemdata.json` | 55 KB | 53 条，每条的**战备道具资源**（`ref`/`projectile_type`/`stratcode`/`recoil_info`） | `ref` = StratagemType 名；`projectile_type` = 弹丸类型名 |
| `Decodedata-Attacks/weapons data.json` | 240 KB | 7 段，damage 206 / projectile 109 / explosion 69 / weapons 159 | 武器侧字段名 |
| `Decodedata-Attacks/enemydata.json` | 61 KB | 敌人侧的 damage/projectile/explosion/beam/arc/status | 敌人侧字段名 |
| `Decodedata-Attacks/status data.json` | 13 KB | damage 23（持续伤害）+ status | 状态伤害字段名 |
| `Decodedata-Attacks/new gear.json` | 40 KB | 新装备的 damage/projectile/explosion/... | 同上 |
| `Decodedata-Weapons/data.json` | 25 KB | 49 条武器，每条 70 字段（`category`/`code`/`fullname`/...） | 武器元数据 |
| `Weapon Attach/data.json` | 186 KB | 30 个配件的 `name`/`desc`/`variants` | 配件命名 |
| `Weapon Attach/data weapons.json` | 34 KB | 47 把武器 × 每个配件槽的 `lvl`/`cost` | 解锁成本 |
| `Weapon Attach/attachments.json` | 0.7 KB | 4 槽（Optics/Underbarrel/Muzzle/Magazine）× 9 项 | 索引 |
| `ArmorPassiveData` | 3.8 KB | Lua（非 JSON） | 破甲被动 |

⚠ `Module:Stratagem type categories` 虽然名字最像我们想要的分类表，实际只是 **Lua 格式化代码**，
没有数据。

## 2. 字段字典：这些模块给出的名字

### 2.1 projectile_settings（272 B）

`Decodedata-Attacks/stratagems data.json` 的 projectile 段给了完整具名字段，
用 `S_P15` 一条逐值对上我们的行（`+0=160`）：

| 偏移 | 字段 | 我们的值 | 模块的值 |
|---:|---|---|---|
| `+24` | `caliber` | 110 | 110 |
| `+28` | `pellets` | 1 | 1 |
| `+32` | `velocity` | 400 | 400 |
| `+36` | `mass` | 5000 | 5000 |
| `+40` | `drag` | 0 | 0 |
| `+44` | `gravity` | 1 | 1 |
| `+48` | `simulation_steps` | 1 | — |
| `+52` | `lifetime` | 0.95 | 0.95 |
| `+56` | `life_time_randomness` | 0 | 0 |
| `+60` | `damage_id` | 271（行 id） | `S_P15_dm`（名） |
| `+64` | `pen_slow` | 0.25 | 0.25 |
| `+88` | `thruster_effect_length` | 0.01 | — |
| **`+136`** | **`explode_angle`** | **80** | **80** |
| `+144` | `explode_on_impact_id` | 380 | `S_P15_IE` |
| `+148` | `explode_proximity` | 0 | 0 |
| `+152` | `explosion_delay` | 0 | 0 |
| `+156` | `explode_id`（过期） | 380 | `S_P15_IE` |
| `+160` | `arming_distance` | 0 | 0 |
| `+168` | `decal_size` | 0.1 | — |
| `+180`~`+200` | `max_ricochets` / `ricochet_threshold_angle` / `_speed` / `_angle_loss` / `spread_vertical` / `spread_horizontal` | 1 / 83 / 60 / 0.75 / 12 / 45 | — |

⚠ **`+136` 是我上一轮猜错的偏移**：当时按字段顺序推成 `+140`，实测 `+140=1`（某个 bool），
真正的 `explode_angle=80` 在 `+136`。这是"按顺序推断"的典型翻车点。

### 2.2 explosion_settings（152 B）

`stratagems data.json` 的 explosion 段直接给了 `r1 / r2 / r3 / cone_angle / shrapnel / shrapnel_count`：

| 偏移 | 字段 | 证据 |
|---:|---|---|
| `+4` | `damage_id` | 段里每条都有 `damage_id` |
| `+16` | `r1` inner radius | `S_P13_IE`: 4 = 4 |
| `+20` | `r2` outer radius | 12 = 12 |
| `+24` | `r3` **shockwave radius** | 18 = 18（wiki 数据页面也标 "Shockwave Radius 18 m"）|
| `+28` | **`cone_angle`** | `S_P15_IE`: 35（补丁前）；我们读到 **27** |
| `+32` | `camera_shake_radius` | 80 = 80 |
| `+56` | `particle_effect_path` | 用 64 位值反查唯一行 |
| `+64` | `audio_event` | 580769797 = 580769797 |
| `+80` | **`shrapnel_count`** | `S_P15_IE`: 12；`_MK2` 7 |
| `+84` | **`shrapnel`（破片弹丸）** | 语义确定，编码未定（见 §5） |

⚠ 上一版把 `+24` 叫 `stagger_radius`（filediver 的命名）。wiki 自己的数据页面把它显示为
**Shockwave Radius**，且 `r3=18` 与截图上的 18 一致，所以按 `r3 = shockwave radius` 记，
括号里保留 filediver 的别名。

### 2.3 damage_settings / beam / arc / status_effect

| 段 | 条目 | 字段名 |
|---|---:|---|
| damage | 426 | `dmg, dmg2, ap1, ap2, ap3, ap4, demo, stun, push, param1`（+ `hits_per_second`/`element_name`/`statuses` 在其它模块里） |
| beam | 14 | `range, damage_id`（`weapons data` 里还有 `falloff, radius`） |
| arc | 11 | `velocity, range, spreadrange, chainangle, aimangle, splits, damage_id` |
| status_effect | 59 | `strength, duration` |

这几张表**尚未做值层面的对接**（我们的 damage 661 行、beam 30、arc 16、status 73，
模块只有 426/14/11/59 条，且缺一个稳定的连接键）。

## 3. 一处必须注意的口径差异

同一份 wiki 上有**两套战备视图**，它们对同一个战备可能指向不同的弹丸记录：

| 来源 | 字段 | Orbital Precision Strike |
|---|---|---|
| `stratagemdata.json` | `projectile_type` | `Orbital_Precision_Strike` |
| `stratagems data.json` | `attacks[0].name` | `S_P13` |

前者是**弹丸类型枚举名**，后者是**攻击资源名**。而你截图里那张表（`S P13` / Size 406 mm /
Mass 30 kg / Velocity 400 m/s）对应的是 **`S_P13`**，不是 `Orbital_Precision_Strike`。

我们表里也存在同一 `name_upper` 的多行（例：`Shrapnel_Heavy_MK2` 在 `+0=12` 和 `+0=191` 各有一行），
所以"按名字哈希连接"会歧义——**这是目前弹丸表命名最脆的一环**。

## 4. 数据准不准

* **数值来自不同 build**：`stratagemdata.json` 写 Orbital Precision Strike 冷却 90，
  本 build 与 wiki 数据页面都是 80；`S_P15_IE` 的 `cone_angle` 写 35，本 build 是 27。
* **语义字段可靠**：`ref`（= StratagemType 名）与 HD2Runtime 的 `nativeType` **38/42 相等**；
  `stratagems` 段的 `cooldown`/`uses` 与我们逐条对 **14/14、14/14** 全中。
* 结论：**拿它当字段名字典和结构参照，不拿它的数值当基准。**

## 5. 还没解决的

1. `+84`（破片弹丸）的**编码**：语义确定（写它会出破片），但它既不是弹丸行的 `+0`，
   也不是 `ProjectileType` 枚举下标。
2. 弹丸表**重复行**：同一 `name_upper` 出现多行，导致按名连接有歧义。
3. damage / beam / arc / status 四张表**尚未做值对接**（缺稳定连接键）。
4. ~~`stratagems data.json` 的 `num_bombs` / `num_salvos` / `area_size` / `fire_height`
   还没在我们 400 B 行里定位~~ —— **已查清：它们不在战备行里**。连同
   `bomb_interval` / `salvo_interval` / `calltime` / `health` / `armor` 一起反查全部落空；
   战备表只携带 `cooldown`（`+104`）与 `uses`（`+80`）两个标量。见
   `STRATAGEM-SETTINGS-DECODED.md` §7.6。

## 6. 复现

```bash
# 抓取（需要浏览器 UA，wiki 会挡默认 UA）
for p in "Module:Decodedata-Attacks/data.json" "Module:Decodedata-Attacks/stratagems data.json" \
         "Module:Decodedata-Attacks/stratagemdata.json"; do
  curl -sS -A "Mozilla/5.0" "https://helldivers.wiki.gg/wiki/$(echo "$p" | sed 's/ /_/g')?action=raw"
done

# 走通一条链
python tools/stratagem_attack_chain.py --sk <你的>/recipient.sk --stratagem "Orbital Precision Strike"
```

## 7. 出处

* 全部模块：<https://helldivers.wiki.gg> 的 `Module:` 命名空间，页面清单见
  `refs/wiki/modules.json`（276 页的 API 导出）。
* 本地副本与字段对比：`refs/wiki/modules/`、`refs/wiki/stratagemdata.json`。
* 数值校验对照：本机解密表（`projectile_settings` / `explosion_settings` / `stratagem_settings`）。
