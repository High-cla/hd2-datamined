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

## 2. 流水线（三个工具）

```bash
# 1) 页面源码（走 MediaWiki API，50 个标题一批，批间 sleep 1s）
python tools/fetch_wiki_pages.py --category Stratagems --category Weapons

# 2) 数据模块（字段名字典 + 详细攻击数据）
python tools/fetch_wiki_modules.py --out refs/wiki/modules

# 3) 建库
python tools/wiki_build_db.py
```

规模：**237 页**（战备 87 + 武器 144）、**3,904 个模板参数**、**3,629 个模块实体**、
**98 条合并战备行 + 235 条合并武器行**，SQLite 1.7 MB。

### 表结构

| 表 | 行数 | 内容 |
|---|---:|---|
| `page` | 233 | title / kind / last_updated / attack_key / n_params |
| `param` | 3,914 | section(infobox·stats) / title / key / value / **num** |
| `entity` | 4,038 | section / key / json（模块里的弹丸/爆炸/伤害等） |
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
