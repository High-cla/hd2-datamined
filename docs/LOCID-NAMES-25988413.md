# 表的本地化 ID 槽：从"内部名"走到"游戏内名字"（build 25988413）

一句话：**表行里存的不是字符串，是 32 位本地化 ID**；`.strings` 资源是一张全局的
ID→文本表（英文 18 个 blob / 24,846 条 / 15 种语言同构）。把这条打通之后，**六张表**
的绝大多数行都拿到了游戏内文本：

| 表 | 行数 | 名字 | 附带字段 |
|---|---:|---:|---|
| `stratagem_settings` | 153 | **145** | 描述 129 / 长描述 49 / 状态标签 153 |
| `projectile_settings` | 355 | **225** | 弹头短名 36 |
| `weapon_customization_settings` | 252 | **234** | 描述 234（弹种/枪口/弹匣/瞄具/涂装/扳机/下挂）|
| `customization_armor_sets` | 422 | **389** | 描述 389 |
| `customization_passive_bonuses` | 33 | **33** | — |
| `unit_customization_settings` | 12 | **11** | 图案名 9 |
| `planet_data` | 438 | **399** | 地形描述 371 |
| `explosion_settings` | 424 | 0（自己没名字）| 靠引用链反查出 **103** |

这份文档记录**判据**、**覆盖数**、**几何陷阱**、**交叉验证**、以及被否证的假设。

---

## 1. 判据：为什么不靠"看起来像"

`.strings` 的条目 ID 是构建期分配的 32 位整数，语料里 24,846 个。于是**随机**一个 u32
落进语料集合的概率是

```
24,846 / 2^32 = 5.8e-6
```

一张 355 行的表，某一列"恰好"命中的期望次数是 `355 × 5.8e-6 = 0.0021`。所以

* 单行命中 → 巧合，不能说明任何事；
* **整列几十上百行命中 → 不可能是巧合**（p 远小于 1e-6）。

这就是全部判据，不依赖任何外部映射表。反向用法同样重要：`explosion_settings` 全表
唯一的命中槽是 `+8`，但只有 3 行命中（`'Environment'`、`'Unknowable Forces'`），
**样本太少，所以我们不把它当名字字段**，只记录。

第二个判据是**语义自洽**：命中的文本必须和那张表的对象同类。`projectile_settings`
`+12` 解出来的全是 `APHET / FLAK / HE / FRAG` 这种弹头短名，`weapon_customization_settings`
`+12` 解出来的全是 `9x20mm EXPLOSIVE / MUZZLE BRAKE / SHORT MAGAZINE` 这种配件名 ——
一个槽"碰巧"命中几百条同类词的概率可以忽略。

---

## 2. 各表结果

### 2.1 `stratagem_settings`（400 B × 153 行，12 个系族组）

| 槽 | 含义 | 覆盖 |
|---|---|---:|
| `+40` | 大写名 | 145/153 |
| `+44` | 显示名 | 135 直接 + 1 文本匹配 + 9 退回大写 = **145/153** |
| `+48` | 描述 | 129/153 |
| `+52` | 长描述（fluff，49 条有值，其中 **45 条标着 `NOT IMPLEMENTED`**，即砍掉的内容） | 49/153 |
| `+56` | 状态标签，整表只有 4 个值：`EQUIPPING` 120 / `CHARGING` 16 / `FUELING` 10 / `PREPARING` 7 | 153/153 |

145 个显示名对上 wiki 页面 **115** 个（44 精确 + 71 带厂商前缀）。剩下 8 行连大写名都没有，
见 §4。

### 2.2 `projectile_settings`（272 B × 355 行）

| 槽 | 含义 | 覆盖 |
|---|---|---:|
| `+4` | 大写名 ID | 225/355 |
| `+8` | 显示名 ID | 224/355 |
| `+12` | 弹头短名 ID | 36/355 |

355 行拆开：224 行大小写两份都有，1 行只有大写，**72 行的 ID 字段是 0**（本来就没有名字，
纯内部弹丸），58 行是非零但语料里不存在的 ID（死引用，见 §4）。

解出来的名字就是游戏内的弹种名：

```
行  0  100kg Cluster Bomb        行 11  500kg Bomb
行  2  100kg Bomb                行  5  Napalm Bomb
行 31  20mm Flak Rounds          行 67  40mm HE Mortar
行 79  380mm HE Cannon Round     行 271 110mm Standard Rocket
行 281 12g Scatter Shot          行 290 10g Fragmentation
```

### 2.3 `weapon_customization_settings`（88 B × 252 行，9 个组）

| 槽 | 含义 | 覆盖 |
|---|---|---:|
| `+12` | 大写名 ID | 234/252 |
| `+16` | 显示名 ID | 216/252 |
| `+20` | 描述 ID | 234/252 |

第 9 组（12 个涂装）的 `+16` 是 0/12 命中 —— 该组字符串池里插了颜色块，正是 `POINTERS`
注释里说的"位置法在这组会读到碎片"。另外 filediver 字段表把 `+24` 叫 `Fluff`，
这里 **0 命中，不是本地化 ID**（✗ 修正）。

这一张表是"可选弹种 / 枪口 / 弹匣 / 内部件 / 瞄具 / 涂装 / 扳机 / 下挂"的总表，
现在每个配件都有游戏内名和一句话描述，直接对应改装界面。

### 2.4 `customization_armor_sets`（64 B × 422 个组）

| 槽 | 含义 | 覆盖 |
|---|---|---:|
| `+12` | 大写名 | 389/422 |
| `+16` | 显示名 | 356/422 |
| `+20` | 描述 | 389/422 |

解出来是护甲名：`FS-37 RAVAGER` / `FS-55 DEVASTATOR` / `CW-4 ARCTIC RANGER`，
描述就是游戏里那句风味文本（`Contains many small pockets, allowing the user to evenly
distribute the weight of ammunition, samples, and cool rocks.`）。

### 2.5 `customization_passive_bonuses`（56 B × 33 个组）

`+4` = 名字，**33/33 全中**：`EXTRA PADDING` / `SERVO-ASSISTED` / `ENGINEERING KIT` /
`MED-KIT` / `ADRENO-DEFIBRILLATOR` —— 就是护甲被动条的名字。

### 2.6 `unit_customization_settings`（80 B × 12 个组）

`+12` = 11/12（`PATRIOT EXOSUIT` / `EMANCIPATOR EXOSUIT` / `GUNNER FRV`），
`+16` = 9/12（`EXOSUIT PATTERN` / `VEHICLE PATTERN`，是图案标签不是名字）。

### 2.7 `planet_data`（624 B × 438 个组）

| 槽 | 含义 | 覆盖 |
|---|---|---:|
| `+8` | 星球名（395 个去重） | 399/438 |
| `+16` | 地形/风味描述（只有 20 个去重 —— 同一地形共享） | 371/438 |
| `+0` | 地图块资源路径（u64 池指针） | 406/438 |
| `+88` | 内部 id `planet_000`..`planet_437` | 438/438 |
| `+96` | 区域名 `region_superearth` 等（32 个去重） | 438/438 |

名字例如 `SUPER EARTH`、`KLEN DAHTH II`、`PATHFINDER V`、`WIDOW'S HARBOR`、`MERIDIAN IIa`。
`+0` 是`content/level_generation_settings/planet_settings/planet_setup/planet_<地块>_<地形>_<变体>`，
即"这个星球用哪张地图块"——顺带得到了星球→地图块的映射。

### 2.8 没有名字槽的表（✗）

`zone_data`、`region_settings`、`status_effect_settings`、`hit_effect_settings`、
`damage_settings`、`beam_settings`、`arc_settings`、`stratagem_upgrade_settings`、
`entity_deltas`、`modifier_settings`、`policy_settings`、`add_resource_dependencies`
—— 全表扫完，没有任何一列能过 `min_hits` 判据。`candidate_descs` 的 `+0` 只有 3/12
（`Gun Ingbrit Morgunsdottir` 这种随机人名候选），不够当名字字段。

---

## 3. 几何陷阱：两种组头，只认一种会得到假阴性

这是这轮踩得最深的坑。`LDLD` 组的 payload 有两种开头：

| 形态 | payload 开头 | 例子 | 记录起点 |
|---|---|---|---|
| **数组型** | `u64 0x10 \| u64 count` 然后 `count` 条记录 | stratagem(400)、projectile(272)、explosion(152)、weapon_customization(88) | payload+16 |
| **单记录型** | **payload 直接就是那条记录**，没有描述符 | planet_data(624)、zone_data(912)、armor_sets(64)、unit_customization(80)、passive_bonuses(56) | payload+0 |

第一版工具只认数组型，于是 planet/armor/passive 这些表被整个跳过，输出一句
"没有候选槽位" —— **那是假阴性，不是发现**。表现为：

```
=== customization_armor_sets ===      # 修之前
  没有候选槽位                        # ← 错：真实答案是 +12/+16/+20
```

还有第二个坑：**单记录型的表每组只有 1 行**，按组统计命中数永远 ≤ 1，会被 `min_hits`
过滤掉。所以扫描必须按 `(stride, offset)` **跨组聚合**——armor_sets 是 422 个组一起数，
不是 422 次数 1 个。

另外 stride 不许从 `payload % count` 推：有字符串池的表永远除不尽（explosion 424 行后面
跟着 3,664 B 池）。stride 只能来自 typelib —— 容器类型的唯一成员是行数组，成员的元素
类型大小就是 stride（projectile 272 / explosion 152 / beam 112 / arc 104 都与实测逐字节吻合）。

---

## 4. 交叉验证

### 4.1 名字与物理字段（✓ 硬验证）

名字槽和数值字段是同一行的不同列，读错槽数值不会配合。抽查：

| 行 | 解出的名字 | `+24` caliber | `+36` mass |
|---:|---|---:|---:|
| 2 | `100kg Bomb` | 25.00 | **100.000** |
| 11 | `500kg Bomb` | 50.00 | **500.000** |
| 271 | `110mm Standard Rocket` | **110.00** | 3300 |
| 67 | `40mm HE Mortar` | **40.00** | 750 |
| 263 | `15x100mm Standard Rocket` | **15.00** | 100 |
| 79 | `380mm HE Cannon Round` | 406.00 ⚠ | 30000 |

前两行是最硬的一条：名字里的重量（100kg / 500kg）与行内 `mass` 字段（100.000 / 500.000）
逐位相同；`110mm` / `40mm` / `15x100mm` 与 `caliber` 完全相等。`380mm` 与 `caliber=406.00`
的差别是名义口径（Super Earth 的 `380mm` 命名）与真实口径（406 mm = 16 英寸）之差，
⚠ 按命名习惯解释，不作数值依据。

### 4.2 与 wiki 页面交叉验证（✓ 补上了）

上一版这里写的是"这三张表没有外部对照，因为本地 wiki 库只有战备页和武器页"。现在补上了：
把 wiki 的 `Category:Armor`、`Category:Planets`、`Category:Armor Passives` 一起抓下来
（`tools/fetch_wiki_pages.py`，50 标题/请求 + 1 s 间隔），本地库从 237 页扩到 **763 页**，
再按扁平化 + 后缀 + 包含 + 模糊四条规则做匹配（`tools/wiki_match_tables.py`）：

| 表 | 唯一名字 | 匹配到页面 | 其中精确 | 后缀/包含/模糊 | wiki 上确实没页面 |
|---|---:|---:|---:|---:|---:|
| `customization_armor_sets` | 237 | **217** | 213 | 1 / 2 / 1 | 20 |
| `customization_passive_bonuses` | 33 | **32** | 32 | 0 | 1（`STANDARD ISSUE`） |
| `planet_data` | 395 | **277** | 276 | 1 / 0 / 0 | 118 |

没页面的那些逐个查过（`refs/wiki/unmatched-existence.json`）：**21 个护甲/1 个被动/118 个星球
在 wiki 上确实不存在**（查标题 API 直接 `missing`），不是我们匹配没做到 —— 它们是发布数据里有、
wiki 还没建页的条目（未实装 / 从未在银河战争里出现过的星球）。

**最硬的一条交叉验证：星球描述逐字相等。** 我们的 `planet_data +16` 是地形描述，wiki 的
`{{Infobox Planet | description=}}` 也是它。两边都有的 258 个星球里：

```
描述逐字相同      218
描述不同           40   —— 全是 wiki 校对（游戏原文 "perenially"/"The arid,..."，
                           wiki 改成 "perennially"/"This arid,..."）
```

名字 → 页面 → 描述三样同时对上，说明 `+8` 的名字槽与 `+16` 的描述槽确实属于同一个星球。

另外还暴露了两处**游戏文本里的错字**（wiki 已修正，值得记下来）：
`Patient Zero's Rememberance`（游戏）/ `Remembrance`（wiki）、
`Greatcloak of Rebar Resolve`（游戏）/ `Rebar Resolve`（wiki 短标题）。

### 4.3 没有独立交叉验证的部分（⚠）

`+0` 的资源路径曾想用来互证星球名，结果是否证的（路径编码的是地形，不是名字）：

```
KLEN DAHTH II  <-> planet_desert_sandy_klen_dahth_2      ✓ 一致（罗马数字 vs 阿拉伯数字）
WIDOW'S HARBOR <-> planet_desert_sandy_moon              ✗ 路径编码的是地形，不是名字
PILEN V        <-> planet_desert_sandy_spiky             ✗ 同上
```

也就是说 `+0` 的路径是"地块_地形_变体"三元组，不是名字的另一种写法。**路径不构成名字的证据**，
只能当"星球→地图块"的映射用。

---

## 5. ✗ 被否证的假设：剩下的查不到，不是因为 bundle 没解够

上一轮的结论是"再解几个 bundle 就能补齐"。**不成立**，理由三条：

**① 英文语料是全局且唯一的。** `.strings` 的 ID 空间是全局命名空间 —— 同一个 ID 在每种语言里
指向同一条文本的不同译文。实测（bundle.00 全解 + 01..10 解完）：

```
bundle.00          18 个 distinct 英文 blob / 24,846 条 ID / 1.92 MB
bundle.01..10      每个 bundle 解出 4,054 个文件，文件清单 md5 全同
                   每个 bundle 的 18 个英文 blob 内容哈希也与 00 完全相同
并集               18 个 blob、24,846 条 ID —— 一个都没多出来
语言               15 种，每种 17-18 个 blob
```

11 个 bundle 的文件清单 md5 完全一致（`7c9b1207694dc7e8f969995c50365c08`），说明
`bundles.NN.nxa` 里带的 strings 是同一批资源的重复副本 —— 每个 bundle 都带一份完整语言包，
是为了流式加载，不是各带一份独立语料。因此 11..29 没有继续解：**ID 空间不会因为多解 bundle 变大**。

15 种语言的 `language` 字段全部反查出来了（`ThinHash(两字母代码)`，枚举 676 个组合即得）：

```
bp 巴西葡语   cn 简中   fr 法语   jp 日语   es 西语   ms 马来语   us 英语
de 德语       it 意语   pl 波兰语 tc 繁中   ko 韩语   pt 葡语     ru 俄语    gb 英式英语
```

也就是说"再解 25 个 bundle"只会重复拿到同一批 18 个英文副本。bundle 里带 strings 是为了流式加载，
不是各带一份独立语料。

**② 那 18 个 ID 在 15 种语言的 1,584 个 blob 里全都不存在。** 不是"缺英文"，是整条记录没发布
（1,584 = bundle.00 的 264 个 blob 加上当时已解出的 bundle 01-05 的 1,320 个）：

```
0xa50b8131  BACKPACK. HOVERPACK BACKPACK      不在任何 blob
0x882003c9  EAGLE. (NOT USED) ADDITIONAL ...  不在任何 blob
0x9439404a  MISSIONS. CARGO CONTAINER         不在任何 blob
...                                            共 18 行
```

而且这些 ID 两侧的邻居都在语料里（例如 `0xe82308d9` 的邻居是 `0xe8231d84`，只差 0x14EB），
说明它们**曾**在 ID 空间里占位，是本 build 里被删掉的条目 —— 典型的"标记为 NOT USED 的内容"。

**③ 可回填的只有 10 行，而且回填要标来源。** 处理顺序写进了工具：

| 来源 | 行数 | 做法 |
|---|---:|---|
| `name_id` | 135 | `+44` 直接命中，无需解释 |
| `case_variant` | 1 | 语料里存在同文本但大小写不同的条目（`Hover Pack`，ID `0x0d12dc99`，与行内 `0xa50b8131` 不同）|
| `upper_fallback` | 9 | 只有大写名（任务物件在 HUD 上本来就显示大写）|
| 无 | 8 | 连大写名都没有，留空 |

剩下的 8 行：`EAGLE. (NOT USED) ADDITIONAL STRAFING RUNS`、`MISSIONS. IMMEDIATE EXTRACTION BEACON`、
`MISSIONS CLAN STATION. Nuke`、`MISSIONS. REMOTE EXPLOSIVES`、`SEAF Squad`、`TANK. TANK RELOAD HE/AT/CANISTER`。

---

## 6. 爆炸行：自己没名字，但引用链上有

`explosion_settings`（152 B × 424 行）三条路都试过了：

* u32 本地化 ID 槽：全表唯一命中是 `+8`，3 行，不是名字字段；
* u64 池指针：没有一个槽能解出可打印串（表尾那 3,664 B 池不是字符串池）；
* 结论 ✗：**爆炸行内部没有名字**。

但是**指向它的行有名字**：`projectile_settings` 的 `+144`（`explode_on_impact_id`）和 `+156`
（`explode_id`）存的是爆炸行的 `+0` 类型枚举，而投掷物行的 `+8` 能解成 `'500kg Bomb'` 这种名字。
于是爆炸行 = 引用它的投掷物名字集合：

```
爆炸行 424
有效引用边        210   （悬空引用 0）
有消费方的爆炸行  159
能命名的爆炸行    103   （97 个唯一名字 + 6 个被多个投掷物共用）
```

样本（唯一消费方）：

| 爆炸行 | 三层半径 | 名字 |
|---:|---|---|
| 26 | 1.20 / 6.00 / 8.00 | `40mm HE Mortar` |
| 76 | 2.00 / 10.00 / 17.00 | `380mm HE Cannon Round` |
| 79 | 2.50 / 5.00 / 14.00 | `Cluster Bomb` |
| 92 | 0.50 / 2.50 / 3.00 | `10g Fragmentation` |
| 94 | 1.00 / 3.50 / 5.00 | `15x100mm Standard Rocket` |

样本（共用 —— 改这个爆炸的半径会同时影响多个弹丸）：

| 爆炸行 | 消费方 |
|---:|---|
| 227 | `Homing Ground Missile` / `Homing Ground Missile Mk2` |
| 245 | `110mm Standard Rocket` / `110mm Standard Rocket Mk2` |
| 266 | `500kg Bomb Mk2` / `500kg Bomb Mk3` |
| 285 | `12g Scatter Shot` / `10g Scatter Shot` |

"共用"这一列本身就是改数值前必须看的东西：它告诉你这个爆炸是不是共享资源。

### 6.1 `explosion +8` 是什么：`fallback_damage_loc_name`（✓ 定案）

上一版只写了"这个槽有 3 行命中，样本太少，不当作名字字段"。现在查清了 —— 它确实是
本地化 ID，但**不是名字，而是"伤害归因的兜底文本"**。

三条独立证据：

**① 社区 schema 里这个字段就叫这个名字。** `refs/helldiversdata/generated_explosion_settings.json`
（filediver 的旧版明文 dump，字段名是它给的）里 `+4` 是 `damage_type`，紧接着的
`+8` 字段名是 **`fallback_damage_loc_name`**，值就是"本地化 ID 或 0"。

**② 旧 dump 里非零的正好是我们已知的两行。** 249 条记录里只有 2 条非零，且值相同（`1236481912`
= `0x49B33778` = 我们解出的 `'Environment'`）：

```
行239  ExplosionType_Spikeplant_Shrapnel_Explosion   fallback=1236481912
行240  ExplosionType_Iceplant_Shatter                fallback=1236481912
```

**③ 当前 build 的 424 行里只有一个新增项。** 除了上面两个环境道具，多出一行：

| 爆炸行 | `+0` type | `+4` damage | `+8` | 解出的文本 | 半径 r1/r2/r3 |
|---:|---:|---:|---|---|---|
| 376 | 21 | 499（100 伤害） | `0x49B33778` | `Environment` | 2.0 / 6.5 / 8.0 |
| 377 | 104 | 500（15 伤害） | `0x49B33778` | `Environment` | 2.5 / 4.95 / 3.0 |
| 394 | **68** | **503（500 伤害）** | `0x73904477` | `Unknowable Forces` | 5.0 / 6.0 / 4.0 |

`Unknowable Forces` 这条文本**在整个 24,846 条语料里只出现这一次**，15 种语言的译文都是
"未知力量/Forces mystérieuses/Unbekannte Kräfte"这类措辞。它和 wiki 的 lore 对得上：
[The Void](https://helldivers.wiki.gg/wiki/The_Void) 是 Illuminate 的异象，"任何进入 Void 空间的
探测器都会很快停止发送信号"，游戏里也有 `ENTER THE VOID` / `CONSUMING VOID` 这类文本。
所以第 394 行（500 伤害、半径 5/6/4、无破片）**很可能是 Void 的致死体积**，
归因文本用 `Unknowable Forces` 而不是 `Environment`。

把三行放在一起，语义就闭合了：**非武器来源的爆炸，用 `+8` 指定"死亡归因"显示什么** ——
环境道具显示 `Environment`，Void 显示 `Unknowable Forces`；其余 421 行都是 0，
也就是"归因给武器/战备本身的名字"。

**复核定案（不是孤儿）**：在全部 273 个实体块里找"值集完全落在爆炸类型 id 内"的列，
只有一列含 68 —— `BombardmentComponentData +64`（23 行命中 / 17 个不同爆炸类型，
`[68, 76, 79, 82, 86, 89, …]`）。引用它的那条记录属于实体 `0xAEDC4A073FB4B925`，
组件是 `Bombardment + LoadoutPackage + OrbitalShip + StratagemFiresupport` ——
**某个战备的火力支援弹幕**。所以 68 是"某战备的弹幕爆炸"，不是没人引用的孤儿；
`Unknowable Forces` 是这个弹幕的归因文本。

⚠ 仍未定：具体是哪一个战备（该实体没有百科名，`dev_name` 也为空）；以及它是否与 Void 相关
（"500 伤害 + Void 主题措辞"只是高度指向，没有直接证据）。

---

## 7. 实体库（已完成，见 `docs/ENTITY-LOCID-26088801.md`）

`generated_entities.dl_bin`（47 MB，275 个块）里也有大量本地化 ID：
11,814,849 个 4 字节槽位里 **17,500 个**落在语料 ID 集合里（2,124 个不同 ID），
随机期望 68.3 —— 富集 256 倍。

上一版这里写的是"命中在组内散开、没法定字段"。**现在定了**：实体名只有一处 ——
`EncyclopediaEntryComponentData`（块 56，675 行 × 56 B）：

| 槽 | 角色 | 覆盖 |
|---|---|---:|
| `+0` | 单数名（`Liberator`） | 609/675（90.2%） |
| `+8` | 大写名（`LIBERATOR`） | 495/675 |
| `+4` | 复数名（`Liberators`） | 179/675 |
| `+36` | 物品代码（`AR-23`） | 211/675 |
| `+20` | 长描述（**不导出**） | 217/675 |

643 行能解出名字（359 个不同名），1,939 个实体里 643 个有百科条目、其余 1,296 个**本来就没有
本地名字段**（596 纯 Unit 道具 / 240 Interactable / 217 Objective / 215 Destructible）。
另外 15,367 个命中是 HUD/交互/目标文本，不是实体名（详见那份文档的 §6）。

三条独立交叉验证：211 个带物品代码的条目里 **205 个**能用 `code + name` 精确命中 wiki 标题；
8 个已知键（AR-23、MG-43、SG-8、AC-8、JAR-5、StA-52、R-36、SG-20）逐个逐字对上；
675 个键里 56 个能解析成 `content/` 资源路径，其中 33 个（58.9%）名字词与路径词一致。

---

## 8. 三态小结

**✓ 实测**

* `.strings` 的 `language` 字段 = `ThinHash(语言代码)`（seed 0 的 MurmurHash64A 取高 32 位），
  本 build 的 15 种语言**全部**反查出来（`us` `gb` `fr` `de` `es` `it` `pl` `pt` `bp` `ru`
  `cn` `tc` `jp` `ko` `ms`）。
* 七张表的名字槽（见 §2），覆盖 145/153、225/355、234/252、389/422、33/33、11/12、399/438。
* 名字与 `mass` / `caliber` 数值字段在 6 个抽查行上完全吻合（§4.1）。
* 210 条投掷物→爆炸引用边，0 悬空；103 个爆炸行因此有名字。
* 组头有两种形态（§3），修好之后 armor_sets / planet_data 才有命中的。
* 实体名定位到 `EncyclopediaEntryComponentData`（§7）：643/1,939 有名字，205/211 条带代码的
  条目能用 `code + name` 精确命中 wiki 标题。
* wiki 覆盖：护甲 217/237、护甲被动 32/33、星球 277/395 匹配到页面；星球描述 218/258 逐字相同（§4.2）。

**✗ 否证**

* "多解 bundle 就能补齐剩下的 ID" —— 英文语料是全局唯一的那 18 个 blob（§5①）。
* "爆炸行里有名字字段" —— 三条路全落空（§6）。
* "`weapon_customization +24` 是 Fluff 本地化 ID" —— 0 命中（§2.3）。
* "`explosion +8` 是名字槽" —— 只有 3 行命中，样本不足以支撑，明确不当名字用。
* "planet `+0` 的路径能印证星球名" —— 路径编码地形，不是名字（§4.2）。
* "planet/armor/passive 这些表也能靠位置法命名" —— 位置法在这些表上是假阴性（§3）。

**⚠ 未定**

* `explosion +8` 那 3 个值（`Environment` ×2、`Unknowable Forces` ×1）到底是什么字段，不知道。
* `projectile +12`（弹头短名）只有 36/355 命中，剩下 319 行的短名是空还是另有来源，没查。
* `380mm HE Cannon Round` 的 `caliber=406.00`：名义口径与真实口径不一致，按命名习惯解释，
  没有独立证据。
* armor/passive/planet 三张表的名字与 wiki 页面对上了（217 / 32 / 277），但**没页面的条目
  （20 / 1 / 118）只能确认 wiki 上不存在，不能确认它们在游戏里是否可获取**。
* 实体库 1,939 个实体里 1,296 个没有本地名字段（不是没找到，是扫完了没有）；
  块 0 尾部那 27,050 个 u16（组件索引）还没解码。

---

## 8.5 命名约定：查不到的名字一律写"未知"

发布产物里**不留空洞**。任何解不出名字的行/实体都写 `未知`，并同时给一个 `status` 字段，
把"三种缺失"区分开（这三者的含义完全不同，混成一团是误导）：

| status | 含义 | 数量示例 |
|---|---|---:|
| `known` | 本地化 ID 解出了文本 | 弹丸 225 / 战备 145 |
| `unknown` | 该表这一行**没有名字字段**（ID=0），本来就没有名字 | 弹丸 130 / 战备 8 |
| `unknown-has-entry` | **有名字字段、但值是 0**，即"条目还没填名字"（未完成/占位） | 实体 32 |

实体库的 `name_status` 就是这三态；六张表与战备的 JSON 用 `status` / `name_status` 的
`known|unknown` 两态（那些表没有"有条目但空"的情形）。

## 9. 工具

| 工具 | 用途 |
|---|---|
| `table_locid_scan.py` | 扫一张表的每个 4 字节槽，按 `(stride, offset)` 跨组聚合，报告"本地化 ID 命中数 / 去重数 / 样本文本"。两种组头都认（§3），stride 取自 typelib。**发现**名字槽用它 |
| `table_locid_names.py` | 按槽位表把名字倒出来，输出 JSON（`name` / `name_source` / 原始 ID），带文本匹配与大写回退。`--names-only` 输出发布口径（只含名字，不含描述） |
| `explosion_names_from_chain.py` | 投掷物 → 爆炸的引用链命名，输出每个爆炸行的消费方列表（共用关系一目了然） |
| `strings_inventory.py` | 清点 `.strings` 语料：语言分布、每个 bundle 的 distinct 英文 blob 数、ID 并集。**只读文件头 16 字节**，扫 GB 级目录也是秒级 |
| `stratagem_display_names.py` | 战备表专用：五个槽位（大写/显示/描述/长描述/状态）+ wiki 页面匹配 + 死引用回填；`--names-only` 走发布口径 |
| `wiki_match_tables.py` | 把表里的名字和本地 wiki 页面标题对上：精确 / 后缀 / 包含 / 模糊四条规则，输出每张表的覆盖率与未匹配清单（`refs/wiki/name-matches.json`）|
| `plaintext_cache_audit.py` | 检查明文缓存里有没有被我们自己 mod 污染的条目：拿 `refs/dlbin/demo/vanilla_*`（部署前备份）+ 当前 build 两条独立证据交叉查，`--fix` 用原版覆盖 |

复跑（`<sk>` 是你自己的 recipient.sk，仓库不含密钥材料）：

```bash
python -m srkit unpack "<game>/data/bundles.00.nxa" -o refs/strings-probe/all \
    --type strings --no-gpu --no-stream            # 一次就够，语料是全局的
python tools/strings_inventory.py refs/strings-probe/all --show-languages
python tools/table_locid_scan.py --table projectile_settings
python tools/table_locid_names.py --table projectile_settings \
    --table weapon_customization_settings --table customization_armor_sets \
    --table customization_passive_bonuses --table unit_customization_settings \
    --table planet_data --out refs/locid-names.json
python tools/explosion_names_from_chain.py --out refs/explosion-names-chain.json
python tools/stratagem_display_names.py --sk <sk> --strings refs/strings-probe/all \
    --out refs/stratagem-display-names.json
```
