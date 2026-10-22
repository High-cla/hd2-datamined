# 工具索引

本目录的全部工具都**只读/离线**：没有一个会去读游戏进程内存、注入、或改内存里的数值。改数据走的是
"解封装 → 改字节 → 解校正字 → 保哈希 → 重新封装"这条资源侧路线（见 `docs/DLBIN-SEALED-BOX.md`）。

依赖一列是**可选**的：核心表工具只需要标准库（外加同目录的 `murmur64.py` / `dlbin_seal.py`），
带第三方依赖的那几个都写明了。凡是打了"自检"的，都可以直接
`python tools/<名字> --selftest` 复跑，不需要游戏文件。

## 数据表 / 封装

| 工具 | 用途 | 依赖 | 验证 |
|---|---|---|---|
| `murmur64.py` | MurmurHash64A（引擎的内容哈希闸门）+ 反解"校正字"，改完字节仍过校验 | 标准库 | ✓ 已实机（全部表工具都走它） |
| `murmur64a.py` | 同一个算法的**命令行版**：`hash` / `solve --word N --target HEX` / `selftest`（库调用请用上面的 `murmur64.py`，两者在自检里互相对表） | 标准库 | ✓ `--selftest` **7/7**（含"解自己的哈希必须解出原来的字"与跨实现对表） |
| `dlbin_seal.py` | `.dl_bin` 密封盒：解/封、配对→keystream、LDLD 结构 | PyNaCl | ✓ 已实机 |
| `dlbin_keyhunt.py` | 在 `game.dll` 里定位打开 `.dl_bin` 的 X25519 密钥 | PyNaCl + cryptography | ⚠ 研究工具；仓库不含任何密钥材料 |
| `typelib.py` | 解析 DataLibrary 类型库（LTLD v4），查表结构 | `dlbin_seal.py` | ✓ |
| `table_export.py` | 把整张表导成**人类可读**的 CSV + Markdown（名字 + 每字段 hex/f32 + 统计 + 一阶嵌套）；`LAYOUTS` 存字段名与枚举注解，`POINTERS` 存 (表, 步长) → 行内名字指针 | PyNaCl + `typelib.py` | ✓✓ 六张表整表导出（weapon_customization 252×13、stratagem 153×68），名字全部走指针 |
| `table_row_names.py` | 抽出逐行名字。**指针优先**：weapon_customization 252 / stratagem 153 / planet_override 44 / status_effect 73 / language 15 / stratagem_upgrade 1；其余表退化为位置法且必须 `串数 == 行数` | PyNaCl + `typelib.py` | ✓ 实机数据抽全（`refs/table-row-names.json`，每表标明机制） |
| `row_pointer_sweep.py` | 扫全部 55 张表找**行内名字指针**，判据是"每行解析出不同的串"，并与位置法交叉验证 | PyNaCl + `typelib.py` | ✓ 6 张表命中；weapon_customization 交叉验证 240/240 一致 |
| `probe_row_name_offsets.py` | 单表深挖指针：命中率 / 不同串数 / 串的类别（显示名 / 键 / 描述键），用来排除小整数巧合 | PyNaCl | ✓ 实机数据 |
| `stratagem_field_scan.py` | 拿系族当标签给每个 4 字节槽打分（族内纯度 + 能否分离 wiki 四色），用来判定分类字段 | PyNaCl | ✓ `+392` 5/6（唯一交集是 cell 0）；`+56`/`+60` 3/6 及以下，否证了"`+56` 的 4 个值 = wiki 四类" |
| `stratagem_join.py` | 战备行与 HD2Runtime 目录逐名配对（同系族内模糊匹配、一对一），用冷却是否相等反向校验配对；目录快照早于补丁时按 `PATCHED` 表登记 | PyNaCl + HD2Runtime SDK zip | ✓ 21 配对：20 条精确 + 1 条已定案补丁差异（Airburst 100→90），未解释 0 |
| `settings_field_align.py` | 用连接键把 filediver 明文 dump 的字段名对齐到本表偏移（带"常量字段/常量槽"双排除） | PyNaCl + `typelib.py` + filediver JSON | ✓ 弹丸表 18 字段（`name_upper` 连接，132 对）|
| `table_xref_scan.py` | 通用跨表引用扫描：找出源表哪个槽命中目标表某列的值（用 `distinct` 判据排除小整数巧合） | PyNaCl + `typelib.py` | ✓ 用它否证"战备行引用弹丸行" |
| `stratagem_attack_chain.py` | 走通一条链并逐环打印证据：战备行 `+0` → StratagemType 名 → 战备道具资源的 `projectile_type` → 弹丸行 → `+144/+156` → 爆炸行 `+28` | PyNaCl + `typelib.py` + wiki 模块 + filediver dump | ✓ 26 条命中，含 Airburst 的 cone=27 |
| `probe_stratagem_projectile_link.py` | 排查战备行里弹丸类型的编码形式（`+0`/文件下标/`name_upper`/枚举下标），用于否证"战备行有指向弹丸的外键" | PyNaCl + `typelib.py` | ✗ 四种编码全不命中 |
| `fetch_wiki_modules.py` | 按需拉取 wiki 的 `Module:Decodedata-*` 数据模块（当字段名字典用；wiki 会挡默认 UA，故不随仓库分发） | 标准库 | ✓ 12/12 可拉 |
| `probe_stratagem_fields.py` | 把两份 wiki 战备视图的全部数值字段逐一对到本表槽（含最佳槽报告，能区分"没有"和"有但值不同"） | PyNaCl | ✓ 定位 `+104`/`+80`/`+84` |
| `find_bombs_salvos_pair.py` | 战备 `num_bombs`×`num_salvos` 的**联合**反查：扫所有有序槽对、扫乘积、再按 u8/u16/u32/f32 四种宽度找标志值 | PyNaCl | ✗ 全落空（证明这两项不在战备行里）|
| `fetch_wiki_pages.py` | 用 MediaWiki API 批量缓存 wiki 页面源码，50 页一请求 + sleep；支持 `--category` 与按标题补抓（`--titles` / `--titles-file`） | 标准库 | ✓ 763 页（战备/武器/护甲/披风/外观/护甲被动/星球） |
| `wiki_build_db.py` | 把页面源码的模板参数 + 模块 JSON 落成 SQLite（`page`/`param`/`entity`/`stratagem`/`weapon`）；`page.kind` 由信息框模板判定；标题走 `_titles.json` 以免斜杠丢失 | 标准库 | ✓ 763 页 / 9,312 参数 / 235 武器行 |
| `wiki_match_tables.py` | 把表里解出的名字和 wiki 页面标题对上（精确 / 后缀 / 包含 / 模糊四条规则），输出覆盖率与未匹配清单 | 标准库 | ✓ 护甲 217/237、被动 32/33、星球 277/395；未匹配的都查过确实无页面 |
| `wiki_query.py` | 查本地库：任意页（战备/武器）全貌 + 攻击链解析（含嵌套 weapon）+ 与解密表并排对照（`--sk` 时自动用别名表兜底）；支持 `--page` / `--field` / `--entity` / `--sql` | PyNaCl（仅 `--sk` 时） | ✓ 见 `docs/WIKI-LOCAL-DB.md` |
| `build_stratagem_alias.py` | 用行内 `+24` 本地化键 → slug → HD2Runtime `uiIcon.nativeType` 建战备别名表（不依赖显示名），产出 `refs/stratagem-alias.json` | PyNaCl + HD2Runtime SDK zip | ✓ 38 条 / 0 歧义；冷却 34/35 一致 |
| `stratagem_display_names.py` | 从 `.strings` 资源解出每行的**游戏内文本**：五个槽位（`+40` 大写名 / `+44` 显示名 / `+48` 描述 / `+52` 长描述 / `+56` 状态标签），并附上匹配到的 wiki 页面标题；死引用会按"文本匹配 → 大写回退"回填并标明来源 | PyNaCl + 由 srkit 解出的 strings 目录 | ✓ 显示名 145/153（135 直接 + 1 文本匹配 + 9 大写回退），wiki 页 115/145 |
| `table_locid_scan.py` | 扫一张表每个 4 字节槽，按 `(stride, offset)` **跨组聚合**，报告"本地化 ID 命中数 / 去重数 / 样本文本"。两种 `LDLD` 组头都认（数组型 `0x10\|count` 与单记录型），stride 取自 typelib。**发现**名字槽用它 | PyNaCl（无）+ `typelib.py` | ✓ 扫出 7 张表的名字槽（判据见 `docs/LOCID-NAMES-25988413.md` §1）|
| `table_locid_names.py` | 按槽位表把本地化 ID 倒成文本，输出 JSON（`name` / `name_source` / 原始 ID），带"文本匹配 → 大写回退" | PyNaCl（无）+ `typelib.py` | ✓ 六张表：弹丸 225/355、配件 234/252、护甲 389/422、被动 33/33、载具 11/12、星球 399/438 |
| `entity_locid_scan.py` | 解实体库（275 块 → `[哈希图][行数组][尾数组]`），定位本地化 ID 槽。实体名只有一处：`EncyclopediaEntryComponentData`（块 56）+0 单数 / +8 大写 / +4 复数 / +36 物品代码 | PyNaCl（无）+ `typelib.py` | ✓ 643/1,939 实体有名字，205/211 条带代码条目精确命中 wiki 标题；`--dump-slot 56:0` 可查单槽 |
| `entity_components.py` | 实体 → 组件清单（用每个组件块自己的哈希图反查，不用块 0 的 u16）；附带"谁引用了某值"的列扫描（找爆炸类型引用方用） | PyNaCl（无）+ `typelib.py` | ✓ 1,932 实体 / 272 种组件；用它查出 explosion 68 被 `Bombardment +64` 引用 |
| `explosion_names_from_chain.py` | 爆炸行没有名字字段，改从引用链命名：投掷物 `+144/+156` → 爆炸 `+0`，输出每个爆炸行的消费方（共用关系一目了然） | PyNaCl（无）+ `typelib.py` | ✓ 210 条边 / 0 悬空；103 个爆炸行有名字（97 唯一 + 6 共用）|
| `strings_inventory.py` | 清点 `.strings` 语料：语言分布（`ThinHash` 反查 15 种语言）、每个 bundle 的 distinct 英文 blob 数、ID 并集。**只读文件头 16 字节** | 标准库 | ✓ 证明英文语料是全局唯一那 18 个 blob |
| `table_dictionary.py` | **全表字典**：解封 55 张表 → 组/行数/步长/尾块 + 每个类型的字段偏移树（需自备 `recipient.sk`） | PyNaCl + `typelib.py` | ✓ 55/55 表解析（18 张几何完全闭合） |
| `build_diff.py` | 更新后逐表回答"改了什么"：文件层（size/sha256）→ 封装层（解封后比**明文**哈希）→ 结构层（组数/行数/步长）。只读 | PyNaCl | ✓ 25988413→26088801：55 张表 0 变化，exe/dll 哈希变 |
| `build_geometry_diff.py` | 用旧 build 的字典几何（`refs/table-geometry.json`）对照当前 55 张表：多大/多组/多少行，哪张被动过一目了然 | PyNaCl | ✓ 同一次更新：identical 21 / structure-same 33 / changed 0 |
| `build_cache.py` | 把当前 build 的 55 张表 + 类型库解封成明文缓存，**按 buildid 另存**（`refs/dlbin/plaintext-<buildid>/`）。更新后第一件事就是跑它 | PyNaCl | ✓ 26088801：56/56 解封 |
| `entities_modeb.py` | 实体表：武器单元格编辑、可选弹种（模式 A/B）、双弹药池、hashmap 维护 | `murmur64.py` | ✓✓ 已实机（主宰/惩罚者/扫荡者） |
| `proj_copy_row.py` | 整行搬运 272 B 射弹行（换弹头），带 5 道门禁 | `murmur64.py` | ✓✓ 已实机（Eruptor 弹头 → 主宰） |
| `expl_set.py` | 写爆炸行字段（半径 / 破片数 `+80` / 破片射弹 `+84`），带 6 道门禁 | `murmur64.py` | ✓✓ 已实机（毒气爆炸加 30 破片） |
| `stratagem_tune.py` | 改战备表的 `+80` uses / `+84` call-in / `+104` cooldown，用 `(NOT USED)` 战备行当校正字宿主保住内容哈希；7 道门禁 | 标准库（`murmur64.py` + `typelib.py`） | ✓ 离线：380mm 冷却 240→60，7/7 门禁通过，哈希复原，封包往返一致 |
| `patch_compose.py` | 数据路线 mod 的离线合成器：`scan` 查各包槽位与空洞、`merge` 求并集（同 id 不同内容=冲突，默认拒绝）+ 逐条回读验证、`install` 只写下一个连续槽位 | 标准库 + `srkit.container` | ✓ 实测把 bones/material/texture/lua 共 7 条合进一个补丁，toc 与 gpu 附流逐条一致 |
| `dmg_edit.py` / `dmg_custom_row.py` / `dmg_refs.py` | 伤害行编辑 / 自制伤害行 / 跨表引用查询 | `murmur64.py` | ✓ 离线门禁通过 |
| `name_rows.py` | 用跨 build 指纹给爆炸/射弹行恢复名字 | 标准库 | ✓ |
| `make_loadlib_fixtures.py` | 造 DLL 夹具，测进程内原生代码那条路：`--matrix`（换目录 / 换名）、`--in-place-name`（同目录换名） | 标准库 | ✓✓ 已实机（两轮共 5 个夹具 / 7 个用例；结论见 `MEMORY-ACCESS` §12g） |

## 补丁 / 资源

| 工具 | 用途 | 依赖 | 验证 |
|---|---|---|---|
| `resource_patch.py` | **任意** Stingray 资源类型的 `.patch_N` 构建/查看/解包/重打 | `srkit`（构建时） | ✓ |
| `swap_texture.py` | 把一张 PNG 换进 `.patch_N` 里的某个贴图并重打 | Pillow | ✓ 已实机 |
| `export_textures.py` | 把 `.patch_N` 里每个贴图导出成可编辑 DDS | Pillow | ✓ |
| `extract_seal_material.py` | 从**第三方 mod** 的 `boot.lua` 里取密封材料（用于互操作） | lupa | ✓；`--share-safe` 输出占位符版本 |

## Lua 侧

| 工具 | 用途 | 依赖 | 验证 |
|---|---|---|---|
| `lua51_check.py` | 用**真** Lua 5.1 解析/消毒载荷，避免方言错误烧一次启动 | lupa | ✓ 自检 |
| `luac51_disasm.py` | 反汇编标准 Lua 5.1 字节码块 | 标准库 | ✓ 自检（6 项） |
| `check_unit_snapshot.py` | 静态查"遍历 `World.units()` 快照还调 Unit getter"的崩溃写法 | 标准库 | ✓ 自检 |
| `hud_layout_check.py` | 离线算 HUD 绘制坐标（假引擎跑真 lua） | lupa | ✓ |
| `lensmask_to_reticle.py` | "亮镜片 + 暗准心"贴图 → 自发光准心遮罩 | Pillow | ✓ |
| `grab_logs.py` | 在下次启动覆盖前把游戏日志归档 | 标准库 | ✓ |

## 反作弊 / 能力边界（**全部是否证记录**，不是方法）

这三个是"试着做 → 失败 → 把失败量出来"的工具，**没有一个成功过**，最硬的证据来自它们自己的自检：
`eac_access_test.py --selftest` 会**故意造一只被剥权的句柄**（`0x0400`，正是 EAC 还给你那种形状），
要求"读一个字节必须被拒绝"，5/5 PASS。发布它们是因为"我们试过并且失败了"比沉默有用——
`docs/MEMORY-ACCESS-25988413.md` §2–§8 就是这些工具的输出。

| 工具 | 它回答的问题 / 实测结果 | 依赖 | 验证 |
|---|---|---|---|
| `eac_access_test.py` | 外部进程还能读游戏吗？→ **不能**：`OpenProcess` 三档全给句柄、元数据能读，但 `ReadProcessMemory` **err=5**、`MiniDumpWriteDump` **0x80070005**。文件头留着第一版**假阳性**的教训（只看 `OpenProcess` 会骗自己） | 标准库 | ✓ `--selftest` **5/5**（含"剥权句柄必须被拒"的变异测试） |
| `eac_early_handle.py` | 有没有"保护生效前"的窗口？→ **没有**：进程出现后 **10.6 ms** 建的句柄**已经被剥权**（err=5），access mask 在创建时就定了 | 标准库 | ✓ `--help`；完整流程需要一次游戏启动 |
| `crash_watch.py` | 在 CRS 删掉之前抢救游戏**自己**的崩溃捕获。外部全量 dump 那条路已死：`dumper.ps1` 未随仓库发布，而 `can_read_memory()` 会在调用它之前就拒绝 | `eac_access_test.py`（缺席时降级为"跳过预检"） | ✓ `--selftest`（造假 CRS 捕获 → 救援 → hash 校验 PASS） |
| `watched_modules.py` | 从**外部**盯一个进程的**映射文件列表**（`VirtualQueryEx` + `GetMappedFileNameW`，只读元数据、不读内容），用来回答"某个 DLL 到底有没有被映射进来" | 标准库 | ✓ 实机（2026-10-22：正常态插件在第一个样本就出现 / 换供体后 23 个样本里从未出现） |

## 文档提到、但本仓库**故意不含**的工具

写清楚是为了让人别照着文档找不存在的文件：

| 文档里出现 | 为什么不在 |
|---|---|
| `memscan.py` | 旧路线（LuaJIT + `ffi`）的扫描器，**弃用**：25988413 的 VM 没有 `ffi`，跑不起来；3,000+ 行里全是旧 build 的偏移知识 |
| `verify_patch_series.py` | 依赖 `patch_series_prune.py` → `hd2_archive`（不在本仓库） |
| `build_snapshot.py` | 需要本机的普查表 / 探针 / 文档作为输入，不是通用输入 |
| `package_p2p_ping.py` | 属于另一个项目（`hd2-p2p-ping`），与本仓库无关 |
| `passive_example.py` | **不是我们的工具**：`docs/DLBIN-SEALED-BOX.md` 引用的是某个第三方 modkit 里的 `kit/tools/passive_example.py`，只作为"别人怎么解这个字"的对照 |

> 注：少数工具相对私有工作区只改了两处——默认输出路径改成**相对路径**、个人 SDK 路径改成
> `HD2SDK` 环境变量或 `~/HD2SDK-CommunityEdition`。逻辑未改。
