#!/usr/bin/env python3
"""小红书视频链接 → 逐字稿 + 归档元数据。

video2text.py 走 yt-dlp，对小红书（无提取器、视频直链带时效签名）不可用，
本脚本为小红书专用入口：curl 抓页 → 解析 window.__INITIAL_STATE__ → 备份源下载
→ ffmpeg 转 16k 音频 → 腾讯云 ASR，并把封面一并下载到 out_dir 供后续 OCR。

用法：
    python3 xhs_note.py "<小红书 explore 链接>" [--out DIR]

输出约定（与 video2text.py 对齐）：
- stderr：进度信息 + `[标题] xxx` / `[作者] xxx`
- stdout：单个 JSON（ensure_ascii=False），含 noteId/type/title/desc/tags/作者/互动数/
         本地文件路径(cover/video/audio)/逐字稿(text 去时间戳, text_timed 带时间戳)
- 图文笔记（type=normal）不转录：text 为空，靠 AI 对图片做 OCR
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
REFERER = "https://www.xiaohongshu.com/"
CURL_HEADERS = [
    "-H", f"User-Agent: {UA}",
    "-H", f"Referer: {REFERER}",
    "-H", "Accept-Language: zh-CN,zh;q=0.9",
]


def parse_env(path: str):
    """把单个 .env 文件的键值读入 os.environ（覆盖同名键）。"""
    if not path or not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()


def load_env():
    """密钥加载：环境变量 < ~/.cc-switch/skills/.env < 当前工作目录 .env（后者覆盖）。"""
    parse_env(os.path.expanduser("~/.cc-switch/skills/.env"))
    parse_env(os.path.join(os.getcwd(), ".env"))


def run(cmd: list, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def http_get(url: str, dest: str) -> bool:
    """带 UA/Referer 下载，返回是否成功（curl 退出码 + 文件非空）。"""
    cmd = ["curl", "-sL", "--retry", "3", "--retry-all-errors",
           *CURL_HEADERS, "-o", dest, url]
    r = run(cmd)
    if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) == 0:
        if os.path.exists(dest):
            os.remove(dest)
        return False
    return True


def fetch_page(url: str, dest: str) -> str:
    print("[1/6] 抓取页面...", file=sys.stderr)
    if not http_get(url, dest):
        sys.exit("抓取页面失败（链接可能失效/需登录/xsec_token 过期）")
    return dest


def parse_state(page_path: str, note_id: str) -> dict:
    """解析 INITIAL_STATE，返回 noteDetailMap 里的 note 对象。"""
    raw = open(page_path, encoding="utf-8", errors="ignore").read()
    m = re.search(r"window\.__INITIAL_STATE__=(.*?)</script>", raw, re.S)
    if not m:
        sys.exit("页面里找不到 __INITIAL_STATE__（可能被风控/需登录）")
    s = re.sub(r":undefined", ":null", m.group(1))
    try:
        d = json.loads(s)
    except json.JSONDecodeError as e:
        sys.exit(f"INITIAL_STATE JSON 解析失败: {e}")
    try:
        note = d["note"]["noteDetailMap"][note_id]["note"]
    except KeyError:
        sys.exit(f"noteDetailMap 里找不到 noteId={note_id}（链接与页面不匹配？）")
    return note


def pick_cover_url(note: dict):
    """取封面最大分辨率图的直链；找不到返回 None。"""
    urls = []
    for im in note.get("imageList") or []:
        for info in im.get("infoList") or []:
            u = info.get("url")
            if u:
                urls.append(u)
    # infoList 通常按分辨率升序，取最后一个；同时保留前面的作为降级源
    if urls:
        return urls[-1], list(dict.fromkeys(urls))
    return None, []


def pick_stream(note: dict):
    """返回 (masterUrl, [backupUrls]) 或 (None, [])。"""
    try:
        st = note["video"]["media"]["stream"]["h264"][0]
    except (KeyError, IndexError, TypeError):
        return None, []
    return st.get("masterUrl"), list(st.get("backupUrls") or [])


def download_video(out_dir: str, master: str, backups: list) -> str:
    print("[2/6] 下载视频（优先 backup 源，支持续传）...", file=sys.stderr)
    dest = os.path.join(out_dir, "video.mp4")
    # backup 源（腾讯 COS）稳定且支持 -C - 断点续传；master 源带时效签名不可靠，仅兜底
    candidates = backups + ([master] if master else [])
    for url in candidates:
        if http_get(url, dest):
            return dest
    sys.exit("视频下载失败（master/backup 均不可用）")


def convert_audio(video_path: str, out_dir: str) -> str:
    print("[3/6] 转码音频 (16kHz mono)...", file=sys.stderr)
    out = os.path.join(out_dir, "audio_16k.mp3")
    r = run(["ffmpeg", "-y", "-loglevel", "error",
             "-i", video_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", out])
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit(f"ffmpeg 转码失败:\n{r.stderr}")
    return out


def split_for_asr(audio_path: str, out_dir: str):
    """音频 >5MB 时按 ~7 分钟切片（64kbps≈3.4MB/段），返回 [(seg_path, start_s)]。

    腾讯 CreateRecTask 以 SourceType=1 把音频 base64 塞进请求体，单文件上限 5MB，
    长视频需分片各提交一次，再按 start 偏移回全局时间轴。
    """
    mb = os.path.getsize(audio_path) / (1024 * 1024)
    if mb <= 5:
        return [(audio_path, 0.0)]
    print(f"音频 {mb:.1f}MB 超过单任务 5MB 上限，自动分片转录…", file=sys.stderr)
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path])
    try:
        total = float(r.stdout.strip())
    except ValueError:
        sys.exit(f"无法获取音频时长: {r.stderr}")
    chunk_s = 420  # 64kbps × 420s ≈ 3.4MB，留足余量
    segs, start, idx = [], 0.0, 0
    while start < total - 1e-3:
        seg = os.path.join(out_dir, f"audio_seg_{idx:02d}.mp3")
        rr = run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}",
                  "-t", str(chunk_s), "-i", audio_path, "-c", "copy", seg])
        if rr.returncode != 0 or not os.path.exists(seg):
            sys.exit(f"分片失败:\n{rr.stderr}")
        if os.path.getsize(seg) / (1024 * 1024) > 5:
            sys.exit(f"分片仍超 5MB（第 {idx} 段），请调小 chunk_s")
        segs.append((seg, start))
        start += chunk_s
        idx += 1
    return segs


def shift_timestamps(text: str, base_s: float) -> str:
    """把某段的分片内时间戳 [m:ss.f,m:ss.f] 整体加 base_s，拼回全局时间轴。"""
    if not text or base_s <= 0:
        return text
    def fmt(t: float) -> str:
        return f"{int(t // 60)}:{t % 60:.1f}"
    def repl(m):
        a = int(m.group(1)) * 60 + float(m.group(2)) + base_s
        b = int(m.group(3)) * 60 + float(m.group(4)) + base_s
        return f"[{fmt(a)},{fmt(b)}]"
    return re.sub(r"\[(\d+):(\d+\.\d+),(\d+):(\d+\.\d+)\]", repl, text)


def transcribe(audio_path: str) -> str:
    """腾讯云录音文件识别，返回带 [t0,t1] 时间戳的原文。"""
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.asr.v20190614 import asr_client, models

    sid = os.environ.get("TENCENTCLOUD_SECRET_ID")
    skey = os.environ.get("TENCENTCLOUD_SECRET_KEY")
    if not sid or not skey:
        sys.exit("请配置 TENCENTCLOUD_SECRET_ID/KEY：环境变量、~/.cc-switch/skills/.env 或 cwd .env")

    print("[4/6] 提交腾讯云 ASR...", file=sys.stderr)
    data = base64.b64encode(open(audio_path, "rb").read()).decode()
    cred = credential.Credential(sid, skey)
    hp = HttpProfile(); hp.endpoint = "asr.tencentcloudapi.com"
    cp = ClientProfile(); cp.httpProfile = hp
    client = asr_client.AsrClient(cred, "", cp)

    req = models.CreateRecTaskRequest()
    req.from_json_string(json.dumps({"EngineModelType": "16k_zh", "ChannelNum": 1,
                                     "ResTextFormat": 0, "SourceType": 1,
                                     "Data": data, "DataLen": os.path.getsize(audio_path)}))
    task_id = client.CreateRecTask(req).Data.TaskId
    print(f"  任务ID: {task_id}", file=sys.stderr)

    print("[5/6] 等待识别完成...", file=sys.stderr)
    preq = models.DescribeTaskStatusRequest()
    preq.from_json_string(json.dumps({"TaskId": task_id}))
    for i in range(60):
        time.sleep(5)
        st = client.DescribeTaskStatus(preq).Data.Status
        if st == 2:
            return client.DescribeTaskStatus(preq).Data.Result or ""
        if st == 3:
            sys.exit("识别失败: " + (client.DescribeTaskStatus(preq).Data.ErrorMsg or ""))
        print(f"  ...{(i + 1) * 5}s", file=sys.stderr)
    sys.exit("识别超时")


def clean_timestamps(text: str) -> str:
    """去掉每句前的 [t0,t1] 时间戳前缀。"""
    return re.sub(r"\[\d+:\d+\.\d+,\d+:\d+\.\d+\]\s*", "", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="小红书 explore 链接")
    ap.add_argument("--out", default=None, help="输出目录（默认 /tmp/xhs_<noteId>，脚本不清理）")
    ap.add_argument("--meta-only", action="store_true",
                    help="只抓页解析元数据，不下载/不转录（调试用）")
    args = ap.parse_args()
    load_env()

    m = re.search(r"/explore/([0-9a-fA-F]{24})", args.url)
    if not m:
        sys.exit("无法从链接解析 noteId，需 xiaohongshu.com/explore/<id> 形式")
    note_id = m.group(1)

    out_dir = args.out or os.path.join(tempfile_dir(), f"xhs_{note_id}")
    os.makedirs(out_dir, exist_ok=True)

    page = os.path.join(out_dir, "page.html")
    fetch_page(args.url, page)
    note = parse_state(page, note_id)

    # ---- 元数据 ----
    title = note.get("title") or ""
    type_ = note.get("type") or ""
    desc = note.get("desc") or ""
    tags = [t.get("name") for t in (note.get("tagList") or []) if t.get("name")]
    user = note.get("user") or {}
    nickname = user.get("nickname") or ""
    interact = note.get("interactInfo") or {}
    dur_ms = None
    try:
        dur_ms = note["video"]["media"]["stream"]["h264"][0].get("videoDuration")
    except (KeyError, IndexError, TypeError):
        pass
    print(f"[标题] {title}", file=sys.stderr)
    print(f"[作者] {nickname}", file=sys.stderr)

    # ---- 封面 ----
    cover_url, cover_candidates = pick_cover_url(note)
    cover_path = None
    if cover_candidates:
        print("[—] 下载封面...", file=sys.stderr)
        for u in cover_candidates:
            # webpic 常需 https+Referer；逐个尝试
            if http_get(u, os.path.join(out_dir, "cover.jpg")):
                cover_path = os.path.join(out_dir, "cover.jpg")
                break

    result = {
        "noteId": note_id, "type": type_, "title": title, "desc": desc,
        "tags": tags, "cover": cover_path,
        "author": {"nickname": nickname, "userId": user.get("userId", ""),
                   "profile_url": f"https://www.xiaohongshu.com/user/profile/{user.get('userId','')}"},
        "interact": {"liked": interact.get("likedCount", ""),
                     "collected": interact.get("collectedCount", ""),
                     "commented": interact.get("commentCount", ""),
                     "shared": interact.get("shareCount", "")},
        "duration_s": round(dur_ms / 1000, 1) if dur_ms else None,
        "out_dir": out_dir, "video": None, "audio": None,
        "text": "", "text_timed": "",
    }

    if not args.meta_only and type_ == "video":
        master, backups = pick_stream(note)
        video_path = download_video(out_dir, master, backups)
        audio_path = convert_audio(video_path, out_dir)
        print("[6/6] 语音识别...", file=sys.stderr)
        parts = []
        segs = split_for_asr(audio_path, out_dir)
        for i, (seg, start) in enumerate(segs):
            if len(segs) > 1:
                print(f"  第 {i + 1}/{len(segs)} 段…", file=sys.stderr)
            part = transcribe(seg).strip()
            parts.append(shift_timestamps(part, start))
        timed = "\n".join(p for p in parts if p).strip()
        result.update(video=video_path, audio=audio_path,
                      text=clean_timestamps(timed).strip(), text_timed=timed)
    elif not args.meta_only:
        print(f"[提示] type={type_}，非视频不转录，请 AI 对封面/图集做 OCR", file=sys.stderr)

    print(json.dumps(result, ensure_ascii=False))


def tempfile_dir():
    import tempfile
    return tempfile.gettempdir()


if __name__ == "__main__":
    main()
