# 本地 wiki 数据库（不抓 HTML，抓页面源码 + 数据模块）

> 目的：把 wiki 上分散在 200 多页里的数据落成本地 SQLite，一条命令就能查，而不是每次开浏览器。
> 结论先说：**不需要抓 HTML**。页面上的大表是 Lua 模块用 key 从 JSON 模块现算出来的，
> 抓 HTML 反而会把结构丢掉。

## 1. 为什么是"页面源码 + 模块"，不是 HTML

一份战备页的源码长这样：

```
{{Infobox Stratagem
 | permit_type = Offensive | unlock_level = 8 | base_cooldown = 240s | ... }}
{{Stratagem Stats Table
 | call_time = 8.45 | uses = Unlimited | cooldown = 240 | cooldown_upgraded = 216 }}
{{Attack_Data_Stratagem|ORBITAL 380MM HE BARRAGE}}   ← 那张详细表是模块用这个 key 算的
```

* **数字在页面源码里是明文模板参数**（`cooldown = 240`、`call_time = 8.45`）；
* **详细的弹丸/爆炸/伤害表由模块按 key 生成**，数据来自 `Module:Decodedata-Attacks/*.json`。

渲染出来的 HTML 表格是这两层的 **JOIN 结果**。分层存下来，join 随时可重做，也能直接和我们的
解密表对照；抓 HTML 则只能得到 join 后的死数据，拿不到 key。

## 2. 流水线（四个工具）

```bash
# 1) 页面源码（走 MediaWiki API，50 个标题一批，批间 sleep 1s）
python tools/fetch_wiki_pages.py --category Stratagems --category Weapons
python tools/fetch_wiki_pages.py --category Armor --category Planets --category "Armor Passives"
#    分类里没有但确实存在的页面，可以按标题补抓：--titles "A,B" / --titles-file list.txt

# 2) 数据模块（字段名字典 + 详细攻击数据）
python tools/fetch_wiki_modules.py --out refs/wiki/modules

# 3) 建库
python tools/wiki_build_db.py

# 4) 把表里解出来的名字和页面标题对上，量化覆盖率（精确/后缀/包含/模糊四条规则）
python tools/wiki_match_tables.py
```

规模：**763 页**（战备 87 + 武器 145 + 护甲 114 + 披风 79 + 外观 15 + 护甲被动 32 + 星球 280）、
**9,312 个模板参数**、**3,629 个模块实体**、**98 条合并战备行 + 235 条合并武器行**，SQLite 2.3 MB。

### 页面种类（`page.kind`）

`kind` 来自页面用的信息框模板，所以"某类页面有没有抓到"可以直接用 SQL 查：

| kind | 页数 | 模板 |
|---|---:|---|
| `stratagem` | 87 | `Infobox Stratagem` |
| `weapon` | 145 | `Infobox Weapon` / `Infobox_Weapon` / `Infobox Support Weapon` / `Infobox Throwable` |
| `armor` | 114 | `Infobox Armor` |
| `cape` | 79 | `Infobox CapeCard` |
| `cosmetic` | 15 | `Infobox Cosmetic` |
| `armor-passive` | 32 | `Infobox Armor Passive` |
| `planet` | 280 | `Infobox Planet` |

两个解析坑（都会造成"页面抓到了却没算进去"的假阴性）：`find_template` 是子串匹配，
`Infobox Armor` 会吞掉 `Infobox Armor Passive`（更长的模板名必须排前面）；
模板名**大小写不敏感**，wiki 上确实有 `{{infobox Planet` 这种小写写法。

### 表结构

| 表 | 行数 | 内容 |
|---|---:|---|
| `page` | 763 | title / kind / last_updated / attack_key / n_params |
| `param` | 9,312 | section(infobox·stats) / title / key / value / **num** |
| `entity` | 3,629 | section / key / json（模块里的弹丸/爆炸/伤害等） |
| `stratagem` | 98 | key / json（战备合并视图，含 `attacks` 攻击树） |
| `weapon` | 235 | key / json（武器合并视图，同样含 `attacks`） |

`param.num` 是额外抽出来的数字，所以 `{{Damage|Ballistic|90}}` 既能保留原文，也能按 90 查。

## 3. 能查什么

```bash
# 一条战备的全貌 + 解析出的攻击链 + 与我们的解密表并排对照
python tools/wiki_query.py --stratagem "Orbital 380mm HE Barrage" --sk <你的>/recipient.sk

# 某个参数的所有取值（例：许可类型分布）
python tools/wiki_query.py --field permit_type

# 某个攻击实体的全部字段
python tools/wiki_query.py --entity S_P22_IE

# 武器页（同一套命令）
python tools/wiki_query.py --page "AR-23 Liberator"
python tools/wiki_query.py --page "A/AC-8 Autocannon Sentry"

# 任意 SQL
python tools/wiki_query.py --sql "SELECT title,num FROM param WHERE key='cooldown' ORDER BY num DESC LIMIT 5"
```

实测输出（380mm 弹幕，与 wiki 页面逐个数字一致）：

```
[stats]  call_time=8.45  call_time_upgraded=7.45  uses=Unlimited  cooldown=240  cooldown_upgraded=216
[attack data key] ORBITAL 380MM HE BARRAGE
  projectile S_P22       caliber=406, pellets=1, velocity=400, mass=30000, gravity=1, lifetime=0
  explosion  S_P22_IE    r1=4, r2=12, r3=18
[our table] 'ORBITAL. 380MM HE BARRAGE' type=128 cooldown=240 call-in=6 uses=inf cell=4
```

### 3.1 武器侧的两个坑（已处理）

* **key 大小写不统一**：模块里有的写 `AR-23 Liberator`，有的写 `40-K MELTAGUN`，页面参数又是
  第三种写法（`AR-23 LIBERATOR`）。所以攻击键查找一律按**大小写不敏感**匹配，命中后打印真实
  表内 key 供核对。
* **标题里的斜杠会被文件名吃掉**：`A/AC-8 Autocannon Sentry` 存成文件时 `/` 变 `_`，
  直接反推标题会得到 `A AC-8 Autocannon Sentry`。`fetch_wiki_pages.py` 现在同时写
  `_titles.json`（文件名 → 真实标题），`wiki_build_db.py` 优先用它，标题不再失真。

武器页实测（AR-23 Liberator）：

```
[infobox] damage={{Damage|Ballistic|90}}  capacity=45  fire_rate=640 rpm  dps=960  spare_mags=8
[attack data key] AR-23 LIBERATOR   -> weapon table key 'AR-23 Liberator'
  [merged] burst=3, cap=45, capplus=1, category=Assault Rifle, ergonomics=65, mags=8, recoil=15
  projectile Rifle_5.5x50mm_fmj   caliber=5.5, pellets=1, velocity=900, mass=4.5, drag=0.3
```

哨戒类（嵌套武器）也能下钻：

```
A/AC-8 Autocannon Sentry -> AUTOCANNON SENTRY
  [merged] cooldown=150, health=400, armor=2, rpm=160, turn_hori=20, turn_vert=20
  weapons  AUTOCANNON SENTRY    health=400, armor=2, barrels=1, turn_speed_*=20
```

## 4. 第一次跨源对账的结果

### 4.1 冷却：15/15

把页面 `stats.cooldown` 与我们解密表的 `+104` 对比，**15 条全中**——但要用对页面字段：
Eagle Rearm 页面写的是 `cooldown = 0` + `rearm_time = 150`，而我们的 `+104 = 150`。
即**我们的 `+104` 是"这个战备的冷却"，而 Eagle Rearm 在 wiki 上把它叫 rearm_time**。

### 4.2 页面 `call_time` ≠ 我们的 `+84`（两个不同的量）

| 战备 | 页面 call_time | 我们 `+84` | 差 |
|---|---:|---:|---:|
| Orbital 380mm HE Barrage | 8.45 | 6 | 2.45 |
| Orbital Airburst / Gas / Precision / Smoke | 4.45 | 2 | 2.45 |
| Orbital Walking | 5.45 | 3 | 2.45 |
| Orbital Napalm Barrage | 7.45 | 5 | 2.45 |
| Orbital Gatling | 3.05 | 2 | 1.05 |
| Eagle Airstrike / Gas / Napalm | 4.10 | 0 | 4.10 |
| Eagle 500kg | 3.45 | 0 | 3.45 |
| Eagle 110mm Rocket Pods | 3.40 | 0 | 3.40 |
| Orbital Laser / Eagle Rearm | 2 / 0 | 2 / 0 | 0 |

差值不是常数（2.45 / 4.10 / 3.45 / 1.05 / 0），说明页面那个是**观测到的"按下到落地"总时长**
（含信标布设与飞行），而 `+84` 是设置表里的呼叫延迟。两者不是同一个量，**不能互相校验**。

### 4.3 命名覆盖率：只有 15/233

页面标题用的是 `Orbital 380mm HE Barrage` 这种正式名，我们表里的显示名是
`ORBITAL. 380MM HE BARRAGE`；**只有轨道/鹰式两族能对上**（15 条）。其余战备（背包、支援武器、
哨戒等）我们的内部名与 wiki 标题不同名，所以这个库目前主要服务于轨道/鹰式这条线。

## 4.4 注意：`[merged]` 里的数来自不同模块

合并行是"同一 key 在多个模块里出现时，字段最多的那条胜出"。所以 `[merged]` 展示的是字段全集，
个别数值可能来自不同 build。要校准时以页面参数（`[infobox]`/`[stats]`）和我们自己的解密表为准。


## 4.5 别名表：让 38 条战备也能和我们的表对照

页面标题（`B-1 Supply Pack`）与我们内部显示名（`BACKPACK. SUPPLY BACKPACK`）不同名，所以按名字
只能对上 15 条。别名表换了一个**不依赖显示名**的桥：

```
行内 +24 指针 -> 本地化键 nui_stratagem_backpack_ammo_name  ->  slug  backpack_ammo
                    HD2Runtime 的 uiIcon.nativeType = AmmoBackpack（= wiki 的 ref，38/42 已验证相等）
                        ->  catalog 里的战备名 == wiki 页面标题
```

| 匹配档 | 规则 | 条数 |
|---|---|---:|
| `nativeType-exact` | slug 与 nativeType 小写化后相等 | 34 |
| `token-set` | 驼峰拆分后词集合相等，能接住词序反转（`backpack_ammo` ↔ `AmmoBackpack`） | 4 |
| 歧义 | 同一 slug 命中多条 catalog | 0 |

产物：`refs/stratagem-alias.json`（38 条，含 method 与原始字段）。工具
`tools/build_stratagem_alias.py`；`wiki_query.py --sk` 会自动用它兜底。

**想突破 38 条**：查过社区做法（见 `PRIOR-ART-NAMING.md`），没有现成的"内部名 ↔ wiki 名"
映射表；正解是解游戏自己的 strings 资源（`nui_*` 键 → 游戏内显示名 → wiki 标题），
那样能覆盖全部 128 条带键的行。

**为什么停在 38**：catalog 只映射 96 个战备，我们的 153 行里只有 128 行带本地化键
（25 行没有，90 行的 slug 在 catalog 里无对应）。再往下就得靠猜——而错一条别名会让之后所有
`--sk` 对照都错，所以到此为止。

### 独立验证：玩法数值

别名表是用"本地化键 ↔ 类型名"建的，可以用另一个维度验证——把 38 条页面的
`stats.cooldown` / `stats.uses` 与我们的 `+104` / `+80` 对比：

| 字段 | 一致 | 不一致 |
|---|---:|---|
| 冷却 | **34/35** | 1 |
| 使用次数 | **34/35** | 1 |

唯一不一致的是 `PRESIDENT REWARDS. ROCKET SENTRY` → `A/MLS-4X Rocket Sentry`：
我们冷却 **45**，页面 **150**。这更像"总统奖励变体"的真实数值差异（而不是错配），
因为同一条别名的使用次数是对得上的。

（35 而非 38，是因为 3 条页面的 `cooldown` 参数为空或走 `rearm_time`。）

## 5. 授权与礼貌

* `helldivers.wiki.gg/robots.txt`：`User-agent: * / Allow: /`，但**明确屏蔽**了 GPTBot、
  ClaudeBot、anthropic-ai、CCBot、Bytespider 等 AI 训练爬虫（内容信号里也声明了 ai-input/ai-train）。
  本工具是以普通浏览器 UA、为用户本地研究缓存的用途抓取，批量 50 页/请求、批间 sleep。
* wiki 内容为 CC BY-SA。**本仓库不分发这些内容**：`refs/wiki/.gitignore` 忽略了 `pages/`、
  `modules/`、`wiki.sqlite`、`*.raw`，只提交工具与本文档。
* 唯一随仓库分发的是 `refs/wiki/stratagemdata.json`（55 KB，攻击链工具的默认输入）。

## 6. 刷新

页面 `{{Last Updated|1.007.000}}` 已存进 `page.last_updated`，可以直接查哪些页过期了：

```bash
python tools/wiki_query.py --sql "SELECT last_updated, COUNT(*) FROM page GROUP BY 1 ORDER BY 1 DESC"
```
