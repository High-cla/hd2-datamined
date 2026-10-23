# Build 索引：每个 build 验证了什么、哪些结论还能直接用

本仓库**不绑定某一个 build**。热点更新一到两周一次（三天内就从 `25480438` 走到 `25988413`
再到 `26088801`），所以：

* **仓库名 / 工具 / 方法论文档** 不带 build 号 —— 它们跨 build 有效；
* **事实类文档** 文件名带 build 号（`docs/xxx-25988413.md`）—— 里面的偏移、地址、实测结论
  只对那个 build 成立；
* 每确认一个新 build，先跑下面的三步，再决定哪些旧结论需要重写。

## 1. 已验证的 build

| build | 日期 | 状态 | 关键结论 / 差异 | 对应文档 |
|---|---|---|---|---|
| **26088801** | 2026-10-22 19:59（steamdb 11:59 UTC） | **当前** | 密钥未变（56/56 解封）；类型库明文逐字节相同；**55 张表 0 变化**（22 张明文全同、33 张结构全同）；exe/game.dll 同大小、哈希变；`bundles.nxa` +151 B，5 个 bundle ±64 KB。⚠ 该 build 曾一度被误报"改了一张表"，实为我们自己的 mod 负载污染基线缓存（见 §6） | [BUILD-26088801-DIFF.md](docs/builds/BUILD-26088801-DIFF.md) |
| 25988413 | 2026-10-20 | 历史基线 | 本仓库绝大多数 `-25988413` 文档的实测版本：内容哈希闸门、实体块布局、可选弹种、独立弹药池、爆炸/弹头线、行命名、本地化名、战备/武器表解码 | `docs/*-25988413.md`、`refs/table-geometry.json` |
| 25480438 | 2026-10-15 | 更早 | 仅本地备份，**不收录**（结论已过时会误导） | — |

## 2. 哪些结论跨 build，哪些必须逐 build 复验

分清这三层，能省掉大半无效工作：

| 层 | 例子 | 跨 build？ |
|---|---|---|
| **结构 / 格式** | `.dl_bin` 密封盒（`明文+48 B`）、内容哈希（MurmurHash64A, seed `0xDEADBEEFABAD1DEA`）、`LDLD` 组头（数组型 `0x10|count` 与单记录型两种）、实体块序列与 hashmap 键、`.strings` 格式与 `ThinHash`、行内「本地化 ID」机制、行命名（指针 vs 位置） | ✓ 跨 build（25988413 → 26088801 实测不变，密钥也没变） |
| **字段 / 偏移** | 「战备 `+104` 是冷却」「弹丸 `+8` 是显示名 ID」「实体 `+576` 是备选弹丸」 | ⚠ 必须逐 build 复验：类型库逐字节一致才敢直接复用，否则重跑字段定位 |
| **地址 / 常量 / 补丁码** | RVA、内存地址、注入点、patch 字节 | ✗ 基本每 build 必变，必须重新推导 |

## 3. 新 build 到手后的三步（全离线，不启动游戏）

```bash
# 0) 先确认基线缓存干净 —— 否则后面两步全错（这个坑真的踩过，见 §6）
python tools/plaintext_cache_audit.py --sk <recipient.sk>  # -> refs/cache-audit.json

# 1) 把当前 build 的 55 张表 + 类型库解封成明文，按 buildid 另存
python tools/build_cache.py --sk <recipient.sk>          # -> refs/dlbin/plaintext-<buildid>/

# 2) 逐表回答"变了没"：文件层 -> 封装层（比明文哈希）-> 结构层（组数/行数/步长）
python tools/build_diff.py --sk <recipient.sk>            # -> refs/build-diff.json

# 3) 用旧 build 的字典几何对照全部 55 张表（没旧明文的表也能证到"结构没变"）
python tools/build_geometry_diff.py --sk <recipient.sk>   # -> refs/build-geometry-diff.json
```

判读规则：

* `changed = 0` 且密钥仍能解 → 现有工具与文档的**结构层**结论可以直接用；
* 只要有一张表 `changed` → 那张表的行号/偏移全部作废，重跑 `tools/table_dictionary.py`
  与对应的定位工具；
* `structure-same` 只证明"大小 + 组数"没变，**不能排除同尺寸下的数值改动**。

## 4. 基线产物放在哪

| 文件 | 是什么 | 属于哪个 build |
|---|---|---|
| `refs/table-geometry.json` | 55 张表的几何（明文大小 / 组数 / 行数 / 步长 / 类型） | 25988413（26088801 实测结构全同，故仍是有效基线） |
| `refs/build-diff.json` | 某一次「旧 → 新」的逐表 diff | 25988413 → 26088801 |
| `refs/build-geometry-diff.json` | 55 张表对旧几何的对照结果 | 26088801 |
| `refs/dlbin/plaintext-<buildid>/` | 该 build 的解封明文（本地，不入库） | 按目录名 |

build 再多起来时，按 `refs/builds/<buildid>/` 分目录，把上述产物各存一份。

## 5. 命名约定

* 事实类文档：`docs/<主题>-<buildid>.md`，开头写清"本文所有偏移/地址均在该 build 实测"。
* 方法类文档：不带 build 号（如 `docs/DLBIN-SEALED-BOX.md`、`docs/PRIOR-ART-NAMING.md`）。
* 报告类：`docs/BUILD-<buildid>-DIFF.md`，只写这次更新相对上一个基线变了什么。

## 6. ⚠ 踩过的坑：明文缓存会被我们自己的 mod 污染

`refs/dlbin/plaintext-all/` 是"某个 build 的原版明文"。只要有一次 dump 发生在
**我们的 mod 已经写进 `data/game` 之后**，缓存里就会混进改过的表 —— 之后所有
"这张表变了没"的判断全错，而且错得很有说服力。

**实例（2026-10-22）**：09:49 我们为"护甲多被动"实验备份了原版并生成了 mod 负载，
09:52 的 dump 把**deployed 的负载**当成了原版存下（`customization_passive_bonuses`
4992 B，真原版 4016 B）。3.5 小时后的 20:56 游戏更新到 26088801，于是被误报成
"这次更新改了一张表"。实际上原版两个 build 逐字节相同，这次更新**一张表都没动**。

铁证是两份文件并存（都在本机）：`refs/dlbin/demo/vanilla_generated_customization_passive_bonuses.dl_bin`
（4016，`6ba67061fa05b1aa…`）与 `refs/dlbin/demo/passives_medkit.sealed.dl_bin`
（4992，`ca5b6b33dfe0b4b6…`），而旧缓存的 sha256 与后者完全一致。

**规则**：
1. dump 前确认 `data/game` 是原版（有 `refs/dlbin/demo/vanilla_*` 备份的直接比对）；
2. dump 后立刻跑 `tools/plaintext_cache_audit.py`；
3. 改表实验的负载一律留在 `refs/dlbin/demo/`，**永远不要**写进缓存目录。
