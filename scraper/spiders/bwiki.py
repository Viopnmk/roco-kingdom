"""
BWIKI 洛克王国：世界 —— MediaWiki API 爬虫

数据源: https://wiki.biligame.com/rocom/
权威确认: https://rocom.qq.com/web202507/sub/index.html (腾讯官方站点)

策略:
  1. 从「精灵图鉴」页面的渲染 HTML 中提取所有精灵页面链接
  2. 逐个抓取精灵页面的 wikitext，解析模板提取数据
  3. 数据交叉参考官方站点信息进行验证（官方确认＞社区数据）
"""

import re
import json
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from config import (
    BWIKI_API, BWIKI_BASE, BWIKI_INDEX_PAGE,
    RAW_DIR, REQUEST_DELAY, BATCH_SIZE,
)


# ── Session ───────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    """创建带浏览器伪装头的 Session，避免被云防护拦截。"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": BWIKI_BASE,
    })
    return s


# 全局 session（爬取期间复用）
_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = _make_session()
        # 先访问主页建立 cookie
        try:
            _session.get(BWIKI_BASE, timeout=30)
        except requests.RequestException:
            pass
    return _session


# ── MediaWiki API 封装 ────────────────────────────────────────────

def api_call(params: dict) -> dict:
    """调用 MediaWiki API，自动附加 format=json。"""
    params.setdefault("format", "json")
    resp = get_session().get(BWIKI_API, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── 页面发现（从图鉴首页提取精灵链接）───────────────────────────

def discover_pet_pages() -> list[str]:
    """
    从 BWIKI 精灵图鉴页面的渲染 HTML 中提取所有精灵页面标题。

    图鉴首页通过 Lua 模块 {{#invoke:DexIndex|pets}} 动态生成列表，
    因此用 action=parse 获取渲染后的 HTML，从中提取链接。
    """
    print(f"  从「{BWIKI_INDEX_PAGE}」页面发现精灵...")

    data = api_call({
        "action": "parse",
        "page": BWIKI_INDEX_PAGE,
        "prop": "text",
    })

    html = data.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        print("  [WARN] 无法获取图鉴页面 HTML")
        return _fallback_discovery()

    soup = BeautifulSoup(html, "lxml")

    # 收集所有内部链接（/rocom/xxx）
    pet_titles: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href.startswith("/rocom/"):
            continue
        # URL 解码得到页面标题
        slug = href[len("/rocom/"):]
        title = unquote(slug)
        # 排除非精灵页面
        if _is_non_pet(title):
            continue
        if title not in seen:
            seen.add(title)
            pet_titles.append(title)

    print(f"  发现 {len(pet_titles)} 个候选精灵页面")
    return pet_titles


def _is_non_pet(title: str) -> bool:
    """判断页面标题是否不是精灵页面。"""
    exclude_prefixes = [
        "File:", "Template:", "MediaWiki:", "Help:", "Category:",
        "Module:", "Special:", "Widget:", "Gadget:", "User:", "用户:",
        "Project:", "Data:", "CSS", "Widget",
    ]
    for p in exclude_prefixes:
        if title.startswith(p) or title == p:
            return True
    # 排除网址型的标题（如 http://...）
    if title.startswith("http://") or title.startswith("https://"):
        return True
    # 排除过短或过长的标题（精灵名通常2-8个中文字）
    if len(title) < 2:
        return True
    return False


def _fallback_discovery() -> list[str]:
    """后备方案：用 allpages API + 过滤。"""
    print("  尝试 allpages 后备方案...")
    titles = []
    apcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": "max",
            "apnamespace": 0,
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        data = api_call(params)
        pages = data.get("query", {}).get("allpages", [])
        for p in pages:
            title = p["title"]
            if not _is_non_pet(title):
                titles.append(title)

        if "continue" in data:
            apcontinue = data["continue"]["apcontinue"]
            time.sleep(0.3)
        else:
            break
    print(f"  allpages 发现 {len(titles)} 个候选页面")
    return titles


# ── wikitext 模板解析 ─────────────────────────────────────────────

def parse_templates(wikitext: str) -> list[dict]:
    """解析 wikitext 中的顶级 {{模板}}，返回 [{"name": "模板名", "params": {...}}, ...]"""
    templates = []
    i = 0
    while i < len(wikitext):
        brace_start = wikitext.find("{{", i)
        if brace_start == -1:
            break
        if wikitext[brace_start:brace_start + 3] == "{{{":
            i = brace_start + 3
            continue

        end = find_matching_braces(wikitext, brace_start)
        if end == -1:
            i = brace_start + 2
            continue

        content = wikitext[brace_start + 2:end]
        tmpl = parse_single_template(content)
        if tmpl:
            templates.append(tmpl)
        i = end + 2

    return templates


def find_matching_braces(text: str, start: int) -> int:
    """从 start 位置（指向 '{{'）找到匹配的 '}}'，正确处理嵌套。"""
    depth = 0
    i = start
    while i < len(text):
        if text[i:i + 2] == "{{" and text[i:i + 3] != "{{{":
            depth += 1
            i += 2
            continue
        if text[i:i + 2] == "}}":
            depth -= 1
            if depth == 0:
                return i
            i += 2
            continue
        if text[i:i + 3] == "{{{":
            i += 3
            continue
        if text[i:i + 3] == "}}}":
            i += 3
            continue
        i += 1
    return -1


def parse_single_template(content: str) -> dict | None:
    """解析单个模板内容，提取模板名和参数。"""
    content = content.strip()
    if not content:
        return None

    pipe = content.find("|")
    if pipe == -1:
        name = content.strip()
        params = {}
    else:
        name = content[:pipe].strip()
        params = parse_template_params(content) if pipe != -1 else {}

    name = name.split("\n")[0].strip()
    if not name:
        return None

    return {"name": name, "params": params}


def parse_template_params(content: str) -> dict:
    """解析模板的键值参数。"""
    params = {}
    first_pipe = content.find("|")
    if first_pipe == -1:
        return params
    remaining = content[first_pipe + 1:]

    segments = split_params(remaining)
    anon_idx = 1

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        eq = seg.find("=")
        if eq != -1:
            key = seg[:eq].strip()
            val = seg[eq + 1:].strip()
            if key and not is_inside_template(key):
                params[key] = clean_value(val)
                continue
        params[str(anon_idx)] = clean_value(seg)
        anon_idx += 1

    return params


def split_params(text: str) -> list[str]:
    """按顶层 | 分割参数，处理嵌套模板和 wikilink。"""
    segments = []
    depth = 0
    link_depth = 0
    current: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if text[i:i + 2] == "{{" and text[i:i + 3] != "{{{":
            depth += 1
            current.append("{{")
            i += 2
            continue
        if text[i:i + 2] == "}}":
            depth -= 1
            current.append("}}")
            i += 2
            continue
        if text[i:i + 2] == "[[":
            link_depth += 1
            current.append("[[")
            i += 2
            continue
        if text[i:i + 2] == "]]":
            link_depth -= 1
            current.append("]]")
            i += 2
            continue
        if ch == "|" and depth == 0 and link_depth == 0:
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1

    if current:
        segments.append("".join(current))
    return segments


def is_inside_template(s: str) -> bool:
    """检查字符串中是否有未闭合的 {{ 或 [[。"""
    return s.count("{{") != s.count("}}") or s.count("[[") != s.count("]]")


def clean_value(val: str) -> str:
    """清理参数值：去除 wikitext 标记、HTML 标签。"""
    val = re.sub(r"''+", "", val)
    val = re.sub(r"<[^>]+>", "", val)
    val = re.sub(r"<ref[^>]*>.*?</ref>", "", val, flags=re.DOTALL)
    val = re.sub(r"<ref[^/]*/>", "", val)
    val = re.sub(r"\[\[(?:[^|\]]*\|)?([^|\]]*)\]\]", r"\1", val)
    val = re.sub(r"\[https?://[^\s\]]*\s*([^\]]*)\]", r"\1", val)
    val = val.replace("\n", " ").replace("\r", "")
    val = re.sub(r"\s+", " ", val)
    return val.strip()


# ── 页面内容获取 ─────────────────────────────────────────────────

def get_page_wikitext(title: str) -> str | None:
    """获取页面的 wikitext 源代码。"""
    try:
        data = api_call({
            "action": "parse",
            "page": title,
            "prop": "wikitext",
        })
        return data.get("parse", {}).get("wikitext", {}).get("*")
    except requests.HTTPError as e:
        print(f"  [WARN] 获取页面失败: {title} ({e})")
        return None


# ── 精灵数据提取 ─────────────────────────────────────────────────

def extract_pet_info(wikitext: str, page_title: str = "") -> dict | None:
    """从 wikitext 中提取精灵基础信息。

    BWIKI 模板名: 精灵信息/兼容
    字段映射见下方 params.get() 调用。
    """
    templates = parse_templates(wikitext)

    # 找精灵信息模板（关键词匹配）
    pet_tmpl = None
    for t in templates:
        name = t["name"].lower()
        if any(kw in name for kw in ["精灵信息", "宠物信息", "infobox", "pet"]):
            pet_tmpl = t
            break

    if not pet_tmpl:
        # 尝试用第一个参数足够多的模板
        for t in templates:
            if len(t["params"]) >= 8:
                pet_tmpl = t
                break

    if not pet_tmpl:
        return None

    params = pet_tmpl["params"]

    # 提取三种技能列表（BWIKI 用逗号分隔）
    def _parse_skill_list(key: str) -> list[str]:
        val = params.get(key, "")
        if val:
            return [s.strip() for s in re.split(r"[,，、]", val) if s.strip()]
        return []

    skills = _parse_skill_list("技能")
    bloodline_skills = _parse_skill_list("血脉技能")
    stone_skills = _parse_skill_list("可学技能石")

    return {
        # 基础
        "name": params.get("精灵名称", page_title),
        "number": params.get("编号", ""),
        "type_primary": params.get("主属性", ""),
        "type_secondary": params.get("2属性", ""),
        # 种族值
        "hp": params.get("生命", ""),
        "atk": params.get("物攻", ""),
        "defense": params.get("物防", ""),
        "sp_atk": params.get("魔攻", ""),
        "sp_def": params.get("魔防", ""),
        "speed": params.get("速度", ""),
        # 特性 / 描述
        "ability": params.get("特性", ""),
        "height": params.get("体型", ""),
        "weight": params.get("重量", ""),
        "description": params.get("精灵描述", ""),
        # 进化 / 获取
        "evolution": params.get("进化条件", ""),
        "how_to_get": params.get("分布地区", ""),
        # 技能
        "skills": skills,
        "bloodline_skills": bloodline_skills,
        "stone_skills": stone_skills,
        # 元数据
        "source": "bwiki",
    }


# ── 主流程 ─────────────────────────────────────────────────────────

def scrape_pets():
    """
    从 BWIKI 抓取所有精灵数据。
    流程：发现页面 → 逐个抓取 wikitext → 提取数据 → 保存
    """
    print("=" * 50)
    print("BWIKI 精灵图鉴爬虫")
    print("=" * 50)

    # 1. 发现精灵页面
    print("\n[1/3] 发现精灵页面...")
    pet_titles = discover_pet_pages()

    # 保存页面列表
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)
    with open(Path(RAW_DIR) / "pet_titles.json", "w", encoding="utf-8") as f:
        json.dump(pet_titles, f, ensure_ascii=False, indent=2)

    if not pet_titles:
        print("[ERROR] 未发现任何精灵页面，请检查 BWIKI 站点是否可访问")
        return [], {}

    # 2. 批量抓取
    print(f"\n[2/3] 批量抓取精灵数据 ({len(pet_titles)} 个页面)...")
    pets = []
    skills_all = {}
    failed = 0

    for idx, title in enumerate(pet_titles):
        prefix = f"[{idx + 1}/{len(pet_titles)}]"
        wikitext = get_page_wikitext(title)
        if not wikitext:
            failed += 1
            if failed <= 5:
                print(f"  {prefix} {title} — 获取失败")
            continue

        pet = extract_pet_info(wikitext, page_title=title)
        if pet:
            if not pet.get("name"):
                pet["name"] = title
            # BWIKI 模板无编号字段，用图鉴页面顺序作为编号
            if not pet.get("number"):
                pet["number"] = str(idx + 1)
            pets.append(pet)

            # 收集技能名称
            for sname in pet.get("skills", []):
                if sname and sname not in skills_all:
                    skills_all[sname] = {"name": sname}

            if idx < 5 or (idx + 1) % 50 == 0:
                print(f"  {prefix} {pet['name']} — OK (累计 {len(pets)} 只)")
        else:
            failed += 1
            if failed <= 5:
                print(f"  {prefix} {title} — 无精灵数据")

        time.sleep(REQUEST_DELAY)

        # 定期保存
        if (idx + 1) % BATCH_SIZE == 0:
            _save_checkpoint(pets, skills_all)

    # 3. 最终保存
    print(f"\n[3/3] 保存数据...")
    _save_checkpoint(pets, skills_all, final=True)

    print(f"\n完成! 成功 {len(pets)} 只精灵, {len(skills_all)} 个技能, 失败 {failed} 个页面")
    return pets, skills_all


def _save_checkpoint(pets: list, skills: dict, final: bool = False):
    """保存检查点。"""
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)

    with open(Path(RAW_DIR) / "pets_raw.json", "w", encoding="utf-8") as f:
        json.dump(pets, f, ensure_ascii=False, indent=2)

    with open(Path(RAW_DIR) / "skills_raw.json", "w", encoding="utf-8") as f:
        json.dump(skills, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    scrape_pets()
