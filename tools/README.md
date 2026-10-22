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
| `dlbin_seal.py` | `.dl_bin` 密封盒：解/封、配对→keystream、LDLD 结构 | PyNaCl | ✓ 已实机 |
| `dlbin_keyhunt.py` | 在 `game.dll` 里定位打开 `.dl_bin` 的 X25519 密钥 | PyNaCl + cryptography | ⚠ 研究工具；仓库不含任何密钥材料 |
| `typelib.py` | 解析 DataLibrary 类型库（LTLD v4），查表结构 | `dlbin_seal.py` | ✓ |
| `entities_modeb.py` | 实体表：武器单元格编辑、可选弹种（模式 A/B）、双弹药池、hashmap 维护 | `murmur64.py` | ✓✓ 已实机（主宰/惩罚者/扫荡者） |
| `proj_copy_row.py` | 整行搬运 272 B 射弹行（换弹头），带 5 道门禁 | `murmur64.py` | ✓✓ 已实机（Eruptor 弹头 → 主宰） |
| `expl_set.py` | 写爆炸行字段（半径 / 破片数 `+80` / 破片射弹 `+84`），带 6 道门禁 | `murmur64.py` | ✓✓ 已实机（毒气爆炸加 30 破片） |
| `dmg_edit.py` / `dmg_custom_row.py` / `dmg_refs.py` | 伤害行编辑 / 自制伤害行 / 跨表引用查询 | `murmur64.py` | ✓ 离线门禁通过 |
| `name_rows.py` | 用跨 build 指纹给爆炸/射弹行恢复名字 | 标准库 | ✓ |
| `make_loadlib_fixtures.py` | 造 DLL 夹具，测进程内原生代码那条路（含 `--matrix`） | 标准库 | ✓ 实机（结论见 `MEMORY-ACCESS` §12） |

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

## 文档提到、但本仓库**故意不含**的工具

写清楚是为了让人别照着文档找不存在的文件：

| 文档里出现 | 为什么不在 |
|---|---|
| `memscan.py` | 旧路线（LuaJIT + `ffi`）的扫描器，**弃用**：25988413 的 VM 没有 `ffi`，跑不起来；3,000+ 行里全是旧 build 的偏移知识 |
| `eac_access_test.py` / `eac_early_handle.py` | 外部读内存 / 抢早期句柄的探针。结论已写进 `docs/MEMORY-ACCESS-25988413.md`（全部 err=5），工具本身是死路；发布它只会变成"怎么试着绕过反作弊"的范文 |
| `crash_watch.py` | 依赖上面那个探针，且配套的 `dumper.ps1` 不在仓库；全量 dump 那条路在 EAC 下已死（引擎自己的崩溃 dump 仍可用，但那部分没随仓库发布） |
| `verify_patch_series.py` | 依赖 `patch_series_prune.py` → `hd2_archive`（不在本仓库） |
| `build_snapshot.py` | 需要本机的普查表 / 探针 / 文档作为输入，不是通用输入 |
| `murmur64a.py` | 已被 `murmur64.py` 取代，且它自己的 `--selftest` 目前 20 项全失败（保留在私有工作区，未发布） |
| `package_p2p_ping.py` | 属于另一个项目（`hd2-p2p-ping`），与本仓库无关 |
