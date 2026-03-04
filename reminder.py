#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纪念日提醒脚本
- 读取仓库内 events.json
- 判断是否临近纪念日（提前 7/3/1 天 + 当天）
- 通过 Apprise 发送推送通知
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import apprise
except ImportError:
    print("❌ 请先安装依赖：pip install apprise")
    sys.exit(1)


# ─── 配置 ──────────────────────────────────────────────────────────────────
EVENTS_FILE = Path(__file__).parent / "events.json"
# APPRISE_URLS 从环境变量读取，多个 URL 用换行或逗号分隔
APPRISE_URLS_RAW = os.environ.get("APPRISE_URLS", "")


# ─── 工具函数 ───────────────────────────────────────────────────────────────
def load_events() -> dict:
    """加载 events.json"""
    if not EVENTS_FILE.exists():
        print(f"❌ 找不到 {EVENTS_FILE}")
        sys.exit(1)
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 艾宾浩斯复习间隔（天）
EBBINGHAUS_DAYS = [1, 2, 4, 7, 15, 30, 60, 90, 180]
# 法定节假日（月-日）
CN_HOLIDAYS = ["01-01", "05-01", "05-02", "05-03", "05-04", "05-05",
               "10-01", "10-02", "10-03", "10-04", "10-05", "10-06", "10-07"]


def _is_workday(d: date) -> bool:
    return 1 <= d.weekday() <= 5


def _is_weekend(d: date) -> bool:
    return d.weekday() in (5, 6)


def _is_cn_holiday(d: date) -> bool:
    k = d.strftime("%m-%d")
    return k in CN_HOLIDAYS


def next_occurrence(date_str: str, repeat: str, today: date, item: dict = None):
    """
    计算下一次纪念日的日期。
    返回 (next_date, days_left)
    """
    orig = date.fromisoformat(date_str)
    item = item or {}

    if repeat == "once":
        days_left = (orig - today).days
        return orig, days_left

    if repeat == "none":
        return None, None

    if repeat == "daily":
        return today, 0

    if repeat == "yearly":
        next_d = orig.replace(year=today.year)
        if next_d < today:
            next_d = orig.replace(year=today.year + 1)
        days_left = (next_d - today).days
        return next_d, days_left

    if repeat == "monthly":
        try:
            next_d = today.replace(day=orig.day)
        except ValueError:
            next_d = (today.replace(day=1) + timedelta(days=32)).replace(day=orig.day)
        if next_d < today:
            try:
                next_month = (next_d.replace(day=1) + timedelta(days=32))
                next_d = next_month.replace(day=orig.day)
            except ValueError:
                pass
        days_left = (next_d - today).days
        return next_d, days_left

    if repeat == "weekly":
        dow = orig.weekday()
        ndow = today.weekday()
        diff = (dow - ndow + 7) % 7
        if diff == 0:
            diff = 7
        next_d = today + timedelta(days=diff)
        return next_d, (next_d - today).days

    if repeat == "workday_weekly":
        d = today
        while not _is_workday(d):
            d += timedelta(days=1)
        return d, (d - today).days

    if repeat == "holiday_weekend":
        d = today
        while not _is_weekend(d):
            d += timedelta(days=1)
        return d, (d - today).days

    if repeat in ("workday_legal", "holiday_legal"):
        d = today
        for _ in range(366):
            if _is_cn_holiday(d):
                return d, (d - today).days
            d += timedelta(days=1)
        return None, None

    if repeat == "ebbinghaus":
        passed = (today - orig).days
        if passed < 0:
            return orig, (orig - today).days
        for interval in EBBINGHAUS_DAYS:
            if passed < interval:
                next_d = orig + timedelta(days=interval)
                return next_d, (next_d - today).days
        return None, None

    if repeat == "custom":
        cr = item.get("customRepeat") or {"repeatType": "byDueDate", "freq": 1, "unit": "week", "weekdays": [], "skipHolidays": False, "selectedDates": [], "lastCompletedAt": None}
        rt = cr.get("repeatType") or "byDueDate"
        base = orig
        if rt == "byCompletion" and cr.get("lastCompletedAt"):
            try:
                lc = date.fromisoformat(cr["lastCompletedAt"])
                if lc >= orig:
                    base = lc
            except ValueError:
                pass
        if rt == "bySelectedDates":
            sd = sorted(cr.get("selectedDates") or [])
            for ds in sd:
                try:
                    d = date.fromisoformat(ds)
                    if d >= today:
                        return d, (d - today).days
                except ValueError:
                    continue
            return None, None

        f = cr.get("freq") or 1
        u = cr.get("unit") or "week"
        # JS weekdays: 0=Sun..6=Sat → Python: 0=Mon..6=Sun
        wds_js = cr.get("weekdays") or [(base.weekday() + 1) % 7]
        wds = [(w + 6) % 7 for w in wds_js]
        skip = cr.get("skipHolidays") or False

        def _skip_by_unit(d: date, unit: str) -> date:
            if not skip:
                return d
            x = d
            for _ in range(100):
                if not _is_cn_holiday(x):
                    return x
                if unit == "day":
                    x += timedelta(days=1)
                elif unit == "week":
                    x += timedelta(days=7)
                elif unit == "month":
                    try:
                        x = (x.replace(day=1) + timedelta(days=32)).replace(day=d.day)
                    except ValueError:
                        x += timedelta(days=1)
                elif unit == "year":
                    x = x.replace(year=x.year + 1)
            return d

        if u == "day":
            delta = (today - base).days
            k = max(0, (delta // f) * f)
            next_d = base + timedelta(days=k)
            while next_d < today:
                next_d += timedelta(days=f)
            next_d = _skip_by_unit(next_d, "day")
            return next_d, (next_d - today).days

        if u == "week":
            # first occurrence: first date in wds on or after base
            first = base
            while first.weekday() not in wds:
                first += timedelta(days=1)
            d = today
            for _ in range(60):
                if d.weekday() in wds:
                    weeks = (d - first).days // 7
                    if weeks >= 0 and weeks % f == 0:
                        next_d = _skip_by_unit(d, "week")
                        return next_d, (next_d - today).days
                d += timedelta(days=1)
            return None, None

        if u == "month":
            months_diff = (today.year - base.year) * 12 + (today.month - base.month)
            m = ((months_diff + 1 + f - 1) // f) * f
            total = base.year * 12 + base.month - 1 + m
            y, mo = total // 12, (total % 12) + 1
            try:
                next_d = date(y, mo, base.day)
            except ValueError:
                next_d = date(y, mo, min(base.day, 28))
            if next_d < today:
                m += f
                total = base.year * 12 + base.month - 1 + m
                y, mo = total // 12, (total % 12) + 1
                try:
                    next_d = date(y, mo, base.day)
                except ValueError:
                    next_d = date(y, mo, min(base.day, 28))
            next_d = _skip_by_unit(next_d, "month")
            return next_d, (next_d - today).days

        if u == "year":
            y = today.year - base.year
            y = ((y + 1 + f - 1) // f) * f
            next_d = base.replace(year=base.year + y)
            if next_d < today:
                next_d = base.replace(year=base.year + y + f)
            next_d = _skip_by_unit(next_d, "year")
            return next_d, (next_d - today).days

        return base, (base - today).days

    return orig, (orig - today).days


def anniversary_years(date_str: str, next_date: date) -> int:
    """计算第几周年"""
    orig = date.fromisoformat(date_str)
    return next_date.year - orig.year


def build_message(item: dict, days_left: int, next_date: date) -> str:
    """构建推送消息文本"""
    name = item["name"]
    repeat = item.get("repeat", "yearly")
    note = item.get("note", "")

    if days_left == 0:
        prefix = "🎊 【今天】"
    elif days_left == 1:
        prefix = "⏰ 【明天】"
    else:
        prefix = f"📅 【{days_left} 天后】"

    lines = [f"{prefix} {name}"]

    if repeat == "yearly":
        years = anniversary_years(item["date"], next_date)
        if years > 0:
            lines.append(f"🎂 第 {years} 周年纪念日")

    lines.append(f"📆 日期：{next_date.strftime('%Y-%m-%d')}")

    if note:
        lines.append(f"💬 {note}")

    return "\n".join(lines)


# ─── 核心逻辑 ───────────────────────────────────────────────────────────────
def check_and_notify():
    data = load_events()
    items = data.get("items", [])
    remind_days: list[int] = data.get("remind_days", [7, 3, 1, 0])
    today = date.today()

    print(f"📅 今天：{today}  提醒阈值：{remind_days} 天")
    print(f"📋 共 {len(items)} 条纪念日")

    # 解析 Apprise URLs
    raw = APPRISE_URLS_RAW.strip()
    if not raw:
        print("⚠️  未设置 APPRISE_URLS 环境变量，仅输出到控制台。")
        apprise_instance = None
    else:
        urls = [u.strip() for u in raw.replace("\n", ",").split(",") if u.strip()]
        apprise_instance = apprise.Apprise()
        for url in urls:
            apprise_instance.add(url)
        print(f"🔔 已配置 {len(urls)} 个推送渠道")

    triggered = []

    for item in items:
        if not item.get("date"):
            continue

        repeat = item.get("repeat", "yearly")
        next_date, days_left = next_occurrence(item["date"], repeat, today, item)

        if next_date is None or days_left is None:
            continue

        # 结束重复：按日期
        end_repeat = item.get("endRepeat")
        if end_repeat == "endByDate" and item.get("endDate"):
            try:
                end_d = date.fromisoformat(item["endDate"])
                if next_date > end_d:
                    continue
            except ValueError:
                pass

        # 结束重复：按次数（简化处理）
        if end_repeat == "endByCount" and item.get("endCount"):
            ec = int(item["endCount"])
            orig = date.fromisoformat(item["date"])
            if repeat == "daily":
                cnt = (today - orig).days + 1
            elif repeat == "weekly":
                cnt = (today - orig).days // 7 + 1
            elif repeat == "monthly":
                cnt = (today.year - orig.year) * 12 + (today.month - orig.month) + 1
            elif repeat == "yearly":
                cnt = today.year - orig.year + 1
            elif repeat == "ebbinghaus":
                passed = (today - orig).days
                cnt = sum(1 for d in EBBINGHAUS_DAYS if passed >= d) if passed >= 0 else 0
            else:
                cnt = 0
            if cnt >= ec:
                continue

        # 对于 once 类型，已过期则跳过
        if repeat == "once" and days_left < 0:
            continue

        if days_left in remind_days:
            msg = build_message(item, days_left, next_date)
            triggered.append((item["name"], days_left, msg))
            print(f"\n{'='*50}")
            print(msg)

    if not triggered:
        print("\n✅ 今天没有需要提醒的纪念日。")
        return

    print(f"\n📣 共 {len(triggered)} 条提醒需要推送")

    if apprise_instance is None:
        return

    # 合并为一条消息发送，也可逐条发送
    title = f"纪念日提醒（{today.strftime('%m月%d日')}）共 {len(triggered)} 条"
    body = "\n\n".join(msg for _, _, msg in triggered)

    success = apprise_instance.notify(title=title, body=body)
    if success:
        print("✅ 推送成功！")
    else:
        print("❌ 推送失败，请检查 APPRISE_URLS 配置。")
        sys.exit(1)


# ─── 入口 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    check_and_notify()
