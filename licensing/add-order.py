#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
已购订单白名单维护脚本（licensing/orders.json）

用法：
  # 追加一笔订单（自动去重、更新 count 与 updatedAt）
  python3 licensing/add-order.py add 2026092012345678901
  python3 licensing/add-order.py add 2026092012345678901 --date 2026-09-20 --note "小红书首单"

  # 查看当前白名单
  python3 licensing/add-order.py list

  # 删除一笔订单（填订单号或列表中显示的值）
  python3 licensing/add-order.py remove 2026092012345678901

  # 本地模拟快捷指令校验（输入订单号，返回 已购买 / 未购买）
  python3 licensing/add-order.py check 2026092012345678901

  # 切换匹配口径：exact（默认，全号比对）/ suffix（仅比对末 N 位，降低隐私暴露）
  python3 licensing/add-order.py mode suffix --length 10

说明：
  - 存储形态由 orders.json 的 matchMode 决定：
      exact  → orders[].orderId 存完整订单号
      suffix → orders[].orderId 只存订单号末 suffixLength 位
  - 切换 mode 不会自动转换已有记录，切换后请用 check 复核，必要时重建列表。
  - 本脚本只改 JSON 数据，不做任何网络操作，可安全离线运行。
"""

import argparse
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "orders.json")


def load():
    if not os.path.exists(DATA):
        sys.exit(f"❌ 未找到数据文件：{DATA}")
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def save(d):
    d["count"] = len(d["orders"])
    d["updatedAt"] = date.today().isoformat()
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")


def normalize(raw, d):
    """按当前 matchMode 把用户输入的订单号转成存储值。"""
    raw = raw.strip()
    if d.get("matchMode") == "suffix":
        n = int(d.get("suffixLength") or 0)
        if n <= 0:
            sys.exit("❌ matchMode=suffix 但 suffixLength 未设置有效值")
        return raw[-n:]
    return raw


def cmd_add(args):
    d = load()
    value = normalize(args.order_id, d)
    if not value:
        sys.exit("❌ 订单号为空")

    for o in d["orders"]:
        if o["orderId"] == value:
            print(f"⚠️ 已存在，未重复添加：{value}")
            return

    d["orders"].insert(0, {
        "orderId": value,
        "activatedAt": args.date or date.today().isoformat(),
        "note": args.note or "",
    })
    save(d)
    print(f"✅ 已添加：{value}")
    print(f"   当前白名单共 {d['count']} 条（matchMode={d.get('matchMode')}）")
    print("   记得 commit + push 后才会对快捷指令生效（raw 可能有缓存延迟）")


def cmd_list(args):
    d = load()
    mode = d.get("matchMode")
    tail = f"（存末 {d.get('suffixLength')} 位）" if mode == "suffix" else "（完整订单号）"
    print(f"📋 白名单 {d['count']} 条 | matchMode={mode}{tail} | updatedAt={d['updatedAt']}")
    if not d["orders"]:
        print("   （空）")
        return
    for i, o in enumerate(d["orders"], 1):
        note = f"  # {o['note']}" if o.get("note") else ""
        print(f"  {i:>3}. {o['orderId']}  [{o.get('activatedAt', '')}]{note}")


def cmd_remove(args):
    d = load()
    value = normalize(args.order_id, d)
    before = len(d["orders"])
    d["orders"] = [o for o in d["orders"] if o["orderId"] != value]
    if len(d["orders"]) == before:
        print(f"⚠️ 未找到：{value}")
        return
    save(d)
    print(f"✅ 已删除：{value} | 剩余 {d['count']} 条")


def cmd_check(args):
    d = load()
    value = normalize(args.order_id, d)
    hit = any(o["orderId"] == value for o in d["orders"])
    print(f"输入：{args.order_id.strip()}")
    print(f"比对值：{value}（matchMode={d.get('matchMode')}）")
    print("结果：", "✅ 已购买" if hit else "❌ 未购买")


def cmd_mode(args):
    d = load()
    if d.get("matchMode") == args.name:
        print(f"ℹ️ matchMode 已是 {args.name}")
    d["matchMode"] = args.name
    if args.name == "suffix":
        if not args.length:
            sys.exit("❌ suffix 模式必须指定 --length N")
        d["suffixLength"] = args.length
    else:
        d["suffixLength"] = 0
    save(d)
    print(f"✅ matchMode → {args.name}" + (f"（末 {args.length} 位）" if args.name == "suffix" else ""))
    print("⚠️ 已有记录未自动转换，请用 list 复核，必要时重建白名单")


def main():
    p = argparse.ArgumentParser(description="快递取件码 · 已购订单白名单维护")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="追加订单")
    a.add_argument("order_id")
    a.add_argument("--date", help="购买日期 YYYY-MM-DD，默认今天")
    a.add_argument("--note", help="备注")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="列出白名单")
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("remove", help="删除订单")
    r.add_argument("order_id")
    r.set_defaults(func=cmd_remove)

    c = sub.add_parser("check", help="模拟快捷指令校验")
    c.add_argument("order_id")
    c.set_defaults(func=cmd_check)

    m = sub.add_parser("mode", help="切换匹配口径")
    m.add_argument("name", choices=["exact", "suffix"])
    m.add_argument("--length", type=int, help="suffix 模式下的尾号位数")
    m.set_defaults(func=cmd_mode)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
