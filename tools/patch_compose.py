#!/usr/bin/env python3
"""patch_compose.py -- 把多个"改数据文件"路线（`.patch_N`）的 mod 合成一个补丁，让它们能共存。

为什么需要它（社区说"数据 mod 不能共存"，原因其实有两条，都可解）
    1. **文件名撞车**：每个 mod 都按 `9ba626afa44a3aa3.patch_0` 发布，后装的直接盖掉先装的。
    2. **序号必须连续**（实测，见 docs/LOADER-SPEC-25988413.md）：引擎按连续序号合并
       `.patch_N`，中间缺一个号，**后面的一律不生效**。多数安装器在删除/重排时都会制造空洞，
       表现出来就是"两个 mod 一起装就有一个不见了"。

    所以"加载器"在这条路线上根本不需要执行权（ffi 死了也无所谓）—— 它是**离线合成器**：
    读每个 mod 的补丁条目 → 按资源 id 求并集 → 冲突检测 → 合成**一个**补丁写到一个连续槽位。
    引擎侧什么都不用改，它本来就会读 `patch_N`。

判据（全部离线，可复跑）
    * 同 id 同内容 → 去重（记一条 note）
    * 同 id 不同内容 → **冲突**，默认拒绝合成（要人工选边：`--prefer` 指定优先的 mod）
    * 合成结果逐条回读，与来源逐字节比对
    * 安装时检查目标包的补丁序号是否连续，只在**下一个连续槽位**写入

用法
    python tools/patch_compose.py scan --data "<game>/data"
    python tools/patch_compose.py merge --mods a.patch b.patch --out out/merged
    python tools/patch_compose.py install --patch out/merged/9ba626afa44a3aa3.patch_5 --data "<game>/data"
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resource_patch import BASE, find_sdk, open_patch, type_label      # noqa: E402
from srkit.container.package import Package, TocEntry                  # noqa: E402


def load_entries(path: str) -> dict[int, dict]:
    """file_id -> {type, toc, gpu, stream}。补丁里同一资源只有一条。"""
    out = {}
    for entry in open_patch(path):
        out[entry.file_id] = {
            "type": entry.type_id,
            "toc": bytes(entry.toc_data),
            "gpu": bytes(entry.gpu_data or b""),
            "stream": bytes(entry.stream_data or b""),
        }
    return out


def cmd_scan(args) -> int:
    data = args.data
    packages = {}
    for path in glob.glob(os.path.join(data, "*.patch_*")):
        if path.endswith(".gpu_resources") or path.endswith(".stream"):
            continue
        m = re.match(r"(.+)\.patch_(\d+)$", os.path.basename(path))
        if not m:
            continue
        packages.setdefault(m.group(1), []).append((int(m.group(2)), path))
    if not packages:
        print(f"{data}: 没有任何 .patch_N")
        return 0
    bad = False
    for name, slots in sorted(packages.items()):
        slots.sort()
        idx = [s[0] for s in slots]
        gaps = [i for i in range(0, max(idx) + 1) if i not in idx]
        print(f"{name}: 槽位 {idx}  空洞 {gaps if gaps else '无'}")
        for i, path in slots:
            entries = load_entries(path)
            types = {}
            for e in entries.values():
                types[type_label(e["type"])] = types.get(type_label(e["type"]), 0) + 1
            size = os.path.getsize(path)
            print(f"  patch_{i}: {len(entries):4d} 条 / {size:>10,} B  "
                  + "  ".join(f"{k}×{v}" for k, v in sorted(types.items())[:5]))
            if gaps:
                bad = True
    if bad:
        print("\n⚠ 存在空洞：按实测规则，空洞之后的补丁不会生效")
    return 0


def cmd_merge(args) -> int:
    per_mod, conflicts, notes = {}, [], []
    for path in args.mods:
        if not os.path.isfile(path):
            print(f"✗ 缺少 {path}")
            return 2
        entries = load_entries(path)
        per_mod[path] = entries
        print(f"{os.path.basename(path)}: {len(entries)} 条")
    prefer = set(args.prefer or [])
    merged: dict[int, dict] = {}
    origin: dict[int, str] = {}
    for path, entries in per_mod.items():
        for fid, e in entries.items():
            if fid not in merged:
                merged[fid] = e
                origin[fid] = path
                continue
            old = merged[fid]
            if old["toc"] == e["toc"] and old["gpu"] == e["gpu"] and old["stream"] == e["stream"]:
                notes.append((fid, origin[fid], path, "同内容去重"))
                continue
            keep_new = path in prefer and origin[fid] not in prefer
            conflicts.append({"id": f"0x{fid:016X}", "a": origin[fid], "b": path,
                              "type": type_label(e["type"]),
                              "size_a": len(old["toc"]), "size_b": len(e["toc"]),
                              "picked": path if keep_new else origin[fid]})
            if keep_new:
                merged[fid] = e
                origin[fid] = path
    print(f"\n并集 {len(merged)} 条；同内容去重 {len(notes)} 条；冲突 {len(conflicts)} 条")
    for n in notes[:8]:
        print(f"  = 0x{n[0]:016X}  {os.path.basename(n[1])} + {os.path.basename(n[2])}  {n[3]}")
    for c in conflicts:
        print(f"  ！冲突 {c['id']} type={c['type']}: {os.path.basename(c['a'])}({c['size_a']} B)"
              f" vs {os.path.basename(c['b'])}({c['size_b']} B) -> 选中 {os.path.basename(c['picked'])}")
    if conflicts and not args.prefer:
        print("\n✗ 有冲突且没给 --prefer，拒绝合成（同一资源两个 mod 各写一份，语义上必须人工选边）")
        return 1

    package = Package(name=BASE)
    for fid in sorted(merged):
        e = merged[fid]
        entry = TocEntry(file_id=fid, type_id=e["type"], toc_data=bytearray(e["toc"]))
        if e["gpu"]:
            entry.gpu_data = bytearray(e["gpu"])
        if e["stream"]:
            entry.stream_data = bytearray(e["stream"])
        package.add_entry(entry)
    toc, gpu, stream = package.to_bytes()
    index = args.index
    outdir = args.out
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{BASE}.patch_{index}")
    with open(out, "wb") as handle:
        handle.write(toc)
    with open(out + ".gpu_resources", "wb") as handle:
        handle.write(gpu)
    with open(out + ".stream", "wb") as handle:
        handle.write(stream)
    print(f"\n合成 {out}  toc={len(toc):,} B  gpu={len(gpu):,} B  stream={len(stream):,} B")

    # ---- 回读验证：并集完整、逐条逐字节 ----
    back = load_entries(out)
    ok = True
    if set(back) != set(merged):
        missing = set(merged) - set(back)
        extra = set(back) - set(merged)
        print(f"  FAIL 回读条目集合不一致 缺 {len(missing)} 多 {len(extra)}")
        ok = False
    else:
        print(f"  PASS 回读条目集合一致（{len(back)} 条）")
    bad = [fid for fid, e in merged.items()
           if back.get(fid, {}).get("toc") != e["toc"]]
    print(f"  {'PASS' if not bad else 'FAIL'} 逐条 toc 字节一致"
          + ("" if not bad else f"，{len(bad)} 条不同"))
    ok = ok and not bad
    gpu_bad = [fid for fid, e in merged.items() if e["gpu"] and back.get(fid, {}).get("gpu") != e["gpu"]]
    if any(e["gpu"] for e in merged.values()):
        print(f"  {'PASS' if not gpu_bad else 'FAIL'} gpu 附流一致"
              + ("" if not gpu_bad else f"，{len(gpu_bad)} 条不同"))
        ok = ok and not gpu_bad
    return 0 if ok else 1


def cmd_install(args) -> int:
    data = os.path.dirname(os.path.abspath(args.patch))
    name = os.path.basename(args.patch).split(".patch_")[0]
    if args.data:
        data = args.data
    existing = []
    for path in glob.glob(os.path.join(data, f"{name}.patch_*")):
        m = re.search(r"\.patch_(\d+)$", path)
        if m and not path.endswith(".gpu_resources") and not path.endswith(".stream"):
            existing.append(int(m.group(1)))
    existing.sort()
    gaps = [i for i in range(0, (max(existing) + 1) if existing else 0) if i not in existing]
    if gaps:
        print(f"✗ 目标包的补丁序号有空洞 {gaps}；按实测规则空洞之后的补丁不生效。"
              f"先补齐再安装（这正是不该手删补丁的原因）")
        return 1
    index = (max(existing) + 1) if existing else 0
    dest = os.path.join(data, f"{name}.patch_{index}")
    shutil.copyfile(args.patch, dest)
    for suffix in (".gpu_resources", ".stream"):
        src = args.patch + suffix
        if os.path.isfile(src):
            shutil.copyfile(src, dest + suffix)
    size = os.path.getsize(dest)
    print(f"安装到 {dest}  ({size:,} B)，槽位 {index}（原有 {existing}）")
    print(f"回滚：del \"{dest}\" 及同名前缀的 .gpu_resources / .stream")
    return 0


def cmd_deploy(args) -> int:
    """BSL 风格的 mods 目录 -> 连续的单一补丁链（启动前跑一次，等价于"加载器"）。"""
    import json
    mods = []
    for manifest in sorted(glob.glob(os.path.join(args.mods_dir, "*", "mod.json"))):
        try:
            meta = json.load(open(manifest, encoding="utf-8"))
        except Exception as exc:                                   # noqa: BLE001
            print(f"✗ {manifest}: 读不了（{exc}）")
            return 2
        root = os.path.dirname(manifest)
        patch = meta.get("patch") or ""
        path = patch if os.path.isabs(patch) else os.path.join(root, patch)
        if not patch or not os.path.isfile(path):
            print(f"✗ {manifest}: patch 文件不存在（{patch!r}）")
            return 2
        mods.append({"name": meta.get("name") or os.path.basename(root),
                     "package": meta.get("package") or BASE,
                     "priority": int(meta.get("priority", 100)),
                     "path": path})
    if not mods:
        print(f"✗ {args.mods_dir} 下没有找到任何 <dir>/mod.json")
        return 2
    by_pkg: dict[str, list[dict]] = {}
    for m in mods:
        by_pkg.setdefault(m["package"], []).append(m)
    plan = {}
    for pkg, items in sorted(by_pkg.items()):
        items.sort(key=lambda m: (-m["priority"], m["name"]))
        print(f"\n包 {pkg}: {len(items)} 个 mod（按优先级高→低）")
        merged, origin, overrides = {}, {}, []
        for m in items:
            entries = load_entries(m["path"])
            print(f"  {m['name']:<28} priority={m['priority']:<5} {len(entries):4d} 条  <- {os.path.basename(m['path'])}")
            for fid, e in entries.items():
                if fid in merged:
                    same = (merged[fid]["toc"] == e["toc"] and merged[fid]["gpu"] == e["gpu"])
                    overrides.append((fid, origin[fid], m["name"], "同内容" if same else "覆盖"))
                    if not same and m["priority"] > next(x["priority"] for x in items if x["name"] == origin[fid]):
                        merged[fid] = e
                        origin[fid] = m["name"]
                    continue
                merged[fid] = e
                origin[fid] = m["name"]
        for fid, a, b, kind in overrides:
            print(f"    {'=' if kind == '同内容' else '！'} 0x{fid:016X}  {a} -> {b}（{kind}）")
        print(f"  并集 {len(merged)} 条")
        plan[pkg] = merged
    if args.dry_run:
        print("\n--dry-run：只打印计划，不写文件")
        return 0

    for pkg, merged in plan.items():
        package = Package(name=pkg)
        for fid in sorted(merged):
            e = merged[fid]
            entry = TocEntry(file_id=fid, type_id=e["type"], toc_data=bytearray(e["toc"]))
            if e["gpu"]:
                entry.gpu_data = bytearray(e["gpu"])
            if e["stream"]:
                entry.stream_data = bytearray(e["stream"])
            package.add_entry(entry)
        toc, gpu, stream = package.to_bytes()
        # 备份并清掉该包的其它槽位：链上只留 patch_0，天然满足"必须连续"
        others = [p for p in glob.glob(os.path.join(args.data, f"{pkg}.patch_*"))
                  if not p.endswith(".gpu_resources") and not p.endswith(".stream")
                  and not p.endswith(".patch_0")]
        if others:
            if not args.prune:
                print(f"⚠ {pkg} 还有其它槽位 {[os.path.basename(o) for o in others]}；"
                      f"加 --prune 会先备份再删除（链上只留 patch_0）")
            else:
                bk = os.path.join(args.data, "..", f"patch-backup-{os.urandom(3).hex()}")
                os.makedirs(bk, exist_ok=True)
                for o in others:
                    for suf in ("", ".gpu_resources", ".stream"):
                        if os.path.isfile(o + suf):
                            shutil.copyfile(o + suf, os.path.join(bk, os.path.basename(o) + suf))
                            os.remove(o + suf)
                print(f"  已备份其它槽位到 {os.path.abspath(bk)} 后删除")
        dest = os.path.join(args.data, f"{pkg}.patch_0")
        with open(dest, "wb") as handle:
            handle.write(toc)
        with open(dest + ".gpu_resources", "wb") as handle:
            handle.write(gpu)
        with open(dest + ".stream", "wb") as handle:
            handle.write(stream)
        back = load_entries(dest)
        ok = set(back) == set(merged) and all(back[f]["toc"] == merged[f]["toc"] for f in merged)
        print(f"{'PASS' if ok else 'FAIL'} 写入 {os.path.basename(dest)}  "
              f"toc={len(toc):,} B gpu={len(gpu):,} B，回读 {len(back)} 条")
        if not ok:
            return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="数据文件路线 mod 的离线合成器 / 槽位分配器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan", help="列出某个 data 目录里所有包与补丁槽位（查空洞）")
    p.add_argument("--data", required=True)
    p.set_defaults(func=cmd_scan)
    p = sub.add_parser("merge", help="把多个补丁合成一个（冲突检测 + 回读验证）")
    p.add_argument("--mods", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--prefer", nargs="*", default=[], help="冲突时优先的 mod 文件名")
    p.set_defaults(func=cmd_merge)
    p = sub.add_parser("deploy", help="按 mods 目录清单合成并写成一个连续补丁链")
    p.add_argument("--mods-dir", required=True, help="每个 mod 一个子目录，内含 mod.json")
    p.add_argument("--data", required=True, help="游戏 data 目录")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--prune", action="store_true", help="备份后删除该包其它槽位（链上只留 patch_0）")
    p.set_defaults(func=cmd_deploy)
    p = sub.add_parser("install", help="把合成好的补丁放到下一个连续槽位")
    p.add_argument("--patch", required=True)
    p.add_argument("--data", default="")
    p.set_defaults(func=cmd_install)
    a = ap.parse_args()
    find_sdk()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
