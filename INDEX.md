# 索引

> **本仓库唯一索引入口。** [README](README.md) 只讲「这是什么、怎么上手」；所有文档都从这里进。
>
> 当前验证 build **`26088801`** ｜ 历史基线 `25480438` → `25988413`
> **事实类**文档文件名带 build 号，结论只对那个 build 成立；**方法类**不带 build 号，跨 build 有效。
> 每个 build 验证了什么、新 build 到手先跑哪三步 → **[BUILDS.md](BUILDS.md)**。
> 链接自检：`python tools/check_links.py`（0 断链才算过）。

## 0. 三十秒：我该从哪进

| 你是… | 从这进 |
|---|---|
| 想亲手改一张表 | **[改盘上数据的完整工作流](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)** —— 主线文档，8 步链 + 锚点哈希 + 92 条坑 |
| 想让**代理**去做 | **[skills/hd2-file-route-mod](skills/hd2-file-route-mod/SKILL.md)** —— Agent Skills，只给方法论（每步的目的 / 判据 / 停的条件）+ 指回本页 |
| 想查某个字段 / 某个数 | [§1 按问题找](#1-按问题找) |
| 想按类型看全部 33 篇 | [§2 按类型浏览](#2-按类型浏览33-篇) |
| 刚更新完游戏 | [BUILDS.md §3](BUILDS.md) |
| 什么都没有、只想先摸摸 | [§3 无密钥也能练](#3-无密钥也能练) |

## 1. 按问题找

### 动手改东西

| 我想改 | 读 | 关键小节 | build |
|---|---|---|---|
| 战备冷却 / 呼叫时间 / 使用次数 | [STRATAGEM-FIELDS](docs/tables/STRATAGEM-FIELDS-26088801.md) | §2 面板公式 · §5.2 鹰式次数 · §5.3 float32 边界 | `26088801` |
| **Eagle 回收时间** | [STRATAGEM-FIELDS](docs/tables/STRATAGEM-FIELDS-26088801.md) | **§5.4 `EAGLE. REARM` 独立行** | `26088801` |
| 爆炸半径 / 破片数 / 粒子 / 震屏 / 外观移植 | [EXPLOSION-VISUAL](docs/explosions/EXPLOSION-VISUAL-26088801.md) | §1 字段图 · §5 `+0xA8` 跨包加载 | `26088801` |
| 换弹头（整行搬运）/ 换爆炸效果 | [EXPLOSION-PROJECTILE](docs/explosions/EXPLOSION-PROJECTILE-25988413.md) | 全文 | `25988413` |
| 武器数值 / 可选弹种 / 独立弹药池 | [ENTITY-TABLE](docs/tables/ENTITY-TABLE-25988413.md) | §9 | `25988413` |
| 武器配件与槽位 | [WEAPON-CUSTOMIZATION-DECODED](docs/tables/WEAPON-CUSTOMIZATION-DECODED.md) | 全文 | `25988413` |
| 弹幕轮数 / 每轮弹数 / 散布 | [STRATAGEM-FIELDS](docs/tables/STRATAGEM-FIELDS-26088801.md) · [ENTITY-TABLE](docs/tables/ENTITY-TABLE-25988413.md) | §3 散布 · §5 弹幕组件 | `26088801` |

### 理解原理

| 想知道 | 读 | 关键小节 |
|---|---|---|
| 密封盒 / 内容哈希 / 校正字怎么工作 | [DLBIN-SEALED-BOX](docs/engine/DLBIN-SEALED-BOX.md) | §1–§6 · §10 取密钥 · §11 实机验收 |
| `LDLD` 容器 / 组头 / 行起点怎么算 | [WORKFLOW](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) | §3 定位 · §4 保哈希 |
| 每张表的组 / 行 / 步长 / 尾块几何 | [TABLE-DICTIONARY](docs/tables/TABLE-DICTIONARY-25988413.md) | 全表字典 |
| 表里的名字从哪来（locid / `.strings`） | [LOCID-NAMES](docs/tables/LOCID-NAMES-25988413.md) · [ROW-NAMING](docs/tables/ROW-NAMING-25988413.md) · [ENTITY-LOCID](docs/tables/ENTITY-LOCID-26088801.md) | — |
| 实体库 275 个块 / 组件布局 | [ENTITY-TABLE](docs/tables/ENTITY-TABLE-25988413.md) | 全文 |
| 战备 → 弹丸 → 爆炸这条引用链 | [STRATAGEM-REFERENCE-CHAIN](docs/tables/STRATAGEM-REFERENCE-CHAIN-25988413.md) | 全文 |
| 战备表 400 B 行的完整解码 | [STRATAGEM-SETTINGS-DECODED](docs/tables/STRATAGEM-SETTINGS-DECODED.md) | 全文 |

### 密钥与前置

| 想知道 | 读 |
|---|---|
| **只有一份 dump，怎么自己解出密钥**（RVA + XOR 常数 + seek 工具 + 三重验证） | [DLBIN-SEALED-BOX §10](docs/engine/DLBIN-SEALED-BOX.md) |
| 所有密钥来源与各自代价 | [WORKFLOW §1.2.1](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 怎么判盘上是原版（「哈希 == 锚点」识别不出保哈希 mod） | [WORKFLOW §2.5](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 没有密钥能练什么 | [WORKFLOW §2.6](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) · [§3 无密钥也能练](#3-无密钥也能练) |

### 坑与边界

| 想知道 | 读 |
|---|---|
| **92 条坑**（现象 / 规则 / 三态） | [WORKFLOW §10](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 工具的行为陷阱（不报错但会让你误判） | [WORKFLOW §5.2](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) · [tools/README](tools/README.md) |
| 走不通的路：进程内存 / 未签名 DLL / 加载器 | [MEMORY-ACCESS](docs/boundaries/MEMORY-ACCESS-25988413.md) · [LOADER-SPEC](docs/engine/LOADER-SPEC-25988413.md) |
| 虚拟机路线为什么也不行 | [VM-DUMP](docs/boundaries/VM-DUMP-25988413.md) |
| 还缺什么实验 / 哪些字段没找到 | [WORKFLOW §12](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 四条路线横向比较（为什么选盘上数据） | [ROUTES-COMPARE](docs/builds/ROUTES-COMPARE-26088801.md) |

### 换 build 与工具

| 想知道 | 读 |
|---|---|
| 新 build 到手先跑哪三步 | [BUILDS.md §3](BUILDS.md) |
| 这次更新到底把 55 张表改了没 | [BUILD-26088801-DIFF](docs/builds/BUILD-26088801-DIFF.md) |
| 工具清单与各自验证状态（依赖 / 三态） | [tools/README.md](tools/README.md) |
| 游戏内探针怎么写（旧探针为什么"能加载但静默失效"） | [PROBE-AUTHORING](docs/engine/PROBE-AUTHORING-25988413.md) |
| Lua 运行时 / API 面 / `Gui.*` 绘制 | [LUA-API](docs/engine/LUA-API-25988413.md) · [STINGRAY-API](docs/engine/STINGRAY-API-25988413.md) · [GUI-HUD](docs/engine/GUI-HUD-25988413.md) |
| 数据文件路线为什么不需要执行权 | [PATCH-LOADER-DESIGN](docs/engine/PATCH-LOADER-DESIGN-26088801.md) |

### 外部参照

| 想知道 | 读 |
|---|---|
| 别人怎么把内部名接到显示名 | [PRIOR-ART-NAMING](docs/cases/PRIOR-ART-NAMING.md) |
| wiki 里的原始解码数据能补哪些字段 | [WIKI-DATA-MODULES](docs/cases/WIKI-DATA-MODULES.md) · [WIKI-LOCAL-DB](docs/cases/WIKI-LOCAL-DB.md) |
| 社区包怎么做 / 能不能共存 | [CASE-STUDY](docs/cases/CASE-STUDY-20261021.md) · [COMMUNITY-MODS-COMPAT](docs/cases/COMMUNITY-MODS-COMPAT-26088801.md) · [PATCH-SALVAGE](docs/builds/PATCH-SALVAGE-25988413.md) |

## 2. 按类型浏览（33 篇）

| 类别 | 放什么 | 篇数 |
|---|---|---:|
| [`builds/`](docs/builds/) | 每个 build 的总体变化、差异、路线取舍 | 4 |
| [`engine/`](docs/engine/) | 引擎侧：格式封装、API 面、Lua 运行时、探针、加载器 | 9 |
| [`tables/`](docs/tables/) | 数据表与实体库的解码 / 改写 | 9 |
| [`explosions/`](docs/explosions/) | 爆炸与弹头（玩法层 + 外观层） | 2 |
| [`boundaries/`](docs/boundaries/) | 被挡住的路：进程内存、虚拟机 | 2 |
| [`cases/`](docs/cases/) | 案例与外部参照：社区包、贴图委托、wiki 数据、**完整工作流** | 7 |

### `builds/`

| 文档 | 一句话 | build |
|---|---|---|
| [BUILD-25988413](docs/builds/BUILD-25988413.md) | 10-20 更新改了什么：文件身份、代码与资源层、更新后工具链还剩什么能用 | `25988413` |
| [BUILD-26088801-DIFF](docs/builds/BUILD-26088801-DIFF.md) | 7.2.1 hotfix 逐层比对：55 张表一张没变，变的是 exe/game.dll 与 bundle 打包（含一次误报复盘） | `26088801` |
| [ROUTES-COMPARE-26088801](docs/builds/ROUTES-COMPARE-26088801.md) | 战备线与护甲线谁先开：四个判据逐项对照 | `26088801` |
| [PATCH-SALVAGE-25988413](docs/builds/PATCH-SALVAGE-25988413.md) | 22 个旧补丁按资源类型清点：资产只能当原料，外观方向是新活不是抢救 | `25988413` |

### `engine/`

| 文档 | 一句话 | build |
|---|---|---|
| [DLBIN-SEALED-BOX](docs/engine/DLBIN-SEALED-BOX.md) | `.dl_bin` 封装模型：48 B 头 + `crypto_box_seal` + keystream 关系；**§10 用旧 build 转储取密钥** | `25988413` |
| [ENGINE-API-25988413](docs/engine/ENGINE-API-25988413.md) | 内存路全死之后引擎侧还能读到什么，逐条三态 | `25988413` |
| [STINGRAY-API-25988413](docs/engine/STINGRAY-API-25988413.md) | 游戏内 `pairs()` 枚举到的 446 个 Stingray 入口 | `25988413` |
| [LUA-API-25988413](docs/engine/LUA-API-25988413.md) | Lua API 全量面：125 命名空间 / 2,483 成员 | `25988413` |
| [LUA51-TOOLING-25988413](docs/engine/LUA51-TOOLING-25988413.md) | `lua51.dll` 消失后，迁到 stock Lua 5.1 要改哪些工具与判据 | `25988413` |
| [PROBE-AUTHORING-25988413](docs/engine/PROBE-AUTHORING-25988413.md) | 新 build 上怎么写探针；旧探针为什么"能加载但静默失效" | `25988413` |
| [GUI-HUD-25988413](docs/engine/GUI-HUD-25988413.md) | 纯 Lua 自绘屏幕文字：`Gui.*` 真实签名（三次崩溃换来） | `25988413` |
| [LOADER-SPEC-25988413](docs/engine/LOADER-SPEC-25988413.md) | 共享加载器必须满足什么，含 `package.loadlib` + 原生 DLL 的最终否证 | `25988413` |
| [PATCH-LOADER-DESIGN-26088801](docs/engine/PATCH-LOADER-DESIGN-26088801.md) | 数据文件路线不需要执行权：用离线合成器替掉 boot 覆盖 | `26088801` |

### `tables/`

| 文档 | 一句话 | build |
|---|---|---|
| ★ [TABLE-DICTIONARY-25988413](docs/tables/TABLE-DICTIONARY-25988413.md) | **全表字典**：55 张表几何 + 类型库字段偏移（1,208 类型 / 7,349 成员） | `25988413` |
| ★ [ENTITY-TABLE-25988413](docs/tables/ENTITY-TABLE-25988413.md) | 47 MB 实体库离线改写：组件块、哈希闸门、校正字、可选弹种、LoadoutEntry 否证 | `25988413` |
| [ENTITY-LOCID-26088801](docs/tables/ENTITY-LOCID-26088801.md) | 实体 → 游戏内名字的唯一出处（`EncyclopediaEntry`，643 行可解） | `26088801` |
| [LOCID-NAMES-25988413](docs/tables/LOCID-NAMES-25988413.md) | 32 位本地化 ID：`.strings` 全局 ID→文本表怎么打通六张表的名字 | `25988413` |
| [ROW-NAMING-25988413](docs/tables/ROW-NAMING-25988413.md) | 逐行名字的两条取法、判据、以及位置法取错过名的两张表 | `25988413` |
| ★ [WEAPON-CUSTOMIZATION-DECODED](docs/tables/WEAPON-CUSTOMIZATION-DECODED.md) | 武器配件总表：88 B 行、九类槽位枚举、252 行可读导出 | `25988413` |
| ★ [STRATAGEM-SETTINGS-DECODED](docs/tables/STRATAGEM-SETTINGS-DECODED.md) | 战备表 400 B 行 / 12 组解码，含三处旧结论的自我否证 | `25988413` |
| ★ [STRATAGEM-FIELDS-26088801](docs/tables/STRATAGEM-FIELDS-26088801.md) | 战备字段总表：面板公式（先预测后实测）、散布、**Eagle 回收（§5.4）**、条目 ID 重复=崩溃 | `26088801` |
| [STRATAGEM-REFERENCE-CHAIN-25988413](docs/tables/STRATAGEM-REFERENCE-CHAIN-25988413.md) | 战备→弹丸→爆炸：只有弹丸↔爆炸一跳，战备→弹丸是否证 | `25988413` |

### `explosions/`

| 文档 | 一句话 | build |
|---|---|---|
| ★ [EXPLOSION-PROJECTILE-25988413](docs/explosions/EXPLOSION-PROJECTILE-25988413.md) | 玩法层：换弹头整行、改 `+144`/`+156` 换爆炸、改 `+80`/`+84` 加破片 | `25988413` |
| ★★ [EXPLOSION-VISUAL-26088801](docs/explosions/EXPLOSION-VISUAL-26088801.md) | 外观层：粒子 `+0x38`、震屏 `+0x28`、整行克隆、`+0xA8` 纯数据跨包加载 | `26088801` |

### `boundaries/`

| 文档 | 一句话 | build |
|---|---|---|
| [MEMORY-ACCESS-25988413](docs/boundaries/MEMORY-ACCESS-25988413.md) | EAC 剥掉 `PROCESS_VM_READ`、`ffi` 消失、DLL 加载两道闸门的实测 | `25988413` |
| [VM-DUMP-25988413](docs/boundaries/VM-DUMP-25988413.md) | 虚拟机路线：宿主读 guest 内存已证实，过不了 EAC 的虚拟机检测 | `25988413` |

### `cases/`

| 文档 | 一句话 | build |
|---|---|---|
| ★ [FILE-ROUTE-WORKFLOW-26088801](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) | **知识库主管线**：完整 8 步链、4 张表锚点、宿主三选（含三次崩溃归因）、**92 条坑**、EAGLE 双行案例、未决清单 | `26088801`（流程跨 build） |
| [CASE-STUDY-20261021](docs/cases/CASE-STUDY-20261021.md) | 三个社区包拆出来的路：`.patch_N` 能替换任意资源类型，纯资产 mod 不需要 loader | `25988413` |
| [TEXTURE-SWAP-10X-APEX](docs/cases/TEXTURE-SWAP-10X-APEX.md) | 一次贴图替换委托：BC1 往返误差、材质槽判定、`patch_3` 部署与回滚 | 跨 build |
| [COMMUNITY-MODS-COMPAT-26088801](docs/cases/COMMUNITY-MODS-COMPAT-26088801.md) | SSEO 与护甲多被动为何不能共存：争的是同一文件的基线所有权 | `26088801` |
| [PRIOR-ART-NAMING](docs/cases/PRIOR-ART-NAMING.md) | 别人怎么把内部名接到显示名/页面（filediver / HD2Runtime / wiki），我们该借哪个 | 跨 build |
| [WIKI-DATA-MODULES](docs/cases/WIKI-DATA-MODULES.md) | wiki `Module:` 命名空间里的原始解码数据清单，能补哪些字段名 | 跨 build |
| [WIKI-LOCAL-DB](docs/cases/WIKI-LOCAL-DB.md) | 不抓 HTML：页面源码 + JSON 模块落本地 SQLite，一条命令查战备/武器全貌 | 跨 build |

## 3. 无密钥也能练

不需要游戏、不需要密钥就能跑通「解析 → 改字节 → 过门禁 → 核哈希」这几件事：

| 资产 | 内容 |
|---|---|
| [`tables/`](tables) | 三张很小的明文参数表（projectile 96,604 B / damage 50,336 B / weapon_customization 30,824 B，合计 ~180 KB） |
| [`refs/table-geometry.json`](refs/table-geometry.json) | 55 张表的 stride / 行数 |
| [`refs/exports/`](refs/exports) | 战备 / 爆炸 / 弹丸等表的逐行 CSV（组 / 行 / 内部名 / 偏移值） |
| [`refs/dl-type-names.txt`](refs/dl-type-names.txt) | 类型哈希 → 名字 |
| [`refs/entity-block-types.json`](refs/entity-block-types.json) | 275 个组件块类型名 |

配方：[WORKFLOW §2.6](docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) —— 用 `plain_edit.py` 真跑出完整 G1–G6（锚点 `946A4FE5FAAAE076`）。

## 4. 能力明细

| 能力 | 状态 |
|---|---|
| 解开 `data/game/*.dl_bin`（`crypto_box_seal` 形态）并还原明文 | ✓ 工具可跑（需自备密钥，见 [DLBIN-SEALED-BOX §10](docs/engine/DLBIN-SEALED-BOX.md)） |
| 还原**内容哈希闸门**（MurmurHash64A + 校正字），改完字节仍过校验 | ✓ 已实机 |
| `generated_entities`：组件块布局 / hashmap / 行结构 | ✓ 已实机 |
| 武器数值：人机、站姿惩罚、散布、后坐、装填可移动 | ✓ 已实机 |
| **可选弹种**：`fnid=8` + 备选弹丸（伤害 + 状态切换） | ✓ 已实机（眩晕 / 燃烧） |
| **独立弹药池**：`fnid=4` + `WeaponRounds` 两套弹丸 | ✓✓ 已实机（仅限原生有该行的 25 把） |
| **爆炸/弹头**：换弹头整行 · 换爆炸（`+144`/`+156`）· 加破片（`+80`/`+84`） | ✓✓ 已实机 |
| **爆炸视觉 + 跨包加载**：整行克隆供体爆炸 · `+0xA8` 任意外观可移植 | ✓✓ 已实机（`26088801`） |
| 战备：呼叫 / 冷却 / 散布 / 使用次数 / 弹幕轮数与每轮弹数 / **Eagle 回收时间** | ✓✓ 已实机（`26088801`） |
| 全表字典：55 张表几何 + 1,208 类型字段偏移 | ✓ 离线可复现 |
| 自制伤害行（占无主行，写伤害 / 穿甲 / 状态强度） | ✓ 离线门禁通过 |
| 解锁未发布物品（`LoadoutEntry.selectable`） | ✗ 已否证（发布数据里没有这个开关） |

## 5. 已验证的核心结论

> 这些**在 `25988413` 上做的实机 / 离线验证**；结构层部分（密封盒、闸门算法、块布局、行命名、本地化 ID）在 `26088801` 上已复验仍成立。
> **每个具体偏移都必须按 [BUILDS.md §3](BUILDS.md) 在你自己的 build 上重验一遍。**

1. **闸门**：`data/game/*.dl_bin` 的明文被 `game.dll` 里烘焙的 MurmurHash64A 校验（seed `0xDEADBEEFABAD1DEA`），不匹配就 `0xC000000D`。**解法**：改完字节后在一个语义惰性的 8 字节对齐字里解出「校正字」，让哈希回到原值 —— 长度不变、校验通过。
2. **实体库不是 toc，是块序列**：`u32 type ｜ LDLD ｜ ver ｜ type ｜ payload ｜ …`（28 B 头）；组件块 payload = `[hashmap][行数组]`；hashmap 键 = `Murmur64A(资源路径)`。
3. **可选弹种两格**：`WeaponData +184`（`function_id`，**8 = 原生 ProgrammableAmmo**）＋ `ProjectileWeapon +576`（**备选弹丸 type id**）。备选弹**只贡献伤害 + 状态**，弹道来自主弹行。
4. **独立弹药池**：`WeaponRoundsComponentData`，行内 `+64` 两个弹丸 id / `+72` 两个弹匣容量 / `+80` 两个备弹。全表 25 把里只有 SG-20 Halt 是 B≠A，也正好只有它是 `fnid=4`。正向配方与边界见 [ENTITY-TABLE §9](docs/tables/ENTITY-TABLE-25988413.md)。
5. **未发布物品**：`LoadoutEntryComponentData` 只有 `{id, type, dlc_pack_id, equipment_tags[5]}` 32 字节，**没有 selectable**；带 selectable 的结构在发布数据里 0 命中 ⇒ 不是离线可翻的开关。

## 6. 三态标记与自检

| 标记 | 含义 |
|---|---|
| `✓ 实机` | 进游戏看过，且「账本 + 盘上回读 + 进程状态」三件套齐全 |
| `✓ 离线` | 只读解析 / 离线复跑，不启动游戏 |
| `✗ 否证` | 试过、不通，写清失败形态 |
| `⚠ 未证` | 有推理或部分证据，没上机 / 没分辨 —— **不许**当结论用 |

- **改完文档**：`python tools/check_links.py`（0 断链才算过；`../` 层数写错会逃出仓库根，检查器**静默跳过**）。
- **加新文档**：在 §2 对应目录表里加一行；若它回答了某个「我想…」，同时在 §1 加一行。
- **换 build**：更新本文顶部的「当前验证 build」，并按 [BUILDS.md §3](BUILDS.md) 复验锚点。
