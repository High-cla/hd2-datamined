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
| `table_dictionary.py` | **全表字典**：解封 55 张表 → 组/行数/步长/尾块 + 每个类型的字段偏移树（需自备 `recipient.sk`） | PyNaCl + `typelib.py` | ✓ 55/55 表解析（18 张几何完全闭合） |
| `entities_modeb.py` | 实体表：武器单元格编辑、可选弹种（模式 A/B）、双弹药池、hashmap 维护 | `murmur64.py` | ✓✓ 已实机（主宰/惩罚者/扫荡者） |
| `proj_copy_row.py` | 整行搬运 272 B 射弹行（换弹头），带 5 道门禁 | `murmur64.py` | ✓✓ 已实机（Eruptor 弹头 → 主宰） |
| `expl_set.py` | 写爆炸行字段（半径 / 破片数 `+80` / 破片射弹 `+84`），带 6 道门禁 | `murmur64.py` | ✓✓ 已实机（毒气爆炸加 30 破片） |
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
