# 侦察：第三方「护甲多被动」（build `25988413` 的 Lua mod，落到同一个 `.dl_bin`）

> **一句话**：它用 **Lua 在游戏退出时改写** `generated_customization_passive_bonuses.dl_bin`，
> 把用户勾选的若干「额外被动」**逐条并进每一项真实被动**。
> 路线与我们不同（运行期 Lua 写文件 vs 我们离线改字节再部署），但**落点、哈希修补、封装三件事完全一样**。
> 本文只读侦察，不安装、不运行它的补丁。

## 0. 产物清单与哈希

来源 `D:\Downloads\护甲多被动.zip`（274,213 B），解到 `D:\mod\work\recon-armor-multi\`：

| 大小 | sha256（前 24） | 文件 |
|---:|---|---|
| 418,176 | `f3c3490d5a9c374f80c86d16` | `data/9ba626afa44a3aa3.patch_0`（Bingus 补丁，含 boot.lua） |
| 0 | `e3b0c44298fc1c149afbf4c8` | `.stream` / `.gpu_resources`（空，纯 lua 补丁） |
| 709 | `cbb70a7ba42107366c668727` | `manifest.json` |
| 1,106 | `9b88d58bf308001c0a237260` | `README.md` |
| 417,963 | `af0f6d483c27c41b1eff324f` | `Source/boot.lua`（**可读源码，本文的主要证据**） |
| 4,064 | `91cfc2bf8fa32331da3fc0b2` | `Recovery/profiles/000.dl_bin`（原版 sealed 备份） |
| 9,809 | `9e471562c05455eaa4037bf3` | `Recovery/profiles.json` |

作者自述（README）：适用 **1.007.200 / Build 25988413**；F7 开菜单，空格勾选，F8 保存，
**正常退出游戏时合并、封装并写入资源**，下次启动生效；要求当前文件是**原版 sealed**，
否则菜单报 `unknown target` 并拒绝写入；卸载方式是把 `Recovery/profiles/000.dl_bin` 复制回去。

## 1. 两条路线对照

| | **它（Armory Forge 多被动）** | **我们（本仓库）** |
|---|---|---|
| 触发 | 游戏内菜单（F7），**退出时**写盘 | 离线改字节 → `dlbin_deploy.py install` |
| 改哪个文件 | `data/game/generated_customization_passive_bonuses.dl_bin` | **同一个** |
| 哈希修补 | 先找「未使用的对齐头字」，找不到就在末块 payload 尾追加 8 B，然后解校正字 | 一律末块 payload 尾追加 8 B（tail 宿主） |
| 封装 | **预计算 keystream + Poly1305**（`material.keystream/epk/poly`，固定 ephemeral） | libsodium sealed box，用 recipient **pk** 现封 |
| 失败保护 | 备份 → 临时文件 → rename → 读回校验 → rollback 文件 + 状态机 | 门禁 G1–G9 + 原版备份 + `restore` |
| 依赖 | 无外部库（纯 Lua 5.1：Murmur64A、Poly1305 全手写） | Python + PyNaCl |

> 它**没有**用到任何我们不知道的加密秘密：封装本来只需要**公钥**，
> 它把公钥与一段 keystream 一起烘进 `boot.lua`，所以不需要 libsodium。
> 我们这边有 pk，走标准封装即可，**不需要搬它的 sealer**。

## 2. 数据模型（★ 这一节是全文价值所在）

`generated_customization_passive_bonuses.dl_bin` 是**设置表容器**（`u32 组数` + 24 B 块头），
我们与它的两份文件（`26088801` / `25988413`）**结构完全相同**：

```
u32 组数（=33）
每组：24 B 块头 ['LDLD'][ver][type=0x63CE0FEB][payload_size][wide=1][4 B 保留]
      payload（→ 见下）
```

payload（**偏移相对 payload 起点**）：

| 偏移 | 类型 | 含义 |
|---:|---|---|
| `+0` | u32 | **被动 id**（perk id） |
| `+4` | u32 | `name_id`（本地化名字 id） |
| `+16` | u64 | **pm 数组偏移**（绝对，指向 payload 内） |
| `+24` | u64 | pm 行数 |
| `+32` | u64 | **sm 数组偏移**；**空数组时是 `0xFFFFFFFFFFFFFFFF`** |
| `+40` | u64 | sm 行数 |
| `+48` | 8 B | 原样保留（多数为 0，极少数非 0，例如 `86958b6300000000`） |
| `pm_off` | 16 B × n | **pm 行** |
| `sm_off` | 12 B × n | **sm 行** |

**pm 行（16 B）= 「它说自己有什么」**

| 偏移 | 类型 | 含义 |
|---:|---|---|
| `+0` | u32 | stat 键（名字的 32 位哈希） |
| `+4` | u32 | 类型（本 build 见 0/1/2/3；2 = 倍率，1/3 疑似标志或加值） |
| `+8` | f32 | 数值（倍率就是 ×1.3 这种） |
| `+12` | u32 | **描述文本的本地化 id** |

**sm 行（12 B）= 「引擎真正给什么」**

| 偏移 | 类型 | 含义 |
|---:|---|---|
| `+0` | u32 | **stat 槽位号**（见 §3，本 build 只用到 11–17） |
| `+4` | u32 | 标志（全表都是 0） |
| `+8` | f32 | 数值 |

实例（本 build 实测，perk 16 = 蓄势出击 / Siege-Ready）：

```
pm: key=0xCC530B21 type=2 value=1.3000 text_loc=0xBF0CCA74   ← primary_reload ×1.3
pm: key=0x33C9C713 type=2 value=1.2000 text_loc=0xF432722D   ← ammo_capacity ×1.2
sm: stat=13 flag=0 value=1.3000                              ← 真正生效的那一行
sm: stat=12 flag=0 value=1.2000
```

这正好解释了我们 `a8` 路线档里的悬案：**「description-only」的 pm 行不生效，因为效果在 sm 行上。**

## 3. 本 build 的全表普查（`26088801`）

- **33 条记录**，其中 `id=0` 是占位（作者跳过它），`id=42` 在表里但不在它的菜单里；
  它的菜单只列 **31 个**可选被动（id 1,2,3,5–21,31–41）。
- **sm 槽位只有 7 个**被用到（这就是「真正能叠」的全部空间）：

| stat | 条数 | 出现在 | 值 |
|---:|---:|---|---|
| 11 | 1 | perk 14（毫不畏缩） | 0.05 |
| 12 | 1 | perk 16（蓄势出击） | 1.2 |
| 13 | 2 | perk 16 / perk 10（强化肩章） | 1.3 / 1.3 |
| 14 | 1 | perk 41（坚韧不拔） | 1.3 |
| 15 | 1 | perk 18（神枪手） | 1.6 |
| 16 | 1 | perk 18 | 1.5 |
| 17 | 2 | perk 18 / perk 37（防震内衬·防化型） | 0.3 / 0.7 |

- **pm 键**：全表只有 **44 个不同 (键, 类型)**。
- ⇒ **推论**：所谓「多被动」，实际能叠的**只有那 7 条 sm 行**；
  其余被动的 pm 行加进去只会多一行描述（而且作者把它藏掉了），效果为 0。

## 4. 它的堆叠配方（`build()` 伪码）

```lua
for 每条记录 r（33 条）:
    if r.id ~= 0 then                       -- id=0 的占位不处理
        for extra in 选中的额外被动:
            pm = append_unique(pm, extra.pm 但**每行末 4 字节清 0**, 去重键 = 前 12 B)
            sm = append_unique(sm, extra.sm,                     去重键 = 前 12 B)
        重算 payload：u64bytes(pm_off) u64bytes(#pm) u64bytes(sm_off) u64bytes(#sm) + +48 那 8 B
        块头 payload_size 同步
```

三个要点：

1. **并进「每一项真实被动」而不是只并一条** —— 这样穿任何甲都带这套额外效果；
2. **去重键 = 前 12 字节**（pm 的 stat 键+类型+数值 / sm 的槽位+标志+数值），所以重复勾不会膨胀；
3. **pm 行末 4 字节（描述本地化 id）清 0** —— 作者注释写得很直白：
   *Keep the effect, but hide its description from the armor UI.*
   这就是 README 里「护甲页不显示额外被动描述」的实现方式。

## 5. 它的安全设计（值得学，但我们的工具已覆盖同等强度）

| 机制 | 做法 |
|---|---|
| 只认原版 | 任何写入前先比 `known(bytes)`（= 内嵌的 `ORIGINAL_SEALED` / `ORIGINAL_PLAINTEXT`） |
| 事务 | 备份 → 写临时文件 → `rename(target → rollback)` → `rename(temp → target)` → **读回校验**；失败则把 rollback 名回去 |
| 中断恢复 | `recover()` 在启动时检查 rollback 文件，按「live 文件是否已知」决定回滚还是清理 |
| 状态机 | `AF2\n<id 列表>` 写进 sidecar，点 F8 只是排队，**退出时才 apply** |
| 长度上限 | 显式检查 `#plaintext > material.max_len - 32`（keystream 长度有限） |

> 它的 `build()` 里还有一段：找「未使用的对齐头字」当校正字宿主，找不到才追加尾字。
> 我们一直用尾字（§FILE-ROUTE-BOUNDARIES §8.7 的教训），两者等价，**不必改**。

## 6. 能直接搬到我们这条线的东西

| # | 收获 | 用法 |
|---|---|---|
| 1 | **payload 布局确定**：`+0 id / +4 name_id / +16 pm_off / +24 pm_cnt / +32 sm_off(空=-1) / +40 sm_cnt / +48 保留 8 B` | 写 `passive_bonus_edit.py` 时的唯一权威布局 |
| 2 | **pm/sm 双数组模型**，以及「效果在 sm、描述在 pm」 | 解释并推翻我们 a8 路线档里「description-only」的困惑 |
| 3 | **真实可叠空间只有 stat 11–17 七个槽** | 先做「格挡/装填/弹容…」这些的映射，再谈叠 |
| 4 | **描述隐藏 = pm 行末 4 B 清 0** | 做「静默加成」时的标准做法 |
| 5 | **并进全部 33 条** 才能保证「穿任何甲都吃到」 | 做 mod 时的取值策略 |
| 6 | 它验证了 **`25988413` 与 `26088801` 的表结构一致**（同 type、同 33 条、同布局） | 换 build 时 `passive_bonuses` 这条线可以直接沿用 |

**不能搬/不需要搬**：它的 sealer（我们走 pk 现封）、它的菜单与状态机（我们离线改）。

## 7. 三态判定

| 结论 | 状态 | 依据 |
|---|---|---|
| 目标是 `generated_customization_passive_bonuses.dl_bin`，payload 布局如上 | **✓ 已证**（源码 + 我们自己的明文逐字段对得上） | boot.lua `decode()` 与我们 `struct` 解析结果一致（33 条、type `0x63CE0FEB`、`sm_off=-1`） |
| 「效果在 sm 行」 | **✓ 强证据**（源码 + 数据吻合） | perk 16 的 sm 13/12 = 装填/弹容，与 wiki 数值一致 |
| 「pm 只影响 UI 描述」 | **⚠ 未证** | 作者只是把描述 id 清零来隐藏文本；引擎是否**完全不读** pm 未知 |
| 「stat 11–17 之外的槽无效」 | **⚠ 未证** | 全表没用过，不能证明不存在其它槽 |
| 装到我们 build 上会怎样 | **⚠ 未测** | 它是 25988413 的包，我们没装；结构一致但未实机 |

## 8. 建议的下一步（护甲线第一枪）

1. **先用 pm/sm 模型复现一次已知结论**：把 perk 16 的 sm 13（装填 ×1.3）改成 ×2.0，
   离线改 + 保哈希 + 上机看装填速度 —— 这是**验证「sm 才是效果」**的最小实验；
2. **再试一次「真·多被动」**：把 perk 18 的 sm 15/16/17（三条）并进 perk 16 的 sm 数组，
   看叠加是否生效（这正是本案的核心能力，但走我们的离线路线，可回滚）；
3. 有了 1、2 再谈 `stat → 语义` 的完整映射表。

## 9. 我们这条线的实测进展（跑完 §8 之后补记）

### 9.1 ✓✓ 表格里的数值**确实参与战斗**（Acclimated 0.5 → 0.0）

| 步骤 | 内容 |
|---|---|
| 改动 | perk 15（应变自如 / Acclimated）`pm[0]` = `0xB5A50096`（type=2 乘法）**0.5 → 0.0**，只改这 4 字节 |
| 离线 | 内容哈希复原 `0xBFB6F7235F9A269C`；`plain_edit.py` 全门禁过 |
| 实机 | 穿 Acclimated 甲站火里/毒气里 —— **不掉血** |

⇒ 结论有两层：

1. **`type=2` 是伤害乘数**，`0.5 → 0.0` 就是 100% 抗性；`type=1` 是加法（Med-Kit 的 `stims_add` 即 type 1）。
2. **纯文件路线能改护甲被动效果**，不需要运行期写内存 —— 这一点和 memmod 时代 `a6` 的读数是
   「写入落地但战斗不动」**不一样**。差别在时机：`a6` 是在引擎**已经把被动缓存进玩家侧结构之后**才写内存；
   我们改的是**启动前**的源表，缓存是从它建的，所以生效。

### 9.2 「改长中间块」的做法：整容器重排（第三方与我们同口径）

> **措辞更正**：先前这里写的是「第一个会改长中间块的工具」，不准确 ——
> 第三方的 `boot.lua` 早就在做同一件事，我们的工具链此前没有而已。

`plain_edit.py` 只会在文件尾追加，而「给某个 perk 加一行」会让**中间某一块的 payload 变长**，
后面所有块偏移平移 —— 只能整容器重排。**两边做法完全一样**：

```
重排 = u32 组数
     + Σ（每组：24 B 头[payload 尺寸重算] + payload）
被改动的块：payload = 56 B 头（id/name_id + 四个 u64 + 保留 8 B）+ pm 行 + sm 行
其余块：原样搬运
```

逐行对照（`boot.lua` `build()` vs `passive_bonus_edit.py`）：

| 步骤 | 第三方 `boot.lua` | 我们 `passive_bonus_edit.py` |
|---|---|---|
| 组数 | `string.char(#records …)` 写 4 B | `struct.pack("<I", len(blocks))` |
| 块头尺寸 | `header:sub(1,12) .. <新尺寸> .. header:sub(17)`（0 基 `+12`） | `struct.pack_into("<I", …, head+12, …)` |
| 数组布局 | `pm_off=56`；`sm_off = 56 + #pm*16`（空则 `-1`） | 同 |
| 保留 8 B | `payload:sub(49,56)` | `out[48:56] = rec["tail8"]` |
| 加给谁 | **每一条 `id≠0` 的 perk** | 只加指定的那一两个 perk |
| 文本 id | 清零（隐藏描述） | 沿用（卡片上可见） |
| sm 行 | 一并复制 | 初期只有 `--add-pm`（`decode/encode` 本来就双向读写 sm，缺的只是 CLI）；**2026-10-24 补上 `--add-sm`**，去重口径也对齐成 12 B |

**唯一实质差别是校正字放哪**：

| | 第三方 | 我们 |
|---|---|---|
| 首选 | **借用现成的对齐头字**（本文件有 **7 个**候选：`head+16` 8 对齐且 `wide` 首字节 = 1，如 `0x9e0+16=0x9f0`） | 不用 |
| 兜底 | 尾块 payload 尾部追加 8 B | **一律**尾块追加 8 B |
| 结果长度 | 只增长「加的行数×16」（本例 4032） | 再 +8（本例 4040） |

> ⚠ 它借头字时**只要求校正字首字节 = 1**（保证 `wide` 的低字节仍是 1），后 3 字节会被写乱。
> 那是按**实体库 28 B 头**（`wide` 是 1 B + 7 B 保留）设计的；本表是 **24 B 头**（`wide` 是 **4 B** + 4 B 保留），
> 借用会把 `wide` 的高 3 字节写成随机值。所以我们**不跟**这个做法，宁可多 8 字节。

工具接下来做的事：

```
parse(33 组) → 目标 perk 重新编码（56 B 头 + pm 行 + sm 行）→ 重排容器
→ 尾部追加 8 B 校正字并把末块 payload 尺寸同步 → 解校正字保持原版哈希 → 4 道门禁
```

两个在实现里踩到的布局坑（值得记）：

| 坑 | 说明 |
|---|---|
| **设置表的 payload 尺寸字段在块头 `+12`** | 实体库的 28 B 头里它在 `+16`，照抄就会写进 `wide` 字节 |
| **末块头位置 = 文件尾 − 24 − 末块 payload** | 少减那 24 B 会让末块尺寸溢出到文件外 |

### 9.3 复现 e15：给 Siege-Ready 加 True Grit 的 ergonomics（+30）

按 §8 的建议与 e15 的教训，只加 **`direct` 键**：

| 加什么 | `0xC8CCB6FA`（weapon_ergonomics）**type=1（加）value=30** 到 perk 16 的 pm 数组 |
|---|---|
| **不加**什么 | `0x35F17BEC`（support_reload_speed）是 **description-only**，加了只有一行文案、没有效果 —— 这正是 e15 当年「叠了却无效」的成因 |
| 文本 id | 沿用 True Grit 那一行的 `0x3415CAF3`（护甲卡片会多一行说明） |

产物 `out/armor3/`（封锁后 `cfce2c425b682ceb`），盘上读回：`perk16 pm[2] key=0xC8CCB6FA type=1 value=30`，
`pm_cnt=3`，整文件 Murmur 仍为原版。**待实机读「武器人机工效是否变好」。**

### 9.4 pm 与 sm 各管什么（本 build 的证据）

| | **pm 行（16 B）** | **sm 行（12 B）** |
|---|---|---|
| 结构 | `{stat 键 u32, 类型 u32, 数值 f32, 描述 loc id u32}` | `{stat 槽位 u32, 标志 u32, 数值 f32}` |
| 性质 | **声明 + 文案**：卡片上的每一条效果说明都来自这里 | **引擎真正施加的数值**：按槽位号落到具体 stat 通道 |
| 是否全部生效 | **不是** —— 看该键的 `reader`：`direct` 会真被读（ergonomics `0xC8CCB6FA`、stims `0x2875F44A`、Acclimated 元素 `0xB5A50096`）；**`description-only` 的六个键只影响文案**（`CC530B21` `35F17BEC` `B4F88129` `33C9C713` `AD5289FE` `22035F3C`） | 只有 7 个槽位被用过（11–17），**每个 perk 的 sm 是 pm 的一个子集**（例：perk 10 有 3 条 pm、只有 1 条 sm） |
| 加一行会怎样 | 卡片多一行说明；`direct` 键会真的改行为 | 直接改对应的 stat 通道 |

**pm 键 ↔ sm 槽位 的对应（按同 perk 内顺序配对，值相同的标 ✓）**：

| sm 槽 | 对应 pm 键 | 证据 | 语义 |
|---:|---|---|---|
| 12 | `0x33C9C713` | perk 16：pm 1.2 ↔ sm 1.2 ✓ | 弹容（ammo capacity） |
| 13 | `0xCC530B21` | perk 16 / perk 10：pm 1.3 ↔ sm 1.3 ✓ | **主武器**装填 |
| 14 | `0x35F17BEC` | perk 41：pm 1.3 ↔ sm 1.3 ✓ | **支援武器**装填 |
| 15 | `0xB4F88129` | perk 18：pm 1.4 ↔ sm **1.6**（不一致，按顺序配） | 未定 |
| 16 | `0xAD5289FE` | perk 18：pm 1.5 ↔ sm 1.5 ✓ | 未定 |
| 17 | `0x22035F3C` | perk 18：pm 0.3 ↔ sm 0.3 ✓ | 未定 |
| 11 | —（perk 14 只有 sm 0.05） | — | 未定 |

⇒ **要让「支援武器装填」真的变，改的是 `sm stat=14`，不是 pm 的 `0x35F17BEC`。**
后者加上只会在卡片上多一句说明（e15 后期确实两行都加了，但那不影响效果这一栏）。

### 9.5 更正：「效果在 sm 行」这句说过头了

上一节把 sm 写成「引擎真正施加的数值」。**目前唯一的实机正例其实是一条 pm 行**：

| 已实机 | 改的是什么 | 读数 |
|---|---|---|
| Acclimated 抗性 100% | **pm 行** `0xB5A50096`（`direct` 键）0.5 → 0.0 | ✓ 站火/毒里不掉血。注意 **perk 15 的 sm 行数是 0**，所以这条效果与 sm 无关 |
| Siege-Ready 主武器装填 | **sm 行** `stat=13` 的数值 1.3 → 2.0 | ✗ 手感没变化 |

⇒ 修正后的模型：

| 层 | 现在的说法 | 证据级别 |
|---|---|---|
| pm 行的 `direct` 键 | **会真的改行为** | ✓✓ 实机（Acclimated） |
| pm 行的 `description-only` 键（六个） | 只当文案，改了不改行为 | ✓ 外部知识库 + 间接（e15 历史） |
| sm 行 | 假设是「按槽位施加的数值」，但**只测过一次且是阴性** | ⚠ 未证 |

于是「支援武器装填只能走 sm 14」这条也降级为**假设** —— 它来自 pm↔sm 数值配对的间接证据，
不是实机读数。真正的判据还在 `out/armor4/` 那一版里等着。

### 9.6 护甲两张表的字段账（已知 / 未知）

**A. `generated_customization_passive_bonuses.dl_bin`（33 组 × `0x63CE0FEB`）**

| 偏移 | 内容 | 状态 |
|---:|---|---|
| `+0` | perk id（枚举 `HelldiverCustomizationPassiveBonus`） | ✓ 已知 |
| `+4` | `name_id`（本地化名字） | ✓ 已知 |
| `+8` | 8 B，**33 条全非零**，像哈希 | ⚠ 半解：**同族共享同一个值**（id 0/1 共用 `0x3642B3057D12359E`；防震内衬 35/36/37 共用 `0x90400C4B2C62C1BA`）⇒ 疑似「族/图标」id |
| `+16` | pm 数组（`PassiveBonusModifier`，16 B 行） | ✓ 布局已知（第三方 boot.lua + 我们明文双向印证） |
| `+32` | sm 数组（`StatModifier`，12 B 行） | ✓ 布局已知；语义 ⚠ |
| `+48` | 4 B（+4 填充） | ⚠ 只有 2 条非零：perk 19 `0x638B9586`、perk 17 `0x644F8A3B`，**这两个值同时出现在 `add_resource_dependencies` 表里** ⇒ 疑似资源/依赖 id |

pm 行：`{键 u32, 类型 u32, 值 f32, 描述 loc id u32}` —— 键 ✓、值 ✓、描述 id ✓（清零即隐藏文案，第三方实证）；
**类型**：`1` = 加法（ergonomics +20/+30）、`2` = 乘法（抗性 0.5→0.0）✓；**`0` / `3` 未解**。
sm 行：`{stat 槽位, 标志, 值}` —— 槽位 ✓（11–17，只见 7 个）、值 ✓ 格式、**`标志` 全表恒 0 ⚠**。

**B. `generated_customization_armor_sets.dl_bin`（422 组 / 6,821 行 × `HelldiverCustomizationKit` 64 B）**

类型库给出的成员名（本 build 类型树）：`+24 Rarity` · `+28 PassiveBonus` · `+40 KitType` · `+48 BodyTypePieces(16 B)` · `+0..+20` 六个未命名 u32 · `+32` 8 B 未命名 · `+44` f32。

> ⚠ **本轮快速探测（按 64 B 逐行读 `+24/+28/+40`）拿到的值不像枚举**（`+24` 出现 793 种取值、
> `+40` 593 种），说明**这 422 组的行跨距/对齐不是统一的 64 B**，或组里混了别的类型。
> **所以这张表目前只有「类型名级」的认知，value 级一律算未知**，不要照这些偏移去写。

## 10. memmod 时代的档案：效果确实分「Passive 行」和「Stat 行」两半（2026-10-24 补）

上一节的疑问（sm 到底读不读）在旧知识库里已有答案，权威文件是：

| 文件 | 内容 |
|---|---|
| `D:\mod\c11-recon\sdk-0.30.3\ArmorPassiveCatalog.json` | **32 个被动 × 逐行 `modifiers[]` / `stats[]` / `reader` / `follows` + 411 件甲的 kit 表** |
| `D:\mod\c11-recon\sdk-0.30.3\docsrmor-passives.md` | SDK 的逐被动表（21 full / 10 partial / 1 unknown） |
| `D:\mod\docs\CAPABILITIES.md` §1.4 / §1.4a | 判据与三条路；(b) 写 stat 组件被标「需授权」 |
| `D:\mod\docs\HISTORY.md` | a6/a14 的过程、`(c) 加 stat 行` 被标「未证」 |

**两半的分工**（`model.readers` 原文）：

| 半 | 谁读 | 时机 |
|---|---|---|
| **passive 行（我们的 pm）** | `EntityAttribute 0x11D9DF0` 按 key 直接查 ⇒ `reader = direct` 才跟随换甲 | 运行期，随时 |
| **stat 行（我们的 sm）** | `0x11DA190` 施加 → `SetStat 0xA076C0` 写入 | **仅出生时**，按「穿的那件甲」 |

`description-only` 的官方解释原文：
*"description text; the effect is a stat row the kit worn at spawn applies: a swap never changes it"* ——
这正好合上我们观察到的 Acclimated（`direct`，改 pm 就生效）与 e15（`description-only`，叠 pm 无效）。

### 10.1 目录与我们的二进制**逐条对上了**

| 项 | 目录（SDK） | 我们的明文 | 结果 |
|---|---|---|---|
| `modifier type` | `Set=v=x` / `Add=v+=x` / `Multiply=v*=x` / `Time=v+=x` | 我们看到的 0/1/2/3 | ✓ **0=Set 1=Add 2=Multiply 3=Time**（之前只知 1/2） |
| perk 16 `stats[]` | `[{13 primary reload, mul 1.3}, {12 ammo capacity, mul 1.2}]` | sm `(13,0,1.3) (12,0,1.2)` | ✓ |
| perk 41 `stats[]` | `[{14 support reload, mul 1.3}]` | sm `(14,0,1.3)` | ✓ |
| **全部 6 个带 stats 的 perk** | — | — | **逐条比对：0 处不一致** |
| `+8` 字段 | 每个被动的 `icon`（perk 16 = `0x8667ED2CA6A6846F`） | `+8` 逐条相同 | ✓ **`+8` = 图标 id**，不是"族 id" |

⇒ **sm 行布局确定：`{stat u32, add f32, mul f32}`** —— 我先前当成「标志位」的那 4 字节，其实是 **add 项**（全表都是 0.0）。

### 10.2 stat 槽位的权威名字（7 个全齐）

| stat | 名字 |
|---:|---|
| 11 | 未命名（目录注：`0x607ED0` 缩放一个整数数量） |
| 12 | ammo capacity |
| 13 | primary reload |
| 14 | support reload |
| 15 | sidearm reload |
| 16 | sidearm draw / holster |
| 17 | sidearm recoil |

### 10.3 对当前实验的三条直接影响

1. **必须穿 perk 16 的甲**：stat 行是「出生时穿的那件甲」施加的。
   之前 sm13（主武器装填）读数为空，**头号嫌疑就是当时穿的甲不是 Siege-Ready** ——
   后来 Acclimated 那次能生效，是因为那件甲确实带 perk 15。
2. **`out/armor4` 正是旧档案里点名「未证」的那条路**：
   HISTORY 原文 *"(c) 给 perk 16 的 stat 数组加一行 12 B 行 + count 2→3 ⇒ 多格写、
   且第 3 行会不会被 `0x11DA190` 施加未证"*。我们这次就是去补这个洞。
3. **`kits[]` 里没有 stat 行**（411 件甲只有 id/set/dlc/rarity/名字/wiki 三数字）⇒
   「护甲值 / 速度 / 耐力」不走 stat 通道，它们在 wiki 记的是 `armorRating 100 / speed 500 / staminaRegen 100`，
   文件里的落点仍未定位。

## 11. stat 11 是什么？（2026-10-24 调查结论：**不是占位符**）

**本地三处证据拼起来就够定性了**：

| 来源 | 内容 |
|---|---|
| `ArmorPassiveCatalog.json` perk 14 UNFLINCHING | `stats: [{stat: 11, name: "unnamed (0x607ED0 scales an integer quantity)", add 0.0, mul 0.05, describedBy: null}]` |
| 同上 `note` | *"armor_rating, stat 11 x0.05 (no modifier row) follow the kit worn (at spawn) instead"* |
| `docs/armor-passives.md:230` | `14 UNFLINCHING partial: flinch_prevention (direct), armor_rating (armor rating, NO), radar_scan_interval (direct), stat 11 x0.05 (stat row, NO)` |
| 我们的二进制 | perk 14 的 sm 只有一条：`stat=11, add=0.0, mul=0.05` ✓ 与目录逐值一致 |

结论分三层：

1. **它是真被施加的 stat，不是占位符** —— 有值（×0.05）、有施加路径（出生时 stat 行）、
   而且 `describedBy: null` 说明它**没有对应的 pm 描述行**，所以护甲卡片上永远看不到它。
   这正是它看起来"神秘"的原因：**它在 UI 上不存在，但在数据里活着**。
2. **它为什么没名字**：SDK 的生成器只在代码里找到 `0x607ED0` 这一处"把一个**整数**数量乘以该值"，
   没能把它接到任何一个语义名上，于是老实写成 `unnamed (…)`。
   —— 也就是说这是**"有名字我们不知道"那一类**，不是"未完成"。
3. **它大概率就是「受击时的视角/镜头冲击」缩放**：wiki 的 UNFLINCHING 词条写着
   *"It reduces **damage recoil** by **95%** and tones down camera shakes when staggered"* ——
   `1 − 0.95 = 0.05`，与数据里的 `×0.05` 精确吻合；而 perk 14 另外三条 pm
   （`flinch_prevention` Set 0、`armor_rating` Add、`radar_scan_interval` Time 2.0）
   已经分别对上了 wiki 说的另外三件事，剩下的就是它。

> ⚠ 仍是推断的地方：wiki 说"damage recoil 95%"，我们只知道"某个整数 ×0.05"。
> 判定实验（1 个变量）：把 perk 14 的 `stat 11` 从 **0.05 改成 1.0**，穿 UF-84 Doubt Killer
> （Unflinching 甲）被打时看镜头冲击是否**恢复成普通甲那种晃动**。若恢复 ⇒ 名字钉死。

## 12. Armor rating / Speed / Stamina Regen 住在哪？（2026-10-24，权威答案）

**不在任何单条 `.dl_bin` 行里**，而是「**全局 3 行 class_table** × **每件甲的 9 个部件档位**」两层算出来的。
权威来源：`D:\mod\c11-recon\sdk-0.30.3\ArmorStatsCapabilities.json`（`classes` / `formulas` / `executableData` / `kits[].weights`）。

### 12.1 第一层：class_table —— 3 行，**在 `game.dll` 的可执行数据页里**

| class | `armorValue` A | `speedFactor` S | `staminaFactor` F | 显示 rating | speed | stamina |
|---|---:|---:|---:|---:|---:|---:|
| light | 0.0 | 1.1 | 0.75 | 50 | 550 | 125 |
| medium | 1.0 | 1.0 | 1.0 | 100 | 500 | 100 |
| heavy | 2.0 | 0.9 | 1.5 | 150 | 450 | 50 |

显示公式（`formulas.display`）：`RATING = 50 + 50×A` · `SPEED = 500×S` · `STAMINA = 100×(2−F)`。

伤害曲线也在这里（同一页）：`A = −1 / 0 / 1 / 2 / 3` → 伤害 **×1.66 / 1.25 / 1.00 / 0.75 / 0.65**（线性插值，读在每一次命中）。

> `executableData` 原文：*"The class tables and the damage curve sit in **game.dll pages that are executable at run time** … written as reviewed executable data … only their exact 4-byte entries … the page protection is never changed."*
> ⇒ **这三行不是 .dl_bin 表**，是代码页里的 f32 常量。

### 12.2 第二层：每件甲的 9 个部件各属哪一档 —— **这一层在文件里**

`ArmorStatsCapabilities.kits[]` 每件甲都带 9 个部件的 weight：
`cape · torso · hips · left_leg · right_leg · left_arm · right_arm · left_shoulder · right_shoulder`
（`fieldInstances` 里对应 `hd2.fields.armor_kit` 的 1,141 个实例 = 9 × 127 件）。

聚合规则（`formulas`）：

| 数字 | 怎么算 |
|---|---|
| **rating** | 只取**评分槽**（torso / 两条腿 / 两条臂 / 两肩，**不含 cape 与 hips**）的 `A` 求**均值**，再套被动 armor 行：`(Set 否则均值) + ΣAdd`，再 `× ΠMultiply`；**每次命中都读** |
| **speed** | **全部 9 件**（含 cape 与 hips）的 `S` 求均值 |
| **stamina** | **全部 9 件**的 `F` 求均值（同时缩放耐力消耗与恢复、跳跃/扑倒/攀爬/滑铲开销） |

⇒ 这两层合起来才解释得通两件旧事：

1. **只有 3 档，却能显示 75 / 125 / 175 这类中间值** —— 是**混搭档位的均值**（例如护甲件是 light、腿是 medium ⇒ A=0.5 ⇒ rating 75）；
2. **memmod 时代改 piece 的 `+16`(0/1/2) 卡片一动不动**（`armor_kit_table` 记忆里的 ✗）——
   要么 `+16` 不是那个 weight，要么改的时候卡片已按旧值缓存。

### 12.3 对文件路线的含义

| 想改什么 | 在哪 | 能不能走我们的路线 |
|---|---|---|
| **三档基准**（让所有轻甲更硬、更快） | `game.dll` 代码页 f32 | ✗ **不在 .dl_bin**，属另一条（需授权/改 exe） |
| **单件甲的三数字** | 该甲 9 个部件的 class（套件表内） | ⚠ **文件可达**，但 piece → class 的实际编码**尚未确认**（旧试验阴性） |
| **+25 之类的被动加成** | 被动表的 `armor_rating` pm 行（Add） | ✓ 已证（`type=1` = Add） |

## 13. `game.dll` 加密吗？能解吗？（2026-10-24 一手复核）

### 13.1 一手读数（本 build `26088801`，盘上 49,075,800 B）

| 检查 | 读数 | 判读 |
|---|---|---|
| `MZ` / `PE  ` | ✓ 明文 | 只有**外壳**是明文 |
| 段表 | `.text .rdata .data .pdata _RDATA .rsrc .reloc`（名字正常） | 旧记忆里的 `.winlice`/`.vm_sec`/`.boot` 在**本 build 已不复存在** |
| `.text` | 33,128,448 B，**熵 = 8.000** | 完全随机 ⇒ **加密/压缩** |
| 入口点 | RVA `0x1F10CEC` 处 32 B = `1b1e6ad4…`（随机） | 代码不是明文 |
| 常见 x86-64 序言 | `55 48 89 E5` **0** · `48 89 5C 24 08` **0** · `48 83 EC 28` **0** | 无明文机器码 |
| `.rdata` | 熵 7.214；`stingray` 仅 **2** 处命中，`Helldivers`/`armor` **0** | 字符串表基本也加密 |
| `.data` | 熵 6.109 | 部分可读，但关键常量不在这里 |

> 结论：**盘上这份是「运行时解密」的镜像** —— 磁盘副本没有任何可用的明文代码。

### 13.2 「解」的三条路与各自状态

| 路 | 状态 | 依据 |
|---|---|---|
| **离线找密钥/明文副本** | ✗ **没有** | 历史已全盘搜过 3,558 个文件 / 78.2 GB，0 命中；`.dl_bin` 的 X25519 收件人密钥是**数据表专用**，与 game.dll 无关 |
| **进程内只读 dump（实时）** | ✗ **被 EAC 掐断** | [`MEMORY-ACCESS`](../boundaries/MEMORY-ACCESS-25988413.md) §1：`OpenProcess` 成功但 EAC 把 `PROCESS_VM_READ` 剥掉 ⇒ `ReadProcessMemory` = `err=5`；`MiniDumpWriteDump` = `E_ACCESSDENIED`（0 B 文件） |
| **旧 build 的全量转储** | ✓ **磁盘上还有 61 GB** | `E:\hd2-dumps\kept\`：`crash-20128` 11.1 GB、`crash-124838` 11.4 GB、`crash-125128` 10.3 GB（2026-10-17/18，build ≈ `25988413`）—— 里面是**解密后的 game.dll 镜像** |

⇒ 一句话：**当前 build 解不了；但旧 build 的解密镜像我们手里有。**

### 13.3 这对「护甲三数字」意味着什么

`class_table`（3 档 × armorValue/speedFactor/staminaFactor）与伤害曲线都在**加密的 `.text` 代码页**里，
所以**改三档基准**这件事在文件路线上做不到。

但**读**它仍有可能：在旧转储里按数值指纹搜索
（例如伤害曲线 `(-1.0, 1.66) (0.0, 1.25) (1.0, 1.0) (2.0, 0.75) (3.0, 0.65)` 这 5 对 f32，
或 class 三行 `(0.0, 1.1, 0.75) (1.0, 1.0, 1.0) (2.0, 0.9, 1.5)`）。
找到就能确认布局与取值；⚠ 但那是**旧 build**，数值/布局到本 build 是否一致需另证。

### 13.4 和 `.dl_bin` 不是同一套东西（关键区别）

| | **`.dl_bin`** | **`game.dll`** |
|---|---|---|
| 方案 | libsodium **sealed box**：X25519 + XSalsa20-Poly1305，48 B 头 = `epk(32)+tag(16)` | **运行时壳**（老 build 段名 `.winlice` / `.vm_sec` / `.boot` = WinLicense/VMProtect 系特征；本 build 段名恢复但 `.text` 熵 8.000） |
| 解密发生在 | **我们手上**（有私钥就能离线解） | **loader 装载时**，密钥/算法在壳内 |
| 旧 dump 给的是什么 | **一把钥匙**（私钥烘在 exe 里，按 RVA `0x1653160` + XOR 常数还原） | **那一个 build 的明文镜像**，不含钥匙 |
| 跨 build | ✓ **一把钥匙开所有 build**（本 build 55 张表就是这么解开的） | ✗ **每 build 作废**（旧/今段表布局已不同） |
| 能否拿来解当前 build | ✓ | ✗ |

> 所以「像 `.dl_bin` 那样从旧转储提取」这个类比**不成立**：`.dl_bin` 提取到的是常量钥匙，
> `game.dll` 提取到的只是某一版的内容。想验证「壳是否也用静态密钥」需要**旧 build 的密文/明文对**，
> 而我们手上只有 dump 里的明文，没有旧的 `game.dll` 密文 ⇒ **现阶段无法验证**，
> 结论「当前 build 解不了」是**否证**（无钥匙、无双对、实时读被 EAC 挡），不是猜测。

> 另注：即使解出来，**改** game.dll 也早被关死 —— 决胜实验证实加载闸门查的是**文件身份**（换名/换目录返回 193）。
> 所以这条路的价值只剩「读常量/偏移」，不涉及写。

### 13.5 拿到旧 build 的密文之后：它不是「加密」，是「加壳/压缩」

密文来源：`D:\Helldivers 2_25480438_backup\data\game\game.dll`（15,522,408 B，build `25480438`）。
PE 头明文，**16 个段**，其中 `[0..6]` 段名被抹成 8 个空格，另有 `.vm_sec` / **`.winlice`** / **`.boot`**。

**决定性的一行读数**：

| 段 | vaddr | vsize（内存） | rawsize（文件） | 熵 |
|---|---|---:|---:|---:|
| [0]（原 `.text`） | `0x1000` | **34,667,155** | **8,718,336** | 7.999 |
| [2] | `0x263C000` | 18,462,204 | **138,240** | 7.998 |
| [13] **`.winlice`** | `0x39ED000` | 8,806,400 | **0** | — |
| [14] `.boot` | `0x4253000` | 4,773,888 | 4,773,888 | 7.937 |

⇒ **文件里的字节数和内存里的字节数根本不成比例**（34.7 MB 的段在文件里只有 8.7 MB；`.winlice` 在文件里是 **0 字节**）。
这说明它不是「整段加密、原样放回」，而是 **WinLicense 系的加壳 + 压缩 + 代码虚拟化**：
盘上只放**打包后的载荷**，镜像由 loader **在装载时重建**。

于是「像 `.dl_bin` 那样提取密钥再解」在**格式层面**就不成立：

| | `.dl_bin` | 旧 `game.dll` |
|---|---|---|
| 密文 ↔ 明文 | **逐字节一一对应**（流密码） | **不存在对应**（vsize ≠ rawsize，有内存专属段） |
| 提取到钥匙后 | 可解任意 build 的同类文件 | 也解不出——没有可「解」的完整密文 |

**能做的仍然只有一件**：在旧 dump 的**已重建镜像**里读东西（历史已这样拿到 `.dl_bin` 密钥、
`0x11DA190` / `0xA076C0`）。想拿 `class_table`，就按数值指纹去旧镜像里搜；想拿**当前 build**，仍被 EAC 挡着。
