# 更新后差异：25988413 → 26088801（7.2.1 hotfix）

官方说明只有一条：**修"另一名玩家加入/离开小队时崩溃"**。下面是逐层实测的差异，
全部只读、离线（解封 `data/game` 里的密封盒，不启动游戏、不碰进程内存）。

**结论：这次更新没有改动任何一张表。** 变的是可执行代码和 bundle 打包。

> 时间对齐（steamdb，UTC → 本地 UTC+8）：
> `7.2.0` = 2026-10-20 09:00 UTC = 17:00 本地（build 25988413）
> `7.2.1` = 2026-10-22 11:59 UTC = **19:59 本地**（build 26088801）

---

## 0. 更正：上一版报告把"我们自己的 mod 负载"误报成游戏改动（✗ 已推翻）

上一版写的是"唯一有内容变化的是 `customization_passive_bonuses`"。**这是错的**，
原因是我们自己的实验污染了基线缓存，已修正。

铁证（三份文件都在本机，sha256 可直接复核）：

| 文件 | 时间 | 明文 | sha256(明文) |
|---|---|---:|---|
| `refs/dlbin/demo/vanilla_generated_customization_passive_bonuses.dl_bin` | 10-22 09:49 | **4016 B** | `6ba67061fa05b1aa…` |
| `refs/dlbin/demo/passives_medkit.sealed.dl_bin`（我们做的护甲多被动实验负载） | 10-22 09:49 | 4992 B | `ca5b6b33dfe0b4b6…` |
| `refs/dlbin/plaintext-all/generated_customization_passive_bonuses.dl_bin`（旧缓存） | 10-22 09:52 | 4992 B | `ca5b6b33dfe0b4b6…` ← **与 mod 负载一致，不是原版** |
| 当前 build（26088801）实测 | 10-22 21:29 | **4016 B** | `6ba67061fa05b1aa…` |

时间线：

```
09:30  写回 color_set 实验 → 09:37 崩溃 → 09:39 还原
09:49  备份原版 passive（4016）+ 生成护甲多被动负载（4992）
09:52  ★ 全表明文 dump —— 此时 data/game 里躺着我们的负载，缓存把它当成了原版
09:54  同一负载换 epk 重封装（fresh_epk）
…      之后还原成原版
18:49  全表字典生成，passive = 4016（已经是原版）
19:59  7.2.1 发布（steamdb）
20:56  Steam 写盘
```

所以：**原版 25988413 与 26088801 的 `passive_bonuses` 逐字节相同**，中间那次"变化"是我们自己造的。

`tools/plaintext_cache_audit.py` 就是为这件事写的：拿 `refs/dlbin/demo/vanilla_*.dl_bin`
（部署前备份）和当前 build 两条独立证据交叉查缓存，这次一条命中：

```
缓存条目 22 个，可疑 1 个
  ！generated_customization_passive_bonuses.dl_bin: cache=4992 B demo=4016 B current=4016 B
      -> differs-from-current-build-and-demo
  ✓ 已用当前 build 原版覆盖
```

## 1. 密钥与封装层（✓ 实测）

```
55 张 generated_*.dl_bin + dl_library.dl_typelib   全部解封成功，0 失败
```

解封用的是同一个 `recipient.sk`。只要它还能解，我们的全部表工具链就不用改。

## 2. 类型库（✓ 逐字节相同）

```
旧明文 1,080,024 B   新明文 1,080,024 B   差异字节 0   差异段 0
类型 1208 / 成员 7349 / 枚举 345           全部相同
零个类型的 size32/size64 发生变化
```

顺带记一个易错点：磁盘上的 sealing 是 `明文 + 48 B`（32 B 临时公钥 + 16 B 校验），
所以"文件大小"和"明文大小"差 48；把"文件大了 48 B"当成"类型库改了"就错了。

## 3. 表：55 张全部无变化（修正后）

```
判定（基线 = 原版 25988413 明文）    数量
identical                          22   明文逐字节相同
structure-same                     33   明文字节数 + 组数相同（无旧明文的表）
changed                             0
```

`refs/build-diff.json` 与 `refs/build-geometry-diff.json` 已用修好的基线重新生成。

## 4. 可执行文件与 bundle（✓ 变了，但都不是表）

```
bin/helldivers2.exe   28,743,256 B   sha256 2ce8b3d7… → 0acc07de…   大小不变、代码变
data/game/game.dll    49,075,800 B   sha256 a457433f… → 6d1d4d3b…   大小不变、代码变
data/bundles.nxa       6,505,586 → 6,505,737 B                        +151 B
data/bundle_database.data                                           未变（哈希相同）
```

bundle 大小变化（只列变了的）：

```
bundles.02.nxa   526,427,457 → 526,361,921   -65,536  (-64 KB)
bundles.03.nxa   778,550,954 → 778,485,418   -65,536
bundles.06.nxa   796,403,056 → 796,468,592   +65,536  (+64 KB)
bundles.09.nxa   712,254,666 → 712,189,130   -65,536
bundles.10.nxa   714,089,772 → 714,024,236   -65,536
其余 25 个 bundle                       大小完全不变
```

±64 KB 是整块（0x10000）增减，典型的重新打包/对齐，不是资源被成批删改。
`bundles.00.nxa`（我们解 strings 的那个）大小完全没变，重跑战备显示名的输出**与原文件逐字节相同**。

## 5. 我们的东西还能不能用（✓ 全部复现）

用新 build 的明文重跑一遍：

```
stratagem_settings          153 行  显示名 145  描述 129  长描述 49  状态 153   → 与已发布 JSON 逐字节相同
projectile_settings         355 行  名字 225
weapon_customization        252 行  名字 234
customization_armor_sets    422 行  名字 389
customization_passive_bonus  33 行  名字  33
unit_customization           12 行  名字  11
planet_data                 438 行  名字 399
explosion 引用链             424 行  命名 103，引用边 210，悬空 0
```

已装的 5 个 patch 全部是资源覆盖（`patch_0/1/2/4` 各 1 个 `lua`，`patch_3` 是
bones/material/mesh/texture 的外观包），**没有一个覆盖 `generated_*.dl_bin`**，
所以它们不会把旧表盖回去。Lua 本身是否需要跟着新版改，得实机看日志才知道（未验证）。

## 6. 附：我们那份"护甲多被动"实验负载长什么样（副产品，不是游戏改动）

`customization_passive_bonuses` 的行是**定长 56 B 记录 + 变长条目数组**：

```
记录 56 B：
  +0   u32   序号            +4   u32   名字的本地化 ID
  +8   u32   ID（未定性）    +12  u32   ID（未定性）
  +16  u32   56（记录长度，自描述）      +20  u32  0
  +24  u32   条目数   ← payload = 56 + 条目数×16，33 组全部成立
  +28  u32   0
  +32  u64   0xFFFFFFFFFFFFFFFF          +40/+48  u32 0
条目 16 B：u32 属性 id | u32 种类(1/2/3) | f32 值 | u32 附加 id
```

* 原版条目数：1 / 2 / 3 / 4 / 5 条（4/15/12/1/1 个被动）。
* 我们的负载：30 个被动各**多 2 条**、1 个多 1 条、2 个不变；多出来的两条固定是
  `id 0x2875f44a 种类1 ×2.0` 与 `id 0x93eb16a7 种类3 ×2.0`。
* 识别"表被 mod 改过"的快捷信号：原版这一列 `wide` 字段全是 `1`，负载里出现了
  `0xC601`、`0x72E1…` 之类的杂值 —— 这也是我一开始该警觉的地方。

## 7. 复跑

```bash
python tools/plaintext_cache_audit.py --sk <sk>   # 先查缓存干不干净（本轮新增）
python tools/build_diff.py            --sk <sk>   # 文件层 + 封装层 + 结构层
python tools/build_geometry_diff.py   --sk <sk>   # 55 张表对旧字典几何
python tools/build_cache.py           --sk <sk>   # 明文按 buildid 另存，作为下一轮基线
```

## 8. 三态小结

**✓ 实测**：密钥没变（56/56 解封成功）；类型库明文 0 差异；55 张表 **0 变化**（22 张明文全同、
33 张结构全同）；exe/game.dll 哈希变、大小不变；bundles.nxa +151 B、5 个 bundle ±64 KB；
战备名字重跑结果与已发布文件逐字节相同；原版 passive 表 sha256 在 25988413 与 26088801 完全一致。

**✗ 否证**：上一版"这次更新改了一张表"—— 否证，那是我们自己的 mod 负载污染了基线缓存；
`+24` 不是"记录长度"（是条目数，记录长度在 `+16`）；"文件大 48 B = 内容变了"—— 否证，那是封装头。

**⚠ 未定**：33 张没有旧明文的表只能证明结构没变、不能排除"同尺寸下的数值改动"；
已装 Lua patch 在新版是否需要调整（未实机）。
