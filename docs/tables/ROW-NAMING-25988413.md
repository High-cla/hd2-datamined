# 表内逐行名字的两种取法（build 25988413）

> 55 张 `.dl_bin` 里**只有 6 张**带行级名字，而且它们的取法不能混用。这篇讲清楚判据、证据、
> 以及**上一版在哪两张表上取错了名**。

## 1. 结论

| 判定 | 结论 |
|---|---|
| ✓ 实测 | 行名有两条路：**位置法**（字符串块里第 i 条串 = 第 i 行）和**指针法**（行内 u64 是 payload 相对偏移）。**指针法更强** |
| ✓ 实测 | 6 张表靠指针 100% 覆盖：weapon_customization 252、stratagem 153、planet_override 44、status_effect 73、language 15、stratagem_upgrade 1 |
| ✓ 实测 | 两种机制都能用时有**独立交叉验证**：weapon_customization 的 8 个组 **240/240 完全一致** |
| ✓ 实测 | 位置法在 2 张表上给出过错名：**planet_override 10 行**、**status_effect 2 行**；weapon_customization 第 9 组（12 个染料）位置法直接吐出二进制碎片 |
| ⚠ 推断 | 剩下 49 张表没有行级名字指针（扫过全部 55 张，只有这 6 张命中） |

## 2. 两条路，以及为什么必须是"不同的串"而不是"能解析"

容器是

```
payload = u64 0x10 | u64 行数 | 行数 × 步长 | 可读字符串块
```

**位置法**：块里第 i 条可打印串就是第 i 行。只在"块里恰好一行一条串"时正确。代码里判据必须是
`len(块内串) == 行数`；写成 `>=` 就会在"每行好几条串"的表上**静默取前 N 条**，看起来成功、实际全错。

**指针法**：行内某个 u64 是相对 payload 起点的偏移，直接指向属于这一行的串。

判据的关键在于：**偏移 0 对每一行都"能解析"**（都指向块首）。所以"能不能取到字符串"这个测试
对任何小整数都成立，毫无判别力。真正有判别力的是：

```
hits     = 该槽在各行都能解析出可打印 NUL 结尾串的行数
distinct = 这些串里有多少个是不同的
指针     ⇒  hits ≈ 行数  且  distinct ≈ hits
小整数   ⇒  hits 少，或 distinct 只有个位数（反复指向同一条串）
```

用这个判据扫 stratagem（400 B × 153 行）：

```
slot   hits/rows  distinct
 +16    153/153      151     <== 显示名指针
 +24    128/153      116     <== _name 键指针
 +32    128/153      116     <== _desc 键指针
 +72      5/153        1        巧合
+152      1/153        1        巧合
```

## 3. 独立交叉验证：240/240

`weapon_customization_settings` 有 9 个组，其中 8 个组的块恰好一行一条串——两条路都能走。
比对结果：

```
agree 240, differ 0
```

第 9 组是 12 个染料（PaintScheme），块里**混着颜色二进制**（名字后面跟着 `u32 3` 和若干 f32 三元组）。
f32 的最高字节常是 `0x3E`/`0x3F`（`>`/`?`），于是位置法读出来的"名字"长这样：

```
'=Forest Solid'  '>Forest Camo'  'B>Arctic Solid'  'Z?Arctic Camo'  'rh>'  'p=?ff&?'  'i*G+'
```

16 条串对 12 行，前 12 条里掺着 3 条纯二进制碎片。指针法给出的是干净的 12 个：

```
Default / Helldiver Classic Solid / Forest Solid / Forest Camo / Arctic Solid / Arctic Camo
Desert Solid / Desert Camo / Urban Solid / Urban Camo / Night Solid / Venus Solid
```

同一道理：`planet_override` 位置法有 10 行与指针不符（植物群系组里混着同样的二进制），
`status_effect` 有 2 行不符（该表有重复名，`distinct` 68 < 行数 73，位置法把重复名顶掉了）。

⚠ **上一版把这种现象解释成"约 1% 条目带对齐填充字节，原样保留"是错的**——那是位置法的产物，
不是数据本身的形状。

## 4. 六张表的指针偏移

| 表 | 行数 | 指针 | 说明 |
|---|---:|---|---|
| `weapon_customization_settings` | 252 | `+0` | 类型库里字段名就叫 `DebugNameOffset` |
| `stratagem_settings` | 153 | `+16` / `+24` / `+32` | 显示名 / `nui_*_name` 键 / `nui_*_desc` 键；键只有 128/153 行有 |
| `planet_override_settings` | 44 | `+0` | 行星 / 生物群系名 |
| `status_effect_settings` | 73 | `+8` | 只在该表 160 B 步长的组里；另有 29 行走 40 B 步长组，块里没有名字 |
| `language_settings` | 15 | `+32` / `+48` / `+8` | 语言名（`gb` 行缺失，回落到 locale）/ locale（`en-GB`）/ 代码（`us`、`bp`） |
| `stratagem_upgrade_settings` | 1 | `+0` | `AMMO RACK MOUNTED TURRET` |

**指针偏移必须按 (表, 步长) 记**，不能只按表记：`status_effect_settings.dl_bin` 里同时存在 40 B 和
160 B 步长的组，`+8` 只在前者是名字指针。按表套用会把乱码当名字。

## 5. 局限

* `status_effect_settings` 102 行里只有 73 行能命名（40 B 步长那 29 行的块里没有名字）。
* 其余 49 张表没有行级名字指针。它们要名字得靠别的来源（外部字典 / 交叉引用），不是这张表自己带。
* 指针只保证指到"属于这一行的串"，**不保证那条串就是显示名**——stratagem 的 `+16` 是显示名这一点，
  是靠 153 条名字全部形如 `系族. 名字` 且与系族对得上才确认的。

## 6. 工具与产物

| 工具 | 作用 |
|---|---|
| `tools/row_pointer_sweep.py` | 扫全部 55 张表，用 `distinct` 判据找出指针槽，并做位置法交叉验证 |
| `tools/probe_row_name_offsets.py` | 单表深挖：列出命中/不命中、每种串的类别（显示名 / 键 / 描述键） |
| `tools/table_row_names.py` | 按指针抽名字，输出 `refs/table-row-names.json`（每张表标明用的机制） |
| `tools/table_export.py` | 整表导出 CSV + Markdown，名字列走指针，字段逐槽给 hex / f32 |

产物：`refs/table-row-names.json`、`refs/exports/<table>.csv|md`（六张表）。

## 7. 复现

```bash
python tools/row_pointer_sweep.py --sk <你的>/recipient.sk
python tools/probe_row_name_offsets.py --table stratagem_settings --stride 400 --sk <你的>/recipient.sk
python tools/table_row_names.py --sk <你的>/recipient.sk --json refs/table-row-names.json
python tools/table_export.py --table weapon_customization_settings --sk <你的>/recipient.sk --out out/wc
```

密钥（`recipient.sk`）不在本仓库里；没有它只能得到密文。

## 8. 出处

* 容器结构与指针：本机 `data/game/generated_*.dl_bin`（解密后）自证，见 §2 判据。
* 字段名（`DebugNameOffset` 等）：本机 `dl_library.dl_typelib`。
* weapon_customization 的 88 B 结构与字段语义：xypwn/filediver `datalibrary/weapon_customization.go`（MIT）。
* stratagem 的冷却 / 系族 / 战备名：HD2Runtime 0.28.1 `StratagemAuthoringCapabilities.json`（MIT）。
