# `stratagem_settings` 解码（build 25988413）

> 153 行 × 400 B，12 个组。行名 153/153 从表内尾部字符串块取到（`BACKPACK. SUPPLY BACKPACK`
> 这类显示名与 `nui_stratagem_*` 本地化键成对出现）。
> 整表导出：`refs/exports/stratagem-rows.csv`（153 行 × 71 字段）。

## 1. 行结构

类型库给出 `StratagemInfo` = **400 B / 67 个成员**，其中 **14 个成员的类型是具名枚举**
（类型名来自公开哈希表；**枚举值本身没有名字**，只能给数值）：

| 偏移 | 类型 | 本机观测 |
|---:|---|---|
| `+0` | `StratagemType` | **153 个不同值** ⇒ 每行一个战备 id |
| `+56` | u32 | **只有 4 个不同值**（`0x2d96f9e6`×120 / `0x721d3b12`×16 / `0x84e3a5a8`×10 / `0xe4cd3471`×7）⇒ 像"投送方式"枚举 |
| `+60` | `StratagemCategoryType` | **8 个不同值**（2×94、3×17、0×12、1×11、4×11、5×6、6×1、7×1）⇒ 战备分类 |
| `+64` | `StratagemButtonDirection`（16 B） | 152 个不同值 ⇒ 输入序列（方向键组合） |
| **`+80`** | **`max_uses`** | **6 个不同值**：`0xFFFFFFFF`×125（无限）、1×12、3×7、2×6、4×2、5×1 |
| `+84` | f32 | 3.0×50、0×42、5.0×40 ⇒ **不是冷却**（见 §2.5），像"充能/次数" |
| `+96` | f32 | 4.0×36、6.0×9、0×83 ⇒ 未定 |
| **`+104`** | **f32** | **冷却秒数**：480.0×42（支援武器）、70.0×15、75.0×14、80.0… **与 wiki 一致** ✅ |
| `+112` | `StratagemOriginType` | 来源类型 |
| `+116` | `StratagemCallInType` | 呼叫方式 |
| `+120` | `StratagemCallInLogic`（2 B） | |
| `+148` | `StratagemCooldownType` | 冷却类型 |
| `+184` | `StratagemHUDType` | HUD 显示类型 |
| `+212` | `StratagemBeaconColor` | 信标颜色 |
| `+260` | `StratagemInfoFlag` | 标志位 |
| `+372` | `UnitCustomizationCollectionType` | 关联的涂装集合 |

## 2.5 用 wiki 反查出冷却字段（并纠正上一版）

wiki 的战备页给了每个战备的 Base Cooldown：轨道 70/75/80/180/240/300、鹰式 15、支援武器 480。
拿这些数值去扫 400 字节行里每一个 4 字节槽：

```
+104  480.0×42、70.0×15、75.0×14、80.0…   ← 冷却（f32 秒）
+84   3.0×50、5.0×40、0×42               ← 不是冷却
+96   4.0×36、6.0×9                      ← 未定
```

⇒ **`+104` 是冷却秒数**（f32），**上一版把 `+84` 写成"像冷却秒数"是错的**，已在本文件更正。

## 2.6 wiki 的四类许可 vs 本表的两个分类字段

wiki（<https://helldivers.wiki.gg/wiki/Stratagems>）把战备分为 **4 个许可色**：

| 类别 | 颜色 | 包含 |
|---|---|---|
| Offensive | 红 | Orbital Strikes、Eagle Strikes |
| Supply | 蓝 | Support Weapons、Backpacks、Vehicles |
| Defensive | 绿 | Sentries、Emplacements |
| Mission | 黄 | 目标类（Resupply / Reinforce / 携带数据…）|

本表里正好有两个分类字段：

* **`+56` 只有 4 个不同值** —— 数量与 wiki 的 4 类吻合，**⚠ 但内容未对上**；
* **`+60`（`StratagemCategoryType`）有 8 个值** —— 比 wiki 的 4 类更细，**⚠ 未映射**。

⚠ **这两条都只是形状吻合，不能当结论**：这张表的行名与行号**不是 1:1 对齐**（尾部字符串块里混着
显示名、`nui_stratagem_*` 键和 `_desc` 描述串），所以拿名字做的交叉表不可靠。武器配件那张表能做到
1:1（252 条名字对应 252 行），这张做不到——**这是两张表的重要差别**。

## 2. `+80 = max_uses` 的外部佐证

HD2Runtime 0.26.0 的发布说明写得很明确：

> **Native value.** `StratagemInfo` +80 (u32). The game's own unlimited value is `0xFFFFFFFF`；
> coverage: 85 stratagems: 80 unlimited by default, plus 5 finite (the four Exosuits and the Orbital Laser, at 3).

我们这边的读数与它**同型**：`0xFFFFFFFF` 占绝对多数（125/153），其余是 1/2/3/4/5 这类小整数。
数量不同是因为统计口径不同（我们这张表 153 行含鹰式/背包/涂装类条目，他们的 85 是非鹰式战备）。
**关键一致点**：无限 = `0xFFFFFFFF`，有限 = 小整数，同一个偏移。

## 3. 这轮把什么搞清楚了

1. **行身份**：`+0` 的 id 唯一，`+80` 是使用次数（外部佐证 + 本机分布一致）。
2. **分类**：`+60` 的 8 个值能把 153 行切成 8 类（94/17/12/11/11/6/1/1）。
3. **输入序列**：`+64` 的 16 字节里有方向键序列（152 个不同值，接近"每个战备一个"）。
4. **冷却**：`+84` 只有 6 个值且都是小整数（0/2/3/5/7/120）——读作秒数最合理，但 **⚠ 未实测**。

## 4. 还没解决的

* **枚举值没有名字**：类型库把成员类型名字给了我们，但枚举的**取值**（比如 `+60` 的 2 是什么分类）
  没有名字表。wiki 只给到 4 类，而 `+60` 有 8 个值。
* **行名与行号未对齐**：这张表的尾部字符串块混着显示名 / `nui_*` 键 / `_desc` 串，153 条字符串与
  153 行**不是一一对应**。要修，得先找到"行→名字"的真实链接（`+0` 的 `StratagemType` 值 → 名字表），
  或者在表里找每条记录自带的偏移。**这是这条线目前最大的缺口。**
* `+56` 的 4 个值含义未定（像投送方式，但没有对照）。
* `+84` 是冷却还是别的计时量，未实测。

## 5. 复现

```bash
python tools/table_export.py --table stratagem_settings --sk <你的>/recipient.sk --out out/st
# out/st.csv（153 行 × 71 字段）+ out/st.md（字段图例 + 前 15 行）
```

`tools/table_export.py` 的 `LAYOUTS` 里已带这张表的注解（字段名 + `max_uses`）。

## 6. 出处

* 偏移/成员：本机 `dl_library.dl_typelib`（`StratagemInfo` 67 成员，14 个具名枚举类型）。
* `+80 = max_uses` 与 `0xFFFFFFFF` 语义：**HD2Runtime 0.26.0 发布说明**（`refs/hd2runtime/rel.json`）。
* 行名：表内尾部平行名字数组（见 `tools/table_row_names.py`）。
* 类型名：公开的 filediver 名字表（`refs/dl-type-names.txt`）。
