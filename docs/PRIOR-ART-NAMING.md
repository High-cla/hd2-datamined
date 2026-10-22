# 别人怎么解决"内部名 → 显示名/页面"的（调研）

> 起因：我们的战备行给的是内部显示名（`BACKPACK. SUPPLY BACKPACK`）和本地化键
> （`nui_stratagem_backpack_ammo_name`），而 wiki 页面标题是 `B-1 Supply Pack`。
> 靠 `+24` 键 → slug → `nativeType` 只能覆盖 38 条（见 `WIKI-LOCAL-DB.md` §4.5）。
> 这份文档记录外部已有的做法，以及我们该借哪个。

## 1. 社区工具清单

| 项目 | 语言 | 与本问题的关系 | 判定 |
|---|---|---|---|
| [xypwn/filediver](https://github.com/xypwn/filediver) | Go | 事实标准的提取器。**仓库里直接带 42 个明文 `generated_*.dl_bin`**，另有专门的 strings 提取器 | ✓ 最有用 |
| [SkyeShade/HD2Runtime](https://github.com/SkyeShade/HD2Runtime) | C++/SDK | 96 条战备的语义目录（`nativeType` / `nativeTypeValue` / `attacks`），我们已在用 | ✓ 已在用 |
| [helldivers.wiki.gg 的 Module: 数据模块](https://helldivers.wiki.gg/wiki/Module:Decodedata-Attacks/data.json) | JS/JSON | 社区解码的 settings 视图，我们已建成本地库 | ✓ 已在用 |
| [YimMenuV2/Awesome-GTAV](https://github.com/YimMenuV2) 之类、[UEExtractor](https://solicenteam.github.io/UEExtractor/) | — | 与 Stingray 引擎无关，检索命中但用不上 | ✗ |

## 2. filediver 里两个能直接借的东西

### 2.1 明文 `generated_*.dl_bin`（42 个）

`datalibrary/` 下同时存着 Go 结构体定义**和明文表**，例如
`datalibrary/generated_explosion_settings.dl_bin`、`generated_projectile_settings.dl_bin`
（还有 `.gz`）。

* 价值：这是**另一个 build** 的表，且不需要任何密钥。可以拿来做跨 build 差分。
* 限制：**没有 `generated_stratagem_settings.dl_bin`**——所以没法用它反推 `+56`/`+60` 那批枚举。

### 2.2 strings 提取器（这才是"键 → 显示名"的正解）

`stingray/strings/strings.go` 给出了 `.strings` 资源的完整格式：

```go
type Strings struct {
    Magic    [4]byte
    Version  uint32
    Count    uint32
    Language stingray.ThinHash      // Count == 0 时不存在
    Strings  map[uint32]string      // ThinHash(键) -> 本地化文本
}
```

外加一张语言表（`us`=English (US)、`gb`=English (UK)、`sc`/`tc`=简繁中文…），
键就是那两个字母的 `ThinHash`——**和我们 `language_settings` 表里 `+8` 的 `us`/`gb`/`bp`
完全一致**（见 `docs/ROW-NAMING-25988413.md`）。

## 3. 结论：该借的是 strings 表，不是又一个名字字典

我们要的映射是

```
nui_stratagem_backpack_ammo_name   ->  游戏内显示名   ->  wiki 页面标题
```

现在断在第二段。而**游戏内显示名就存在 strings 资源里**：

1. 从 31 个 `bundles.NN.nxa`（约 20 GB）里按类型 `.strings` 找到该资源；
   `srkit/util/ids.py` 已认这个类型（`TYPE_STRINGS: ".strings"`），但还没有解析器。
2. 按上面的结构解析，用 `ThinHash(键)` 查表，得到英文文本。
3. 该文本就是 wiki 页面标题（wiki 用的正是游戏内显示名）。

这条路的覆盖面是**全部 128 条带键的行**，而不是 38 条——因为键我们全都有（`+24` 指针）。

⚠ 两个待确认：
* `ThinHash` 用的哈希函数（filediver 的 `stingray.Sum`）我们还没核对；本仓库的
  `murmur64a.py` 是 MurmurHash64A，需要确认 `Sum`/`Thin()` 是否同族、以及 thin 取高/低 32 位。
* `.strings` 资源在 bundles 里的定位方式（按类型扫 bundle 索引）尚未实现。

## 4. 本次调研的检索记录（含零结果）

| 查询 | 结果 |
|---|---|
| `Helldivers 2 localization strings dump nui_stratagem_ keys github` | 无直接命中；泛泛的提取器列表 |
| `filediver helldivers 2 datalibrary localization names stratagem` | 命中 filediver 仓库与其 datalibrary |
| `helldivers 2 stratagem internal name to display name mapping github` | 无此类现成映射 |
| `HD2Runtime SkyeShade stratagem catalog semantic id localization` | 命中 HD2Runtime（我们已在用） |
| GitHub API `search/repositories?q=helldivers+generated+settings` | **空**（无输出，未命中可用仓库） |
| GitHub API `repos/xypwn/filediver/contents/datalibrary` | ✓ 42 个明文表 + `dl_library.dl_typelib` |
| 仓库树里搜 `stratagem` 路径 | **零命中**——filediver 不含 stratagem 表 |

**没有现成的"内部名 ↔ wiki 名"映射表**。社区的做法是各自解 strings 表，然后自己 join。
