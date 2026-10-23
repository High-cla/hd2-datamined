---
name: hd2-file-route-mod
description: |
  做「改盘上数据」的 Helldivers 2 mod：解封 data/game/*.dl_bin 明文表（LDLD 容器）→ 定位字段 → 写入并在末尾反解 8 B 校正字保住引擎的 MurmurHash64A 内容哈希 → 过 G1..G7 门禁 → crypto_box_seal 重封 → 部署到游戏目录 → 盘上回读 → 分级实机验证 → 可 restore 回滚。改的是磁盘上的数据文件，持久生效、重启不还原；不碰进程内存、不需要 Lua/FFI/注入/DLL。
  Use when 用户说「改战备冷却 / 使用次数 / 呼叫时间」「改爆炸半径 / 破片 / 外观」「改武器或实体表数值」「把改过的表装进游戏」「离线数据 mod」「dl_bin 改不动」「启动 0xC000000D」「game.dll+0x1083a45 崩溃」「LDLD」「校正字」「seal-key」。
  载体分工（本技能只做第四种）：hd2-mod-maker = 运行期 Lua `.patch_N` 补丁；hd2-value-editor = 运行期进程内存；srkit-resources = Stingray 资源包；本技能 = **盘上明文数据表**。
license: MIT
compatibility: Windows（bash 段需 Git Bash / WSL；路径含空格，命令一律加引号）· Python 3.11+ · PyNaCl（仅解封/重封）· 需使用者自备 recipient.pk / recipient.sk，本仓库不提供（且必须是游戏内置的那一对，自造无效）· 部署前必须退出游戏
metadata:
  domain: hd2-data-tables
  tools: build_cache.py, dlbin_seal.py, plain_edit.py, stratagem_tune.py, murmur64.py, murmur64a.py
---

# HD2 改盘上数据的 mod（file route）

> **一句话**：一条能复现的改表链 = 选表 → 取明文 → 定位字段 → 尾宿主保哈希写入 → 过门禁 → 重封 → 往返 → 备份安装 → **从游戏目录回读** → 分级实机 → 记账/可回滚。**少一次读数，就只能记 `⚠`，不能记 `✓`。**
> 适用：`data/game/*.dl_bin` 明文表（`LDLD` 容器），按 build **`26088801`** 写。原理、数值与 92 条坑在 [FILE-ROUTE-WORKFLOW-26088801.md](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)——**本技能只讲顺序、判据与停的条件**，不重复推导。

## 0. 与其它载体划界（先确认该用哪个技能）

| 技能 | 载体 | 生命周期 | 定位方式 | 回滚方式 |
|---|---|---|---|---|
| `hd2-mod-maker` | `.patch_N` 三件套 | 加文件即生效 | 模块路径 → murmur64 | 删文件 |
| `hd2-value-editor` | 进程内存 | 重启即复原 | id / position 行 | 重启 |
| `srkit-resources` | Stingray 资源包 | 叠层优先级 | 资源 id | 不写游戏目录 |
| **本技能** | `data/game/*.dl_bin` 单文件 | **持久，重启不还原** | **文件绝对偏移 + 行步长** | **备份 + 账本 + 核哈希** |

三句话判据：要**会话内临时**改数值 → `hd2-value-editor`；要**持久**且只改数值/引用 → 本技能；要改资源本体（模型 / 贴图 / 粒子 / lua）→ `srkit-resources` 或 `hd2-mod-maker`。两者会互相打架：运行期 mod 若写同一字段的进程内存，会盖掉盘上值。

**不重复**：模块命名与 patch 索引、离线测试套件、`srkit` 解包与往返证明、内存三守卫、侦察报告 §0–§8 骨架、备份四命令 —— 一律见上述四个技能，本文只给指针。

## 1. 三个必须先切断的混淆点

| 说法 | 本技能里的意思 | 不是 |
|---|---|---|
| **封装** | `tools/dlbin_seal.py seal-key`（`crypto_box_seal`：epk 32 ‖ tag 16 ‖ ciphertext，产物 `*.dl_bin`） | `srkit pack` 的资源打包（产物 `.patch_N`）。产品名也不同：`*.sealed.dl_bin` 已被 `.gitignore` 机械拦截 |
| **murmur64** | 内容闸门 `MurmurHash64A(明文)`，seed `0xDEADBEEFABAD1DEA` → `tools/murmur64.py` / `tools/murmur64a.py` | `srkit hash` 算的是资源 id（路径哈希）。同名不同种，混用会得到「另一个哈希」且**不报错** |
| **`data/game/`** | 55 张 `.dl_bin` + `dl_library.dl_typelib` + `game.dll`，松散加密文件，无 `file_id` | `data/*.patch_N` 叠层包。改 `.dl_bin` 用不到 srkit，srkit 也读不懂它；`.patch_N` 覆盖不了它（**✗ 否证**） |

## 2. 前置（缺一条就停，不要硬试）

| 需要 | 怎么确认 | 缺了怎么办 |
|---|---|---|
| `recipient.pk` / `recipient.sk` | 使用者自备；**本仓库不提供，也不该提供**；且必须是**游戏内置的那一对**（自造一对能让所有命令跑通，只在进游戏时失败）。只有 sk 也行：`pk = PrivateKey(sk).public_key` | 停：没 pk 封不回去，没 sk 解不开。三条已知来源与代价见 [WORKFLOW §1.2.1](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) |
| build 对得上 | `appmanifest_553850.acf` 的 `buildid`；明文哈希 == §3 Step 1 的锚点 | 停：偏移整体作废，先跑 [BUILDS.md](../../BUILDS.md) §3 三步 |
| 游戏已退出 | 任务管理器 / `Get-Process Helldivers2` | 关游戏：表在**启动时**读入，运行中替换会读到半份 |
| `data/game` 是原版 | 没装过自己的 mod，或先 restore | 先 restore：否则 dump 的「原版」是你的负载（缓存污染的来源） |
| 已备份 | 每张要动的表一份 sha256 备份 | 先备份：没有原版就不能回滚 |
| Python 3.11+ / PyNaCl | `python -V`；`python -c "import nacl"` | `pip install pynacl`（只有解封/重封需要） |
| 磁盘 | 实体表 47 MB ⇒ 备份 + 明文留 ~120 MB | 先拿小表把链路做通 |

## 3. 分步链路（Step 0 选表 + 十步执行）

> 与 [FILE-ROUTE-WORKFLOW](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) 的「八步速查」是同一条链：Step 1–10 就是那八步的展开，Step 0「选表」与 Step 9/10「记账 / 回滚」是首尾多出来的两段。

### Step 0 · 选表（先按语义选表，再谈偏移）

| 想改 | 表 | 入口字段 | 状态 |
|---|---|---|---|
| 战备冷却 / 呼叫 / 次数 | `generated_stratagem_settings` | `+0x68` / `+0x54` / `+0x50` | ✓ 实机 |
| Eagle 回收时间 | 同上，`EAGLE. REARM` 是**独立一行** | `+0x68`（同行不同义） | ✓ 字段实机 / 系数 ⚠ |
| 爆炸伤害 / 半径 / 破片 / 粒子 | `generated_explosion_settings` | `+0x04` / `+0x10..+0x18` / `+0x50`·`+0x54` / `+0x38` / `+0xA8` | ✓ 多数实机 |
| 弹丸换**爆炸效果** | `generated_projectile_settings` | `+0x90` / `+0x9C`（= +144 / +156）= 命中 / 到期两个爆炸 type 引用 | ✓✓ 实机 |
| 弹丸换**弹头**（整行搬运） | `generated_projectile_settings` | 整行 272 B 从供体行拷来（`proj_copy_row.py`），**不动** `+0x90/+0x9C` | ✓✓ 实机 |
| 弹幕轮数 / 散布 / 装填可移动 | `generated_entities` | `Bombardment +0x18` / `+0x24`；`WeaponReloadComponentData` | ✓ 实机 **@`25988413`**（`26088801` 的 55 张表逐字节未变） |
| 新可见战备 / 解锁未发布物品 | **不在 55 张表** | — | ✗ 否证 |
| 自定义名称 / 描述文本 | `.strings` 语料 | — | ✗ 另一条路线 |
| 伤害行（`DamageInfo`） | `damage_settings` | 76 B 零 padding | ⚠ 无宿主方案 |

**停的条件**：目标只能靠「面板上看不见」猜 ⇒ 先去 Step 2 找一个可证伪的预测，**不要先改字节**。

### Step 1 · 取明文 + 三个自检

```bash
# 路线 A（推荐：整包基线，同时给你明文和 typelib）
python tools/build_cache.py --sk <recipient.sk> \
    --game "D:/SteamLibrary/steamapps/common/Helldivers 2"
# -> refs/dlbin/plaintext-<buildid>/   55 张表 + dl_library.dl_typelib
# manifest 不用给：--appmanifest 默认值就是 D:/SteamLibrary/steamapps/appmanifest_553850.acf
# （在 steamapps/ 下，不在 common/Helldivers 2/ 下；写错的路径会在这一步 FileNotFoundError）

# 路线 B（单张，快；typelib 必须解到同一目录，stratagem_tune 找不到就退出）
python tools/dlbin_seal.py open-key "<游戏>/data/game/generated_stratagem_settings.dl_bin" --key <recipient.sk> --out <work>/generated_stratagem_settings.dl_bin
python tools/dlbin_seal.py open-key "<游戏>/data/game/dl_library.dl_typelib" --key <recipient.sk> --out <work>/dl_library.dl_typelib
```

三个自检缺一不可。**永远以哈希为准，不以退出码为准**：`unseal` 用错 stream 只打一行 `WARNING: plaintext does not parse` 然后照写文件并 `exit 0`。

| # | 检查 | 命令 / 判据 |
|---|---|---|
| 1 | 长度：密文 − 48 = 明文 | 两边 `ls -l` 对一下 |
| 2 | 结构：`LDLD` 能逐组解析 | `python tools/dlbin_seal.py blocks <plain>` |
| 3 | 哈希 == 本 build 锚点 | `python tools/murmur64.py <plain>` |

| 表 | 明文 B | 组 / 行 / stride | 明文锚点 |
|---|---:|---|---|
| `generated_stratagem_settings` | 82,384 | 12 / 153 / 400 | `04BBE33EF809862A` |
| `generated_explosion_settings` | 68,156 | 1 / 424 / 152 | `2ABCD21D2536373D` |
| `generated_projectile_settings` | 96,604 | 1 / 355 / 272 | `946A4FE5FAAAE076` |
| `generated_entities` | 47,259,396 | 275 个 `LDLD` 块 | `8E49771B181FFAA1` |

**失败怎么办**：哈希对不上只有三种原因 —— build 不是 `26088801` / 解到了已部署的 mod 负载 / `--key` 用错（错密钥抛 `CryptoError`）。逐个排除，**不要往下走**。

**哈希对上了 ≠ 盘上是原版**：保哈希 mod 改过的明文，哈希**仍然等于**锚点（这就是本路线的原理）。判「原版」只有两条路：干净基线，或盘上封包字节数与 `_index.json` 的 `sealed_bytes` / 装前备份比对（战备表：原版 82,432 B，装过 §6 的负载 82,440 B）。

**没有密钥时能做什么**：`tables/` 三张明文样本（projectile 96,604 / damage 50,336 / weapon_customization 30,824 B）可以真跑 `plain_edit.py`（tail 宿主 + G1–G6，锚点 `946A4FE5FAAAE076`），再配 `refs/table-geometry.json`（每表 stride / 行数）与 `refs/exports/stratagem_settings.csv`（153 行的组 / 行 / 内部名 / `+104`）练手 —— **不需要任何密钥**，但不能封、不能部署、不能进游戏。

### Step 2 · 定位字段（三条手段，只有最后一条能定案）

容器几何，背下来（算偏移全靠它）：

```
文件   = u32 group_count │ 组 × { "LDLD" + 组头 24 B + payload }
组头   = magic(4) ‖ version(4) ‖ type_id(4) ‖ payload_size(4) ‖ wide(4) ‖ extra(4)
payload= 描述符 16 B(u64 marker=0x10 ‖ u64 count) ‖ 行×stride ‖ 尾部变长块
行起点 = payload + 16            单组表绝对基址 = 4 + 24 + 16 = 44
绝对偏移 = payload + 16 + i×stride + 字段偏移
多组表   = **该组 payload_off** + 16 + row×stride + 字段（payload_off 用 `dlbin_seal.py blocks` 现查，不是「44 + 组号×…」）
```

| 手段 | 命令 | 能给什么 | 不能给什么 |
|---|---|---|---|
| ① stride | `python tools/table_dictionary.py --sk <sk> --game "<游戏>" --names refs/dl-type-names.txt --json <work>/dict.json` | 组 / 行 / stride / 字段树（`Dictionary.element_of(type_id) → (element, stride)`） | 语义（类型库字符串表是空的） |
| ② 名字 | `python tools/stratagem_tune.py ... --name "EAGLE. REARM"` | 行身份（`+0x10` 是 u64 字符串偏移） | 面板名 ≠ 内部名 |
| ③ 绝对偏移 | 上式手算，喂 `plain_edit --set` | 最快 | 只对当前 build、且未增删行时有效 |

**定案仪式（四步，缺一不可）**：① 找一个只与假设自洽的分布 → ② **写下具体预测**（例：`+0x54` 写 12.0 ⇒ 面板「呼叫时间」应是 `12.0 + 2.45 − 1.0 = 13.45`）→ ③ 只改一个字段 → ④ 读另一个可读数。命中才算定案；不中说明假设错，**不是「没生效」**。

**失败怎么办**：找不到能解释整列分布的候选，或该区域没有 8 对齐空位 ⇒ 先解决宿主（Step 3 的 tail）。反面教材：弹幕行 `+0x3C` 全是 5 被判成「轮数」，实机否证——它是投放方式枚举。

> **字段未知就先停在这一步**：去 `recon-third-party-mod` 产出一张字段图（表 / 记录 / 偏移 / 类型 / 现值 / 来源 / 三态）再回来。它的纪律同样适用：第三方给的 RVA / 计数 / 偏移**不能当判据**，`.dl_bin` 的绝对偏移与行步长必须**逐 build 复验**。

### Step 3 · 写入 + 保哈希

原理：引擎重算 `MurmurHash64A(明文)` 与 `game.dll` 里烘焙的期望值比对，改任何字节都失配（`0xC000000D`）；所以在明文末尾追加 8 B 零区，反解一个 8 B「校正字」写进去，让整块哈希回到原值。

| 表 | 工具 | 寻址 | 注意 |
|---|---|---|---|
| 战备（stride 400） | `tools/stratagem_tune.py` | 内部名（精确优先，否则子串）或 `+0` type | `--edit "名::字段=值"` 可重复；默认 tail 宿主 |
| 标准 counted `LDLD`（**43/55 张**） | `tools/plain_edit.py` | 文件绝对偏移 | 单次 >16 B 要 `--allow-wide`；**不保护身份字段**；其余 12 张：2 张块前带 4 B 标签、3 张首 u32 不是组数、7 张报「尾部残留」 |
| 爆炸 | `tools/expl_set.py` | 爆炸 type + 行内偏移 | 半径 / 破片 |
| 弹丸整行搬运 | `tools/proj_copy_row.py` | 行号 / type | 换弹头 |
| 实体 | `tools/entities_modeb.py`（已发布的那部分）或自写 | 绝对偏移 | 非标准容器，`plain_edit` 会拒绝 |

```bash
# 多行一次封装（--edit 可重复）
python tools/stratagem_tune.py --plain <work>/generated_stratagem_settings.dl_bin \
    --edit "EAGLE. AIRSTRIKE::cooldown=4" --edit "EAGLE. REARM::cooldown=5" \
    --out <work>/probe.plain.dl_bin

# 任意绝对偏移（行首 = 组起始 + 24 + 16 + i×400；字段 = 行首 + 偏移）
python tools/plain_edit.py --plain <plain> --out <out.plain> --set 0x2DD8=f32:5.0
```

值语法，用一次「整行被抹掉」换来的：

| 写法 | 实际字节 | 结论 |
|---|---|---|
| `u32:158` | `9E 00 00 00` | ✅ 数值一律用它 |
| `f32:12.5` | `00 00 48 41` | ✅ IEEE-754 小端 |
| `hex:11223344` | `11 22 33 44` | ✅ 按文件顺序 |
| `4:99` | `00 00 00 99` | ⚠ 宽度 4 + **十六进制文本**语义，不是十进制 |
| `4:0x11223344` | — | ⚠ 已知 bug：`ValueError: non-hexadecimal number` |
| `158`（裸值） | 旧版：158 个零字节 | ✗ 当前已拒绝；历史事故见 §7 #2 |

**tail 宿主六步**（`plain_edit` / `stratagem_tune` 内置）：

```
① 明文对齐到 8 的倍数（pad）        ② 末尾追加 pad+8 字节（战备 pad=0 → +8；实体 pad=4 → +12）
③ 末块 LDLD 头 +12 的 payload_size += pad+8
④ 以「原哈希」为目标解校正字（word_offset % 8 == 0，且完整落在数据内）
⑤ 写入追加区                       ⑥ 复算哈希 == 原值，且容器能重新解析
```

**绝对不许碰**：`+0` 条目 ID（连续 1 基主键，重复必崩）、五个 locid 槽（`+0x28/+0x2C/+0x30/+0x34/+0x38`）、`LDLD` 头 `+16` 的 `wide`（块头宿主的前提）。**校正字绝不落记录行**（见 §7 #1）。

**停的条件**：表里没有 8 对齐宿主（例：雾色表组头 `+16` 在 `0x14`）⇒ 这张表**放弃**。块头 L1 宿主只有设计、**未上机**，不要拿它当备选方案上机。

**一次改完再封**：所有目标字段放进同一次运行、同一次封装、同一次部署。`--edit` 串两次其实**不失效**（哈希仍复原，82,384 → 82,400），只是基准会漂、每轮 payload +8，容易误判「相对原版改了什么」。

### Step 4 · 门禁（该工具全 PASS 才继续）

| 门禁 | 防什么 | 失败怎么办 |
|---|---|---|
| G1 长度 | 漏 pad / 尺寸没同步 | 长度必须 = 原长 + pad + 8，重算 |
| G2 差异集合 | **顺手改到别处**（最有价值的一道） | 差异必须 ⊆ 声明偏移 ∪ 尺寸字段 ∪ 校正字 8 B |
| G3 哈希 | 保哈希失败 | 校正字没 8 对齐 / 写错位置 |
| G4 回读 | 宽度 / 端序 / 偏移错 | 值类型前缀写错（f32 vs u32） |
| G5 其余字节 | 重建丢字节 / 重排 | 不要自己重建容器，用工具 |
| G6 容器自洽 | 加了 `pad+8` 但 `payload_size` 没加 | 跑 `dlbin_seal.py blocks` 兜底 |
| G7 身份字段 | 撞主键（崩溃根因） | 你把 `+0` / locid 带进去了 |

**真实编号（别张冠李戴）**：`plain_edit` 是 G1–G6、独立 **5** 项（G5 与 G2 同条件）；`stratagem_tune` **默认 7 行**（G1–G7）、`--set-type` 时 **8 行**（G7 降级为 G7'，多一行恒真的 G8 —— 那是记录，不是门禁），独立 **6** 项，且它 stdout 里的 `G6 目标行其余字段未变` 是**记录级**：路线级 G6（容器重解析）它**没有**，靠 `dlbin_seal.py blocks` 兜底；`ent_set`（私有）5 行且 G5 很弱。说「全过」时必须点名工具，并点名是 7 行还是 8 行。

**四个局限**：① G3 是「相对原版不变」，不是「等于引擎期望值」——seed 换了会全绿而实机拒；② G4 与写入共用一套解析逻辑，**自己骗自己**也能过；③ G2 的允许集合是调用者声明的，不判「有害」；④ **门禁全绿 ≠ 功能生效**。

### Step 5 · 重封

```bash
python tools/dlbin_seal.py seal-key <work>/probe.plain.dl_bin --key <recipient.pk> --out <work>/probe.dl_bin
python tools/dlbin_seal.py inspect <work>/probe.dl_bin     # 看 48 B 头
```

判据：**封包 = 明文 + 48 B**。不成立 ⇒ 封错了文件，回 Step 3 重新产出明文。**永远显式给 `--out`**——`seal-key` 的默认输出是「去扩展名 + `.dl_bin`」，输入 `x.dl_bin` 会**原地覆盖明文**。同一份明文封两次，文件哈希必然不同（新随机 epk/tag），**比内容只比明文哈希**。长度没有 65,504 上限，那只是「借别人固定流」时的限制。

`seal-material` 用预计算材料（真 MAC，✓ 离线）；`seal --tag copy/zero` **不可用于改动过的明文**（tag 密钥 = `keystream[0:32]`，拿不到），只在「引擎不校验 MAC」的未验证前提下才有意义。

### Step 6 · 解封往返（别省）

```bash
python tools/dlbin_seal.py open-key <work>/probe.dl_bin --key <recipient.sk> --out <work>/rt.plain
cmp <work>/rt.plain <work>/probe.plain.dl_bin && echo 往返一致
python tools/murmur64.py <work>/rt.plain          # 必须 = 锚点
python tools/dlbin_seal.py blocks <work>/rt.plain
```

四条全过只证明「加解密对称、封装没丢字节」；**MAC 有效性与引擎接受都还没证**，要靠 Step 7、8。`selftest` 把原 tag 原样搬回，**不能**证明 MAC 有效。失败怎么办：`cmp` 不一致 ⇒ keystream / 材料不对，重封；哈希 ≠ 锚点 ⇒ 解出来的明文本身不是原版，回 Step 1。

### Step 7 · 部署 + 盘上回读

> 下面是 **bash**（Git Bash / WSL）；PowerShell 逐条等价见 [WORKFLOW §7.8](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。

```bash
set -euo pipefail
GAME="D:/SteamLibrary/steamapps/common/Helldivers 2/data/game"
NAME="generated_stratagem_settings.dl_bin"; WORK="<work>"; mkdir -p "$WORK/backup"

# ① 备份（第一次装之前做一次，之后永不覆盖）
[ -f "$WORK/backup/$NAME" ] || cp "$GAME/$NAME" "$WORK/backup/$NAME"
sha256sum "$WORK/backup/$NAME"              # Windows 可用 certutil -hashfile

# ② 原子替换：.deploying → 校验 sha256 → rename（同卷 rename 原子）
cp "$WORK/probe.dl_bin" "$GAME/$NAME.deploying"
sha256sum "$GAME/$NAME.deploying"           # 必须 = 产物 sha256
mv -f "$GAME/$NAME.deploying" "$GAME/$NAME"

# ③ 盘上回读（从**游戏目录那份**解回来，不从自己的产物读）
python tools/dlbin_seal.py open-key "$GAME/$NAME" --key <recipient.sk> --out "$WORK/readback.plain"
python tools/murmur64.py "$WORK/readback.plain"      # 必须 = 锚点
python - <<'PY'
import struct
p = open(r"<work>/readback.plain", "rb").read()
# 0x2608 = 0x25A0（组2 行3 = EAGLE. AIRSTRIKE 行首）+ 0x68
# 0x2DD8 = 0x2D70（组2 行8 = EAGLE. REARM 行首）    + 0x68
print("AIRSTRIKE +0x68", struct.unpack_from("<f", p, 0x2608)[0])   # 期望 4.0
print("REARM     +0x68", struct.unpack_from("<f", p, 0x2DD8)[0])   # 期望 5.0
PY
```

**失败怎么办**：`installed_sha256` 与盘上不一致 ⇒ 没落盘（被占用 / 权限 / 路径错），**不要启动游戏**，重新部署；盘上哈希 ≠ 锚点 ⇒ 装错了文件。判据顺序：`installed_from` → 盘上明文哈希 → 字段回读 → 进游戏。

账本至少七项：`build` / `backup_sha256` / `installed_sha256` / `installed_from` / `installed_at` / 明文哈希 + 字段旧新值 / 实机读数。部署器 `dlbin_deploy.py` **不在本仓库**，上面三行是它的最小等价物；它只比 sha256，**不校验内容合法**（不解密、不算哈希、不解析 `LDLD`），传错文件照装、崩在引擎里。

### Step 8 · 实机验证（三级，强度差一个数量级）

**先写预测，再看读数。**「变了」不是结果，「等于我算的那个数」才是。

| 级 | 证据 | 能证明 | 不能证明 |
|---|---|---|---|
| 1 | 面板数字 | 运行时读了这个字段 | 面板公式 / 任务内行为 |
| 2 | 任务内计时 / 计数 / 视觉 | 行为真的变了 | 精确系数 |
| 3 | 日志 / 转储 | 引擎拒绝了 / 代码路径走到了 | 字段语义 |

读之前先排除**四种非引擎原因**：① 该字段面板不显示（轮数 / 散布 / 间隔）；② 吃升级（面板 = 基础 × 该玩家升级，冷却已见 ×0.90 ×0.95；轮数 +1；呼叫 = 基础 + 交付延迟 − 升级）；③ 部署的不是那个变体；④ 明文缓存被自己的 mod 污染。四种都排除了，才轮到怀疑字段。

### Step 9 · 记账

```json
{
  "generated_stratagem_settings.dl_bin": {
    "build": "26088801",
    "backup_sha256": "<装前那份>", "installed_sha256": "<装进去那份>",
    "installed_from": "tmp/out/probe.dl_bin", "installed_at": "2026-10-23T15:06:46",
    "plaintext_sha256": "da7f0cb7…", "plaintext_murmur64": "04BBE33EF809862A",
    "diff_bytes": 5,
    "readings": { "panel_cooldown_s": [7, 2], "mission_rearm_s": [150, "3.x"] },
    "restored_at": null
  }
}
```

### Step 10 · 回滚

```bash
cp "$WORK/backup/$NAME" "$GAME/$NAME"
sha256sum "$GAME/$NAME"                            # 必须 = backup_sha256
python tools/dlbin_seal.py open-key "$GAME/$NAME" --key <recipient.sk> --out "$WORK/restored.plain"
python tools/murmur64.py "$WORK/restored.plain"    # 必须 = 原版锚点
```

回滚后账本改成 `installed_sha256 = backup_sha256`、`installed_from = "(restored)"`、`restored_at = <时间>`；**不要删记录**，保留「装过什么、何时回滚」。

两个陷阱：① 改动跨 N 张表 ⇒ N 条账本、N 次回滚；只回一张会留下悬空引用（爆炸外观三步链：只回战备 ⇒ 弹丸仍指向不存在的克隆行 ⇒ 灰块）。按依赖**反序**回，或一次性全回，每步核哈希。② 备份是**一次性快照**：游戏更新后 `restore` 旧 build 的表可能直接崩；更新后先重建基线（`build_cache.py` + `build_diff.py`），别把旧备份当万能回滚。

## 4. 三态证据与「已上机」三件套（本技能相对其它载体的增量）

| 标记 | 含义 | 允许的措辞 |
|---|---|---|
| `✓ 实机` | 进游戏看过，**且三件套齐全** | 「已实机」 |
| `✓ 离线` | 只读解析 / 离线复跑，不启动游戏 | 「离线可复现」 |
| `✗ 否证` | 试过、不通，写清失败形态 | 「否证」+ 怎么否的 |
| `⚠ 未证` | 有推理或部分证据，没上机 / 没分辨 | 「未验证」，**不许**写成结论 |

**「已上机」三件套（缺一条，该实验作废）**：① 账本 `installed_from`（装的是哪份产物）；② 盘上回读值（从**游戏目录那份**解回来的字段值 / 哈希）；③ 进程状态（正常启动、面板可读、无新崩溃签名）。

真实反例：按 `+0x3C` 做「改成 2 轮」的实验没见效，事后核对账本发现部署的是**另一个 probe** ⇒ 整次实验**作废，既不能证明也不能反证**。正例：雾色表改内容后 `0xC000000D`，用**完全相同的原版明文**重封不崩 ⇒ 干净隔离出「崩在内容哈希，不在封装 / tag」。

**汇报模板**：改了什么（表 / 行 / 字段 / 旧值→新值）+ 门禁结果 + **预测值 vs 实测值** + 账本四项 + 回滚命令 + 三态标记。没测的写 `⚠`，否掉的写 `✗` 并写清怎么否的。

## 5. 已验字段速查（只列偏移，不复制数值表）

> 数值表与逐条证据：[STRATAGEM-FIELDS-26088801.md](../../docs/tables/STRATAGEM-FIELDS-26088801.md)、[EXPLOSION-VISUAL-26088801.md](../../docs/explosions/EXPLOSION-VISUAL-26088801.md)；全表几何与 1,208 类型的字段树：[TABLE-DICTIONARY-25988413.md](../../docs/tables/TABLE-DICTIONARY-25988413.md)。本技能**不复制**它们——双份真值必然漂移。

**战备行（stride 400，12 组 153 行）**

| 偏移 | 类型 | 含义 |
|---|---|---|
| `+0x00` | u32 | 连续 1 基条目 ID（**主键**，重复必崩） |
| `+0x10` | u64 | 内部名字符串偏移（相对 payload） |
| `+0x28/+0x2C/+0x30/+0x34/+0x38` | u32 | 五个 locid（大写名 / 显示名 / 描述 / …）——**身份，不许动** |
| `+0x3C` | u32 | 投放方式枚举（Eagle 0 / 单发 1 / 武器 2 / 弹幕 5），**不是轮数** |
| `+0x50` | u32 | 使用次数；`0xFFFFFFFF` = 无限；Eagle = 每次回收次数 |
| `+0x54` | f32 | 呼叫时间（面板 = 基础 + 交付延迟：ORBITAL +2.45 / BACKPACK +4.75 / EAGLE +4.10） |
| `+0x60` | f32 | ⚠ **语义未解**（REARM 行 15.0、空袭行 0.0，无改动实验） |
| `+0x68` | f32 | 冷却；`EAGLE. REARM` 行上 = 回收时间 |
| `+0x188` | u32 | 面板格 / 分类号 |

**爆炸行（stride 152，单组 424 行）**：`+0x04` 伤害行 · `+0x10/+0x14/+0x18` 半径 · `+0x28/+0x2C/+0x30` 相机抖动 · `+0x38` u64 粒子 `file_id` · `+0x40` 未知哈希 · `+0x50` 破片数 · `+0x54` 破片弹丸 · `+0x78` 弧线 · `+0xA8` 根包 id（写外来包 id 会真的加载那个包，四行对照验证过）。

**弹丸行（stride 272）**：`+0x90` / `+0x9C`（十进制 +144 / +156）= **命中 / 到期两个爆炸 type 引用**（换爆炸效果的入口）；换**弹头**是整行 272 B 搬运（`proj_copy_row.py`），**不改**这两格。

**实体库**：不是 counted `LDLD`，是 **275 个 `LDLD` 块**（每块前 4 B 类型标签，块头共 28 B）；`Bombardment +0x18` 轮数、`+0x24` 散布（f32 米）；`WeaponReloadComponentData` 80 B 行含 `ManualClearing` / `ReloadAllowMove` / `Duration`。

> 字段名 `uses_per_rearm` / `rearm_time` 与「每次回收次数」语义来自 **[HD2Runtime by SkyeShade](https://github.com/SkyeShade/HD2Runtime)**；其许可在 MIT 之外要求**引用其偏移 / 字段名 / 清单时显式署名**。本技能的数值与实机读数来自本仓库。

## 6. 配方：一次封装改两行（本仓库唯一 ✓✓ 端到端案例）

目标：`EAGLE. AIRSTRIKE +0x68` 15→4、`EAGLE. REARM +0x68` 150→5。

```bash
python tools/stratagem_tune.py --plain <work>/generated_stratagem_settings.dl_bin \
    --edit "EAGLE. AIRSTRIKE::cooldown=4" --edit "EAGLE. REARM::cooldown=5" \
    --out <work>/eagle.plain.dl_bin
```

| 预期 | 实测 |
|---|---|
| 明文 82,384 → 82,392（tail +8） | 82,392 ✓ |
| 整份只差 **5 字节**（两个 f32 高两字节 + 一个 `payload_size` 字节） | 5 ✓ |
| 明文哈希仍 `04BBE33EF809862A` | 同 ✓ |
| 门禁 7 PASS | 7 PASS ✓ |
| 面板冷却 7 秒 → ? | **2 秒**（公式未解，见 §8.3） |
| 任务内回收 150 秒 → 3.6–5 秒 | **3 秒多** ✓ |

校正字落在 `0x141D0–0x141D7`（`0x141D0 % 8 == 0`），末组 `payload_size` 在 `0x128B0`。两次独立运行产出**逐字节相同**的明文（sha256 相同），不是「看起来一样」。

## 7. 坑与否证清单（本技能最贵的部分）

状态列：`✓ 实机` / `✓ 离线` / `✗ 否证` / `⚠ 未证`。完整 92 条在 [FILE-ROUTE-WORKFLOW §10](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)，这里只留会直接害人的。

### 7.1 会崩、会抹数据

| # | 坑 | 现象 → 规则 | 状态 |
|---:|---|---|---|
| 1 | 校正字写进记录行 | `0xc0000005 @ game.dll+0x1083a45`，寿命 26–29 s，三次同签名。行首 8 B 是 `+0` 主键 + `+4` 名字 ID，写进去 = 改成随机数 | **✓ 实机（崩）** |
| 2 | 裸整数值 | `--set 0x979c=158` 被当成「宽 158 B 全零」，整行抹掉；G4 用同一解析器回读，**自证通过** | **✓ 实机** |
| 3 | 加行沿用原 `+0` | 重复主键 ⇒ 崩。新行取 `max+1`；能不加就不加 | **✓ 实机** |
| 4 | `stratagem_tune --host-mode row` | 帮助自己写着「实机已验证会崩」；默认 `tail`，永不传这个开关 | **✓ 实机** |
| 5 | 启动 `0xC000000D` | 封装正确但**内容哈希**没还原；回 Step 3，不是封装问题 | **✓ 实机** |

### 7.2 改了却不生效（6–11 是四类非引擎原因，12–15 是资源 / 引用）

| # | 坑 | 现象 → 规则 | 状态 |
|---:|---|---|---|
| 6 | 用面板名找行 | `--name "Orbital Laser"` 命中 0 行；表里是 `ORBITAL. LASER` | **✓ 实机** |
| 7 | `+0x3C` 当轮数 | 弹幕行全是 5 只是同枚举值；轮数在实体 `Bombardment +0x18` | **✗ 否证** |
| 8 | 面板数对不上 | 面板 = 基础 × 该玩家升级（冷却 ×0.90 ×0.95）；先换算再判 | **✓ 实机** |
| 9 | 「面板没变」= 没生效 | 轮数 / 散布 / 间隔根本不在面板上；进任务计时 | **✓ 实机** |
| 10 | 结论被推翻 | 部署的不是那个变体（账本指向别的 probe）⇒ 实验作废 | **✓ 实机** |
| 11 | build 误报 | 明文缓存被自己的 mod 负载污染；dump 前确认盘上原版 | **✓ 实机** |
| 12 | 只改粒子 id | 特效不出现；引擎要**整行一致**（克隆）+ 包已加载 | **✗ 否证** |
| 13 | 换粒子后灰块 | 资源不在任何已加载包 ⇒ 改 `+0xA8`；灰块 = 代码路径通了，是免费探针 | **✓ 实机** |
| 14 | `.patch_N` 覆盖 `data/game/*.dl_bin` | 松文件不在 `bundle_database.data`，补丁层看不见它 | **✗ 否证** |
| 15 | 加行 = 新增可见条目 | 能进游戏，面板仍只有一条；成员资格在 55 张表外 | **✗ 否证** |

### 7.3 工具行为（不报错，但会让你误判）

| # | 工具 | 坑 → 规避 | 状态 |
|---:|---|---|---|
| 16 | `plain_edit` | **没有身份字段门禁**，可合法改坏 `+0` / locid；也拦不住 `--out == --plain`（原地覆盖原版） | **⚠ 未证** |
| 17 | `plain_edit` | `4:99` 是十六进制文本语义（`00 00 00 99`）；`4:0x1122…` 直接 `ValueError` | **✓ 离线** |
| 18 | `table_dictionary` | 已发布 MD 的「row 0, both readings」列整体错位 **−16 B**（`sample_rows()` 漏了 `rows`/`rows+blob`）⇒ 用 `--json` + 直接读字节，别照 MD 抄 | **✓ 离线** |
| 19 | `table_dictionary` | MD / JSON 的 build 硬编码 `25988413`；`--sk` 会补零 / 截断；build 号以 `_index.json` + 锚点为准 | **⚠ 未证** |
| 20 | `murmur64.py` | CLI **只能算哈希、不能解字**；解字用 `python tools/murmur64a.py solve <file> --word N --target HEX --out <f>` 或 import `padding_word_for_hash` | **✓ 离线** |
| 21 | `stratagem_tune` | 改完**不重解析块链**（只改末组 `payload_size`）⇒ 之后补一次 `dlbin_seal.py blocks`；且要求明文 8 对齐、只认 stride 400 | **⚠ 未证** |
| 22 | `stratagem_tune` | `--help` 仍写「`--edit` 串两次会失效」——**已否证**（两次后哈希仍复原）；代价是基准漂移，不是失效 | **✗ 否证** |
| 23 | `dlbin_seal` | `unseal` 用错 stream 只打 `WARNING` 就写文件并 **exit 0**；`selftest` 把原 tag 搬回，**不能证明 MAC 有效** | **⚠ 未证** |
| 24 | `dlbin_seal` | `seal-key` 不给 `--out` 会**原地覆盖明文**；`streams/*.xor` 与含 epk/tag 的 `report.json` 是**密钥材料**，与私钥同级 | **⚠ 未证** |

### 7.4 语义误判（最花时间的一类）

| # | 坑 | 现象 → 规则 | 状态 |
|---:|---|---|---|
| 25 | Eagle 设「无限」 | `+0x50` 直接进 f32 运算，`0xFFFFFFFE` / `…FF` / `…FD` 全回绕成 0 ⇒ 鹰式不能设无限 | **✗ 否证** |
| 26 | 「这一行不渲染」= 没人读 | `(NOT USED)` 行不画面板，但 `+0` 照样参与建索引；渲染与建 map 是两条路径 | **✓ 实机** |
| 27 | f32 精度 | ≥2²⁴ 时「+1」被舍掉；`4,294,967,168` → 0；实用上限 2²⁴−1 | **✓ 实机** |
| 28 | `LoadoutEntry.selectable` 解锁 | 发布数据里没有这个组件（djb2 搜索 0 命中）⇒ 改表解锁未发布物品**不可能**；见 `refs/loadout-entry.json` | **✗ 否证** |
| 29 | 给武器新增独立弹种行 | 四个变体全 `0xC000000D`；只改现有行 | **✗ 否证** |
| 30 | 零空位表套 tail | 20 张表在 L1 / L2 无空位；tail +8 只在战备 / 实体实机，其余**逐表未验** | **⚠ 未证** |

## 8. 做不到的事（提前知道，省一次启动）

### 8.1 native / 运行期路线为什么封闭（实测于 `25988413`；`26088801` 换了 exe / game.dll，引擎级结论未在本 build 复验）

| 路 | 结论 | 证据 |
|---|---|---|
| 进程内 `ffi` 读表 | `_VERSION == Lua 5.1`，`type(ffi) == nil`，`jit` / `bit` 同为 nil | [MEMORY-ACCESS](../../docs/boundaries/MEMORY-ACCESS-25988413.md) |
| `package.loadlib` 自备 DLL / 引擎插件目录 | 自备 DLL 被签名闸门拒绝（不存在 / 未签名 / 签名不在名单，三种都不放行；自签证书装进系统根存储也一样）；引擎插件闸门认「名字 + 内容」，同名不同内容不映射 | 同上 §12 |
| 外部进程读内存 / 全量 dump | 反作弊在句柄创建时就把读取权限剥掉；多种替代读法全被拒 | 同上 §1 / §2 / §8 |
| 载荷请求资源包 | Lua 侧 `ResourcePackage` 只有 6 个不可枚举键；跨包驻留只能由 **HD2Runtime by SkyeShade** 走 `game.dll` 的 `RefcountedPackageSystem` | [LOADER-SPEC](../../docs/engine/LOADER-SPEC-25988413.md) §3 |

### 8.2 在 55 张明文表里找不到的字段

| 想改 | 结论 | 状态 |
|---|---|---|
| 战备攻击参数（`num_bombs` / `num_salvos` / `area_size` / `fire_height`） | 400 B 行里四种宽度全 0 命中；在 bundle 的战备攻击定义里 | **✗ 否证** |
| 每轮弹数 / 弹间隔 / 战备→弹丸外键 | 400 B 扫遍无「Napalm=5、其余=3」分布；四种外键编码全不命中（`+0x98` 是 8 B 实体哈希数组） | **✗ 否证** |
| 伤害（`damage_settings`） | `DamageInfo` 76 B / 8 成员覆盖满、**零 padding** ⇒ 无宿主，暂不可改 | **⚠ 未证** |
| `+0x60` | 读到值（REARM 15.0 / 空袭 0.0），没做过改动实验 | **⚠ 未证** |
| 自定义文本 | 表里只有 32 位 locid；写新文本要动 `.strings`（另一条路线） | **✗ 否证** |

### 8.3 只有数据证据、没有实机

- **20 张零空位表的 tail +8**：只在战备 / 实体上实机通过，其余逐表未验（优先 `planet_override` / `planet_color_set` / `weather_color_set`）。
- **块头 L1 宿主**：`wide` 必须保持 1 的受约束反解，只有设计、没上机。
- **Eagle 面板冷却公式**：`15→7`、`4→2` 都符合 `floor(base/2)`，但分母 2 没有来源，与已验证的 `×0.90×0.95` 不符 ⇒ 只打「字段活」的 ✓，公式 ⚠。分辨实验：`+0x68` 设 9，看 4 还是 7–8。
- **Eagle 回收时间升级系数**：`5 → 3 秒多`；`×0.8=4` 与 `×0.8×0.9=3.6` 都落在读数内。分辨实验：设 10，看 8 还是 7.2。
- **实体表偏移**（`Bombardment +0x18` / `+0x24`、`WeaponReloadComponentData`）实测于 `25988413`；两 build 的 55 张表逐字节相同（[BUILD-26088801-DIFF](../../docs/builds/BUILD-26088801-DIFF.md)）故可沿用，但仍先对锚点。

### 8.4 结构上就改不了

成员资格（面板上有哪几条）不在 55 张表里；资源本体（模型 / 贴图 / 粒子）不在这条路上；**加行不会让新条目显示**。**不做**：多人游戏分发、绕过反作弊、DLL 注入。改的是全局数据文件，只限单人 / 私人环境自用。

## 9. 交付与安装

```
skills/hd2-file-route-mod/
└── SKILL.md          ← 唯一必填文件（本文件，≤500 行）
```

- **DSH**：放进本地 skills 目录或做成 bundle；⚠「文件在盘上」≠「在注册表里」——装完必须用 `skill` 工具按名加载一次，确认能解析。
- **通用**：`npx skills` 或 Claude 插件；目录名必须与 `name` 完全一致。
- **提交前门禁**：`python tools/check_links.py` 必须 0 断链。新增 `references/*.md` 时它们也在扫描范围内，**必须真的提交**，否则报 `missing`；`../` 层数写错会逃出仓库根，检查器**静默跳过**。
- **不要提交**：`recipient.pk` / `recipient.sk` / `keys.json` / `streams/*.xor` / 含 epk·tag 的 `report.json` / 47 MB 实体库 / 全量 dump / mod 补丁二进制。`.gitignore` 已机械拦 `*.sk` / `*.pk` / `*.sealed.dl_bin` / `*.plain.dl_bin`，以及 `refs/dlbin/`（明文缓存）、`streams/`、`*.xor`、`report.json` —— 但**别只靠它**：`git add` 之前先 `git status --short` 看一眼。

## 10. 参考

- [FILE-ROUTE-WORKFLOW-26088801.md](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) —— 完整方法论 + 92 条坑 + Eagle 案例（本技能底稿）
- [DLBIN-SEALED-BOX.md](../../docs/engine/DLBIN-SEALED-BOX.md) —— 密封盒 / 内容哈希 / 校正字原语
- [STRATAGEM-FIELDS-26088801.md](../../docs/tables/STRATAGEM-FIELDS-26088801.md) —— 战备字段与面板公式
- [EXPLOSION-VISUAL-26088801.md](../../docs/explosions/EXPLOSION-VISUAL-26088801.md) —— 视觉与跨包加载
- [ENTITY-TABLE-25988413.md](../../docs/tables/ENTITY-TABLE-25988413.md) · [TABLE-DICTIONARY-25988413.md](../../docs/tables/TABLE-DICTIONARY-25988413.md) —— 实体 275 块 / 全表几何与字段树
- [ROUTES-COMPARE-26088801.md](../../docs/builds/ROUTES-COMPARE-26088801.md) —— 四条路线横向比较（含本路线边界）
- [BUILDS.md](../../BUILDS.md) · [tools/README.md](../../tools/README.md) —— 换 build 三步 / 工具索引与验证状态
- 无密钥也能用的索引：[tables/](../../tables)（三张明文小表，用来离线预演 G1–G6）· [refs/table-geometry.json](../../refs/table-geometry.json)（55 张表的 stride / 行数，build `25988413`）· [refs/exports/](../../refs/exports)（战备 / 爆炸 / 弹丸等表的逐行 CSV：组 / 行 / 内部名 / 偏移值；文件本身未标 build，两 build 这 55 张表逐字节相同）· [refs/dl-type-names.txt](../../refs/dl-type-names.txt)（类型哈希 → 名字）

**密钥材料一律自备**：需使用者自备 `recipient.pk` / `recipient.sk`，本仓库不提供。
