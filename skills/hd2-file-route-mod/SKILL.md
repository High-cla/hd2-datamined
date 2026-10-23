---
name: hd2-file-route-mod
description: |
  【方法论型技能】改 Helldivers 2 **盘上数据表**的顺序、判据与停的条件：解封 data/game/*.dl_bin → 定位字段 → 写入并保住引擎内容哈希 → 过门禁 → 重封 → 从游戏目录回读 → 分级实机验证 → 记账/回滚。改的是磁盘数据文件，持久生效；不碰进程内存、不需要 Lua/FFI/注入/DLL。
  ⚠ 本技能**不承载知识库**：字段偏移、面板公式、坑清单与能力边界全部在仓库 hd2-datamined 里，本文件只给方法论与指针（见 §7 → 仓库 `INDEX.md`）。
  Use when 用户说「改战备冷却 / 使用次数 / 呼叫时间」「改爆炸半径 / 破片 / 外观」「改武器或实体表数值」「把改过的表装进游戏」「离线数据 mod」「dl_bin 改不动」「启动 0xC000000D」「game.dll+0x1083a45 崩溃」「LDLD」「校正字」「seal-key」。
  载体分工（本技能只做第四种）：hd2-mod-maker = 运行期 Lua `.patch_N` 补丁；hd2-value-editor = 运行期进程内存；srkit-resources = Stingray 资源包；本技能 = **盘上明文数据表**。
license: MIT
compatibility: Windows · Python 3.11+ · PyNaCl（仅解封/重封）· 需自备 recipient.pk / recipient.sk（**可从一份旧 build 全量转储自行解出**，见 §7 索引 → DLBIN-SEALED-BOX §10）· 部署前必须退出游戏
metadata:
  domain: hd2-data-tables
  kind: methodology
  knowledge-base: https://github.com/deepseekv41flash/hd2-datamined
  tools: build_cache.py, dlbin_seal.py, dump_read_rva.py, murmur64.py, plain_edit.py, stratagem_tune.py
---

# HD2 改盘上数据的 mod · 方法论

> **分工**：本文件只答三件事——「**现在该做什么**」「**怎么算做对了**」「**什么时候停**」。
> 「这个字段是什么」「那个坑是什么」「这条路走到哪为止」全在仓库知识库里，§7 给了逐条指针。
>
> **一条硬规矩**：本技能与仓库文档冲突时 **以仓库为准**。技能会滞后，仓库是唯一真值源。
> 所以换 build、发现新字段、踩到新坑 —— **只改仓库，不改这里**。这正是本技能的容量能一直很小、且永不腐坏的原因。

## 0. 先选对载体（选错，后面全白做）

| 技能 | 载体 | 生命周期 | 定位方式 | 回滚 |
|---|---|---|---|---|
| `hd2-mod-maker` | `.patch_N` 三件套 | 加文件即生效 | 模块路径 → murmur64 | 删文件 |
| `hd2-value-editor` | 进程内存 | 重启即复原 | id / position 行 | 重启 |
| `srkit-resources` | Stingray 资源包 | 叠层优先级 | 资源 id | 不写游戏目录 |
| **本技能** | `data/game/*.dl_bin` 单文件 | **持久，重启不还原** | **文件绝对偏移 + 行步长** | **备份 + 账本 + 核哈希** |

三句话判据：**会话内临时**改数值 → `hd2-value-editor`；**持久**且只改数值 / 引用 → 本技能；改资源本体（模型 / 贴图 / 粒子 / lua）→ `srkit-resources` 或 `hd2-mod-maker`。
⚠ 两者会互相打架：运行期 mod 若写同一字段的进程内存，会盖掉盘上值。

**不重复**：模块命名与 patch 索引、离线测试套件、`srkit` 解包与往返、内存三守卫、侦察报告骨架 —— 一律见上述技能，本文只给指针。

## 1. 三个必须先切断的混淆点

| 说法 | 本技能里的意思 | 不是 |
|---|---|---|
| **封装** | `tools/dlbin_seal.py seal-key`（`crypto_box_seal`：epk 32 ‖ tag 16 ‖ ciphertext，产物 `*.dl_bin`） | `srkit pack` 的资源打包（产物 `.patch_N`）。产品名也不同 |
| **murmur64** | 内容闸门 `MurmurHash64A(明文)` → `tools/murmur64.py` / `murmur64a.py` | `srkit hash` 算的是资源 id（路径哈希）。同名不同种，混用得到「另一个哈希」且**不报错** |
| **`data/game/`** | 55 张 `.dl_bin` + `dl_library.dl_typelib` + `game.dll`，松散加密文件 | `data/*.patch_N` 叠层包。改 `.dl_bin` 用不到 srkit，srkit 也读不懂它；`.patch_N` **覆盖不了**它（✗ 否证） |

## 2. 开工前七项检查（缺一条就停）

| 检查 | 一句话判据 | 细节 |
|---|---|---|
| 密钥 | 有 pk 能封、有 sk 能解；**必须是游戏内置那一对**（自造一对命令全通、进游戏失败） | → [DLBIN-SEALED-BOX §10](../../docs/engine/DLBIN-SEALED-BOX.md)（含「只有 dump 也能自己解」的完整配方 + 三重验证） |
| build 对得上 | 明文哈希 == 本 build 锚点 | → [BUILDS.md](../../BUILDS.md) §3 · [WORKFLOW](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) §3 |
| 游戏已退出 | 表在**启动时**读入，运行中替换会读到半份 | — |
| 盘上是原版 | 没装过自己的 mod，或先 restore | → [WORKFLOW](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) §2.6（缓存污染） |
| 已备份 | 每张要动的表一份 sha256 | → WORKFLOW §9 |
| Python 3.11+ / PyNaCl | `python -c "import nacl"` | `pip install pynacl`（只在解封/重封需要） |
| 磁盘 | 实体表 47 MB ⇒ 备份 + 明文留 ~120 MB | 先拿小表把链路做通 |

## 3. 十步链路

每步四件事：**目的 / 合格判据 / 停的条件 / 细节在哪**。Step 0–10 的顺序**不能调换**。

### Step 0 · 选表

- **目的**：先按语义选表，再谈偏移。
- **判据**：目标字段有出处（字段图 / 逐行 CSV / 类型库字段树），**不是猜的**。
- **停**：目标只能靠「面板上看不见」猜 ⇒ 先去 Step 2 找一个**可证伪的预测**，不要先改字节。
- **细节**：→ [WORKFLOW §3](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) · 选表索引见 §7。

### Step 1 · 取明文

- **目的**：拿到与本 build 对应的**原版**明文 + typelib。
- **判据**：三个自检全过 —— ① 密文 − 48 = 明文 ② 能逐组解析 `LDLD` ③ 哈希 == 本 build 锚点。
- **停**：哈希对不上只有三种原因（build 不是这个 / 解到了自己的 mod 负载 / `--key` 用错），逐个排除，**不要往下走**。
  ⚠ **哈希对上 ≠ 盘上是原版**：保哈希 mod 改过的明文哈希仍等于锚点（这就是本路线的原理），判原版要靠封包字节数或装前备份。
- **细节**：→ [WORKFLOW §2](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)（两条路 + 锚点表 + 「没有密钥也能练什么」）。

### Step 2 · 定位字段

- **目的**：把「我要改的东西」落成 `(表, 行, 偏移, 类型)` 四元组。
- **三条手段，只有最后一条能定案**：typelib stride（给几何不给语义）→ 内部名（给行身份）→ 绝对偏移（最快，最脆）。
- **判据（定案仪式四步，缺一不可）**：① 找一个只与假设自洽的分布 → ② **写下具体预测** → ③ 只改一个字段 → ④ 读另一个可读数。
  命中才算定案；**不中说明假设错，不是「没生效」**。
- **停**：找不到能解释整列的候选，或该区域没有 8 对齐空位 ⇒ 先解决宿主（Step 3），别硬改。
- **细节**：→ [WORKFLOW §3](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) · [TABLE-DICTIONARY](../../docs/tables/TABLE-DICTIONARY-25988413.md)（全表几何 + 字段树）。

### Step 3 · 写入 + 保哈希

- **目的**：改值的同时让整块 `MurmurHash64A` 回到原值（否则 `0xC000000D`）。
- **判据**：只改声明字段；校正字落在 8 对齐的**语义惰性字**；容器仍能重新解析。
- **红线**：校正字**绝不落记录行**（会崩）；**一次改完再封** —— 所有字段放进同一次运行、封装、部署。
- **细节**：→ [WORKFLOW §4](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)（tail 宿主六步 / 值语法 / 工具分工）· [DLBIN-SEALED-BOX](../../docs/engine/DLBIN-SEALED-BOX.md)（原语）。

### Step 4 · 门禁

- **目的**：拦住「顺手改到别处」和「自己骗自己」。
- **判据**：工具全 PASS，**且报「全过」时必须点名工具、点名是 7 行还是 8 行**。
- **认知**：门禁全绿 **≠ 功能生效**；G3 是「相对原版不变」，不是「等于引擎期望值」（seed 换了会全绿而实机拒）。
- **细节**：→ [WORKFLOW §5](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)（G1–G7 各防什么 + 四类局限）。

### Step 5 · 重封

- **目的**：`crypto_box_seal` 到游戏内置接收方公钥。
- **判据**：封包 = 明文 + 48 B。不成立 ⇒ 封错了文件，回 Step 3。
- **红线**：**永远显式给 `--out`** —— 默认输出会**原地覆盖明文**。比内容只比明文哈希（同一明文封两次文件哈希必然不同）。
- **细节**：→ [WORKFLOW §6](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。

### Step 6 · 解封往返（别省）

- **目的**：证明封装没丢字节。
- **判据**：解回 `cmp` 一致 + 哈希 == 锚点 + 容器可解析。
- **认知**：四条全过只证「加解密对称」；**MAC 有效性与引擎接受都还没证**，那要靠 Step 7、8。
- **细节**：→ [WORKFLOW §6](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。

### Step 7 · 部署 + 盘上回读

- **目的**：装进游戏目录，并从**游戏目录那份**解回来读（不从自己的产物读）。
- **判据**：盘上 sha256 == 产物；解回明文哈希 == 锚点；字段值 == 期望。
- **停**：盘上 sha256 不一致（被占用 / 权限 / 路径）⇒ **不要启动游戏**，重新部署。
- **细节**：→ [WORKFLOW §7](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)（原子替换 + 回读脚本 + PowerShell 等价）；部署工具不在仓库，§9 有最小等价物。

### Step 8 · 实机验证

- **目的**：把「**这个字段是活的**」与「**被改的那一行确实被引擎消费**」**分开证**。
  （范式：先用一个面板可见的同类字段证链路，再单独用任务内计时证那行被读。）
- **判据**：**先写预测，再看读数**。「变了」不是结果，「等于我算的那个数」才是。
- **强度三级**：面板数字 > 任务内计时/计数/视觉 > 日志/转储。等级越后越弱。
- **读之前先排除四种非引擎原因**：① 该字段面板不显示 ② 吃升级（面板 = 基础 × 该玩家升级）③ 部署的不是那个变体 ④ 明文缓存被自己的 mod 污染。
- **细节**：→ [WORKFLOW §8](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。

### Step 9 · 记账 / Step 10 · 回滚

- **目的**：让「装过什么、何时回滚」可追溯；回滚后仍能核哈希。
- **判据**：账本至少七项（build / backup_sha256 / installed_sha256 / installed_from / installed_at / 明文哈希 + 字段旧新值 / 实机读数）；回滚后 `installed_from = "(restored)"`，**不要删记录**。
- **停**：改动跨 N 张表 ⇒ N 条账本、N 次回滚；按依赖**反序**回或一次性全回（只回一张会留下悬空引用 ⇒ 灰块）。
- **细节**：→ [WORKFLOW §9](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。

## 4. 证据纪律（本技能相对其它载体的增量）

| 标记 | 含义 | 允许的措辞 |
|---|---|---|
| `✓ 实机` | 进游戏看过，**且三件套齐全** | 「已实机」 |
| `✓ 离线` | 只读解析 / 离线复跑 | 「离线可复现」 |
| `✗ 否证` | 试过、不通，写清失败形态 | 「否证」+ 怎么否的 |
| `⚠ 未证` | 有推理或部分证据，没上机 / 没分辨 | 「未验证」，**不许**写成结论 |

**「已上机」三件套（缺一条，该实验作废）**：① 账本 `installed_from`（装的是哪份产物）；② 盘上回读值（从**游戏目录那份**解回来的字段值 / 哈希）；③ 进程状态（正常启动、面板可读、无新崩溃签名）。

**汇报模板**：改了什么（表 / 行 / 字段 / 旧值→新值）+ 门禁结果（点名工具）+ **预测值 vs 实测值** + 账本四项 + 回滚命令 + 三态标记。没测的写 `⚠`，否掉的写 `✗` 并写清怎么否的。

真实反例与正例见 [WORKFLOW §10](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) 前两条（部署的不是那个变体 ⇒ 实验作废；同原版明文重封不崩 ⇒ 隔离出「崩在内容哈希」）。

## 5. 五条会改变流程顺序的红线

这五条不是知识点，是**顺序纪律**——违反其中任一条，后面的步骤都会在错误的前提上继续。

| # | 红线 | 违反后 |
|---|---|---|
| 1 | 校正字**绝不落记录行** | 记录行首 8 B 是主键与名字 ID，写进去 = 改成随机值 ⇒ 崩溃，寿命 26–29 秒 |
| 2 | **一次改完再封**，不拆多轮 | 基准漂移、每轮 payload +8，无法判断「相对原版改了什么」 |
| 3 | 面板数 **≠** 基础值 | 面板 = 基础 × 该玩家升级；不换算就判「没生效」，会把对的改动当错的 |
| 4 | 面板没变 **≠** 没生效 | 很多字段根本不在面板上；要进任务计时 / 计数 |
| 5 | 门禁全绿 **≠** 功能生效 | 最贵的一条：它只证磁盘与容器，不证引擎是否接受、语义是否正确 |

**完整 92 条坑（含每条的现象、规则、三态）** → [WORKFLOW §10](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。
**逐工具的行为陷阱**（哪些工具不报错但会让你误判）→ 同节 + [INDEX §3 工具清单](../../INDEX.md#3-工具清单tools)。

## 6. 先确认这条路不覆盖什么

| 想做的事 | 结论 | 去哪看 |
|---|---|---|
| 让新战备 / 新条目**出现在面板上** | 成员资格不在 55 张表里；加行不会让它显示（✗ 否证） | [WORKFLOW §10](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 解锁未发布物品 | 发布数据里没有那个组件（✗ 否证） | [ENTITY-TABLE](../../docs/tables/ENTITY-TABLE-25988413.md) |
| 自定义名称 / 描述文本 | 表里只有 locid，写新文本要动 `.strings`（另一条路线） | [STRATAGEM-FIELDS](../../docs/tables/STRATAGEM-FIELDS-26088801.md) |
| 运行期 native / 内存 / DLL 路线 | 已封闭（✗ 否证，实测记录在册） | [MEMORY-ACCESS](../../docs/boundaries/MEMORY-ACCESS-25988413.md) · [LOADER-SPEC](../../docs/engine/LOADER-SPEC-25988413.md) |
| 四条路线横向比较 | — | [ROUTES-COMPARE](../../docs/builds/ROUTES-COMPARE-26088801.md) |

**不做**：多人游戏分发、绕过反作弊、DLL 注入。改的是全局数据文件，**只限单人 / 私人环境自用**。

## 7. 知识库在哪

**所有具体知识都在仓库的 [INDEX.md](../../INDEX.md)** —— 一个按问题组织的单一索引入口。本技能**不复制任何一条**，避免双份真值漂移。

| 你需要 | 入口 |
|---|---|
| 「我想改 X」/「这个字段是什么」/「这个数为什么是这样」 | [INDEX §1 按问题找](../../INDEX.md#1-按问题找) |
| 全部 39 篇文档（按类型浏览） | [INDEX §2](../../INDEX.md#2-按类型浏览39-篇) |
| **找工具**（68 个：用途 / 依赖 / 验证状态 / 按任务速查） | [INDEX §3 工具清单](../../INDEX.md#3-工具清单tools) |
| 无密钥也能练手的资产 | [INDEX §4](../../INDEX.md#4-无密钥也能练) |
| 哪条已实机 / 哪条已否证 | [INDEX §5 能力明细](../../INDEX.md#5-能力明细) |
| **武器自带备弹**：背包供弹武器（AC-8 / GR-8 / Spear / RL-77 / W.A.S.P.）怎么改成不需要背包 | [WEAPON-AMMO-RESERVE](../../docs/tables/WEAPON-AMMO-RESERVE-26088801.md) |
| **有限数量的跨包加载**（最多两个包）：换进来的资产为什么紫问号、怎么让引擎自己去加载 | [LIMITED-CROSS-PACKAGE-LOADING](../../docs/engine/LIMITED-CROSS-PACKAGE-LOADING-26088801.md) |
| **92 条坑**（现象 / 规则 / 三态） | [WORKFLOW §10](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 还缺什么实验 / 哪些字段没找到 | [WORKFLOW §12](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| 换 build 三步 | [BUILDS.md §3](../../BUILDS.md) |
| 别人怎么命名 / 前人做过什么 | [PRIOR-ART-NAMING](../../docs/cases/PRIOR-ART-NAMING.md) |

> 字段名 `uses_per_rearm` / `rearm_time` 与「每次回收次数」语义来自 **[HD2Runtime by SkyeShade](https://github.com/SkyeShade/HD2Runtime)**；其许可要求引用其偏移 / 字段名 / 清单时**显式署名**。本仓库的数值与实机读数均为自行实测。

## 8. 安装与提交门禁

```
skills/hd2-file-route-mod/
└── SKILL.md          ← 唯一必填文件（本文件，方法论；知识在 ../../docs）
```

- **DSH**：放进本地 skills 目录或做成 bundle；⚠「文件在盘上」≠「在注册表里」——装完必须用 `skill` 工具按名加载一次。
- **通用**：`npx skills` 或 Claude 插件；目录名必须与 `name` 完全一致。
- **改本技能前先问自己**：这属于「顺序 / 判据 / 停的条件」吗？属于才写进来；是「某个字段是什么」「某个坑是什么」⇒ **写进仓库**，然后在 §7 加一行。
- **提交前**：`python tools/check_links.py` 必须 0 断链（`../` 层数写错会逃出仓库根，检查器**静默跳过**）。
- **不要提交**：`recipient.pk` / `recipient.sk` / `keys.json` / `streams/*.xor` / 含 epk·tag 的 `report.json` / 47 MB 实体库 / 全量 dump / mod 补丁二进制。`.gitignore` 已机械拦截大部分，但**别只靠它**——`git add` 前先 `git status --short` 看一眼。
