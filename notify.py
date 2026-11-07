#!/usr/bin/env python3
"""斗鱼直播间开播提醒：轮询房间状态，开播时通过 Server酱 推送到微信。"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOM_ID = os.environ.get("DOUYU_ROOM_ID", "71415")
SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
STATE_FILE = Path(__file__).with_name("state.json")

API = "https://open.douyucdn.cn/api/RoomApi/room/{room_id}"
PUSH_API = "https://sctapi.ftqq.com/{sendkey}.send"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )


def fetch_room(room_id):
    req = urllib.request.Request(
        API.format(room_id=room_id),
        headers={"User-Agent": UA, "Referer": "https://www.douyu.com/"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("error") != 0:
        raise RuntimeError(f"接口返回异常: {payload}")
    return payload["data"]


def send_wechat(title, body):
    data = urllib.parse.urlencode({"title": title, "desp": body}).encode("utf-8")
    req = urllib.request.Request(
        PUSH_API.format(sendkey=SENDKEY),
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("code") != 0:
        raise RuntimeError(f"Server酱推送失败: {result}")
    return result


def main():
    dry_run = "--dry-run" in sys.argv
    room = fetch_room(ROOM_ID)

    is_live = str(room.get("room_status")) == "1"
    start_time = room.get("start_time") or ""
    owner = room.get("owner_name") or ""
    room_name = room.get("room_name") or ""
    cate = room.get("cate_name") or ""
    url = f"https://www.douyu.com/{ROOM_ID}"

    print(
        f"[{ROOM_ID}] {owner} | {room_name} | "
        f"room_status={room.get('room_status')} | start_time={start_time}"
    )

    if not is_live:
        print("未开播，跳过。")
        return

    state = load_state()
    if state.get(str(ROOM_ID)) == start_time:
        print(f"本场直播（{start_time}）已提醒过，跳过。")
        return

    title = f"{owner} 开播了！"
    body = (
        f"**{owner}** 正在直播\n\n"
        f"- 标题：{room_name}\n"
        f"- 分区：{cate}\n"
        f"- 开播时间：{start_time}\n\n"
        f"[点击进入直播间]({url})"
    )

    if dry_run or not SENDKEY:
        print("--- 通知内容 ---")
        print(title)
        print(body)
        if not SENDKEY and not dry_run:
            print("缺少环境变量 SERVERCHAN_SENDKEY，未推送。")
            sys.exit(1)
        return

    send_wechat(title, body)
    state[str(ROOM_ID)] = start_time
    save_state(state)
    print("推送成功，已记录本场直播状态。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # 网络抖动由下一次定时任务重试
        print(f"执行失败，5 分钟后重试：{exc}")
        sys.exit(0)
