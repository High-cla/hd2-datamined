# 外部数据快照

## stratagemdata.json

* 来源：<https://helldivers.wiki.gg/wiki/Module:Decodedata-Attacks/stratagemdata.json>
  （社区解码的**战备道具资源**，含 `ref` / `projectile_type` / `attacks` / `stratcode`）
* 抓取：2026-10-22，55,541 B，原样保存，未改动。
* 用途：只取**语义字段**（`ref` 对应 `StratagemType` 名，`projectile_type` 对应弹丸类型名，
  `attacks` 是解析出的攻击树）。**不取数值**——这份数据来自另一个 build
  （它写 Orbital Precision Strike 冷却 90，本 build 与 wiki 页面都是 80）。
* 与本地数据的对照见 `docs/STRATAGEM-REFERENCE-CHAIN-25988413.md` §4.1。
