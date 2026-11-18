#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
博客笔记一键上传工具 (Hexo + Butterfly, 仓库在本机 WSL Ubuntu)

用法示例（在 WSL 终端里运行）:

  # 单篇, 嵌套分类 vulhub靶场/spring, 带标签
  python3 ~/blog/my-blog/upload.py "/mnt/e/笔记/vulhub/spring/xxx.md" \
      --category "vulhub靶场,spring" --tags "Spring,SpEL,RCE"

  # 整个文件夹批量上传, 分类 网工
  python3 ~/blog/my-blog/upload.py "/mnt/e/笔记/网工" --category "网工"

  # 只入库配图, 先不推送
  python3 ~/blog/my-blog/upload.py "笔记.md" --category 网工 --no-push

  # 预览(不写文件、不提交)
  python3 ~/blog/my-blog/upload.py "笔记.md" --category 网工 --dry-run

说明:
  - 自动补全 front-matter (title/date/tags/categories)
  - 自动抽取正文里的本地图片, 拷贝到 source/img/<子目录>/, 并改写引用路径
  - Markdown 图片 -> /img/<子目录>/xxx (交给 hexo 加站点前缀)
  - HTML  图片 -> /blog/img/<子目录>/xxx (手写全路径)
  - 外链 http/https/data: 原样保留
  - 最后 git add/commit/push 到 main, 由 GitHub Actions 自动部署
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# ---------- 路径常量 ----------
BLOG_DIR = Path(__file__).resolve().parent
POSTS_DIR = BLOG_DIR / "source" / "_posts"
IMG_ROOT = BLOG_DIR / "source" / "img"
MD_IMG_PREFIX = "/img"        # Markdown 引用前缀
HTML_IMG_PREFIX = "/blog/img"  # HTML <img> 引用前缀

# 收集本次结果, 最后汇总
REPORT = {"posts": [], "images_ok": 0, "images_missing": [], "errors": []}


def to_wsl_path(p: str) -> str:
    """把 Windows 盘符路径 / file:/// 转成 WSL 路径, 反斜杠转正斜杠。"""
    p = p.strip().strip('"').strip("'")
    if p.startswith("file:///"):
        p = p[len("file:///"):]
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return p.replace("\\", "/")


def safe_filename(name: str) -> str:
    """清洗文件名里的文件系统非法字符。"""
    return re.sub(r'[\\/:*?"<>|\r\n]+', "", name).strip()


def yaml_dump_scalar(s: str) -> str:
    """title 用双引号包裹, 转义内部双引号和反斜杠。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_front_matter(text: str):
    """拆分已有 front-matter 和正文。返回 (fm_dict 或 None, body)。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    if yaml:
        try:
            fm = yaml.safe_load(fm_raw) or {}
        except Exception:
            fm = {}
    return fm, body


def flatten_categories(fm_cats):
    """把 front-matter 里的分类(字符串/列表/嵌套)压平成一维列表。"""
    if not fm_cats:
        return []
    if isinstance(fm_cats, str):
        return [fm_cats]
    out = []

    def walk(x):
        if isinstance(x, list):
            for i in x:
                walk(i)
        else:
            out.append(str(x))

    walk(fm_cats)
    return out


def unique_dest(directory: Path, name: str) -> Path:
    base, ext = os.path.splitext(name)
    cand = name
    i = 1
    while (directory / cand).exists():
        cand = f"{base}_{i}{ext}"
        i += 1
    return directory / cand


def migrate_image(src: str, md_path: Path, img_sub: str, mode: str, dry_run: bool = False) -> str:
    """拷贝本地图片到 img 子目录, 返回改写后的 web 路径; 外链原样, 缺失记录警告。"""
    src = src.strip()
    # 外链 / base64 原样保留
    if re.match(r"^(https?:|data:|//)", src):
        return src

    local = Path(to_wsl_path(src))
    if not local.is_absolute():
        local = (md_path.parent / local).resolve()

    if not local.exists():
        REPORT["images_missing"].append(f"{md_path.name}: 找不到图片 -> {src}")
        return src  # 找不到则保留原路径, 后续人工补

    if dry_run:
        REPORT["images_ok"] += 1
        if mode == "html":
            return f"{HTML_IMG_PREFIX}/{img_sub}/{local.name}"
        return f"{MD_IMG_PREFIX}/{img_sub}/{local.name}"

    target_dir = IMG_ROOT / img_sub
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_dest(target_dir, local.name)
    shutil.copy2(local, dest)

    REPORT["images_ok"] += 1
    if mode == "html":
        return f"{HTML_IMG_PREFIX}/{img_sub}/{dest.name}"
    return f"{MD_IMG_PREFIX}/{img_sub}/{dest.name}"


def rewrite_images(body: str, md_path: Path, img_sub: str, dry_run: bool = False) -> str:
    # 1) Markdown: ![alt](src)
    def repl_md(m):
        alt, old = m.group(1), m.group(2)
        new = migrate_image(old, md_path, img_sub, "md", dry_run)
        return f"![{alt}]({new})"

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl_md, body)

    # 2) HTML: <img ... src="...">  (保留其余属性, 只替换 src)
    def repl_tag(m):
        tag = m.group(0)

        def src_repl(sm):
            old = sm.group(1)
            new = migrate_image(old, md_path, img_sub, "html", dry_run)
            return f'src="{new}"'

        return re.sub(r'src="([^"]+)"', src_repl, tag)

    body = re.sub(r"<img\b[^>]*>", repl_tag, body)
    return body


def build_front_matter(title, date, tags, categories) -> str:
    lines = ["---", f"title: {yaml_dump_scalar(title)}", f"date: {date} 00:00:00"]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")
    if categories:
        lines.append("categories:")
        if len(categories) == 1:
            lines.append(f"  - {categories[0]}")
        else:
            lines.append("  - [" + ", ".join(categories) + "]")
    lines.append("---")
    return "\n".join(lines)


def collect_md_files(inputs):
    files = []
    for inp in inputs:
        p = Path(to_wsl_path(inp))
        if p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        elif p.is_file():
            files.append(p)
        else:
            REPORT["errors"].append(f"路径不存在: {inp}")
    return files


def process_one(md_file: Path, args, today: str, dry_run: bool):
    raw = md_file.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_front_matter(raw)
    fm = fm or {}

    # title
    title = args.title or fm.get("title") or md_file.stem
    # date
    date = args.date or str(fm.get("date") or today)
    if isinstance(date, datetime.date):
        date = date.isoformat()
    # tags
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    else:
        t = fm.get("tags")
        tags = [str(x) for x in t] if isinstance(t, list) else ([str(t)] if t else [])
    # categories
    if args.category:
        categories = [c.strip() for c in args.category.split(",") if c.strip()]
    else:
        categories = flatten_categories(fm.get("categories"))
    # 图片子目录: 默认分类最后一级
    img_sub = args.img_dir or (categories[-1] if categories else "misc")

    body = rewrite_images(body, md_file, img_sub, dry_run)
    fm_block = build_front_matter(title, date, tags, categories)
    out_text = fm_block + "\n\n" + body.strip() + "\n"

    out_name = safe_filename(title) + ".md"
    out_path = POSTS_DIR / out_name

    if dry_run:
        print(f"[预览] {md_file.name}  ->  _posts/{out_name}  分类={categories} 标签={tags} 图片目录={img_sub}")
        REPORT["posts"].append(out_name)
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_text, encoding="utf-8")
    print(f"[入库] {md_file.name}  ->  source/_posts/{out_name}")
    REPORT["posts"].append(out_name)


def git_commit_push(dry_run: bool, no_push: bool):
    if dry_run:
        print("\n[dry-run] 未执行 git 操作。")
        return
    subprocess.run(["git", "-c", "core.quotepath=false", "add", "source/_posts", "source/img"],
                   cwd=BLOG_DIR, check=True)
    titles = "、".join(REPORT["posts"])
    msg = f"新增笔记: {titles}" if titles else "更新博客笔记"
    subprocess.run(["git", "-c", "core.quotepath=false", "commit", "-m", msg],
                   cwd=BLOG_DIR, check=True)
    if no_push:
        print("\n[--no-push] 已本地提交, 未推送。稍后手动: git push origin main")
        return
    print("\n推送 main ...")
    for i in range(1, 9):
        r = subprocess.run(["git", "push", "origin", "main"], cwd=BLOG_DIR)
        if r.returncode == 0:
            print(f"推送成功(第{i}次)")
            return
        print(f"第{i}次推送失败, 10 秒后重试...")
        import time
        time.sleep(10)
    REPORT["errors"].append("多次重试后推送仍失败, 请检查网络/SSH 后手动 git push")


def main():
    ap = argparse.ArgumentParser(description="一键上传 md 笔记到博客")
    ap.add_argument("inputs", nargs="+", help="md 文件或文件夹路径(Windows/E:\\... 或 WSL 路径均可)")
    ap.add_argument("--category", help="分类, 逗号分隔; 嵌套: vulhub靶场,spring")
    ap.add_argument("--tags", help="标签, 逗号分隔")
    ap.add_argument("--img-dir", help="图片子目录名, 默认取分类最后一级")
    ap.add_argument("--title", help="覆盖文章标题")
    ap.add_argument("--date", help="日期 YYYY-MM-DD, 默认今天")
    ap.add_argument("--no-push", action="store_true", help="只本地提交, 不推送")
    ap.add_argument("--dry-run", action="store_true", help="只预览, 不写文件不提交")
    args = ap.parse_args()

    today = args.date or datetime.date.today().isoformat()
    files = collect_md_files(args.inputs)
    if not files:
        print("未找到任何 .md 文件。")
        sys.exit(1)

    print(f"共 {len(files)} 篇笔记待处理\n")
    for f in files:
        try:
            process_one(f, args, today, args.dry_run)
        except Exception as e:
            REPORT["errors"].append(f"{f.name}: {e}")
            print(f"[出错] {f.name}: {e}")

    print("\n===== 汇总 =====")
    print(f"文章: {len(REPORT['posts'])} 篇")
    print(f"图片迁移: {REPORT['images_ok']} 张")
    if REPORT["images_missing"]:
        print("缺失图片:")
        for m in REPORT["images_missing"]:
            print("  - " + m)

    git_commit_push(args.dry_run, args.no_push)

    if REPORT["errors"]:
        print("\n错误:")
        for e in REPORT["errors"]:
            print("  - " + e)
        sys.exit(1)


if __name__ == "__main__":
    main()
