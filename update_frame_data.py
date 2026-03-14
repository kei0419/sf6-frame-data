"""
SF6 Frame Data 更新スクリプト
CAPCOM公式サイトから全キャラのフレームデータを取得し、official_data.jsを更新する

使用方法:
  python update_frame_data.py

依存パッケージ:
  pip install requests beautifulsoup4
"""

import io
import sys

# Windows console encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import time
import os
import re
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("必要なパッケージをインストールしてください:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

# ── 設定 ──
BASE_URL = "https://www.streetfighter.com/6/ja-jp/character/{char_id}/frame"
OUTPUT_FILE = Path(__file__).parent / "official_data.js"
SW_FILE = Path(__file__).parent / "sw.js"

# キャラクターIDリスト（CAPCOM公式サイトのURLスラッグ）
CHARACTERS = [
    "ryu", "luke", "jamie", "chunli", "guile", "kimberly", "juri", "ken",
    "blanka", "dhalsim", "ehonda", "deejay", "manon", "marisa",
    "jp", "zangief", "lily", "cammy", "rashid", "aki", "ed", "gouki_akuma",
    "vega_mbison", "terry", "mai", "elena", "sagat", "cviper",
]

# URLスラッグ → official_data.jsでのキー名マッピング
# PWAアプリ側の characterNames と合わせる
KEY_MAP = {
    "gouki_akuma": "akuma",
    "vega_mbison": "m_bison",
}

# ── CSSクラスからカラム名へのマッピング ──
COLUMN_MAP = {
    "frame_startup_frame": "startup",
    "frame_active_frame": "active",
    "frame_recovery_frame": "recovery",
    "frame_hit_frame": "hit",
    "frame_block_frame": "block",
    "frame_cancel": "cancel",
    "frame_damage": "damage",
    "frame_combo_correct": "scaling",
    "frame_drive_gauge_gain_hit": "d_hit",
    "frame_drive_gauge_lose_dguard": "d_guard",
    "frame_drive_gauge_lose_punish": "d_pc",
    "frame_sa_gauge_gain": "sa_gain",
    "frame_attribute": "attr",
    "frame_note": "notes",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.streetfighter.com/6/ja-jp",
    "Connection": "keep-alive",
}


def get_text_clean(td):
    """tdからテキストを取得してクリーンアップ"""
    # <li> 要素がある場合、カンマ区切りで結合
    lis = td.find_all("li")
    if lis:
        texts = [li.get_text(strip=True) for li in lis if li.get_text(strip=True)]
        return "、 ".join(texts) if texts else ""
    return td.get_text(strip=True)


def get_column_key(td):
    """tdのクラス名からカラムキーを推定"""
    classes = td.get("class", [])
    for cls in classes:
        for prefix, key in COLUMN_MAP.items():
            if cls.startswith(prefix):
                return key
    return None


def parse_move_name(td):
    """技名セルから技名とコマンドを取得"""
    name_span = td.find("span", class_=lambda c: c and "arts" in c)
    name = name_span.get_text(strip=True) if name_span else td.get_text(strip=True)

    cmd_p = td.find("p", class_=lambda c: c and "classic" in c)
    cmd = ""
    if cmd_p:
        # imgタグのalt属性からコマンド入力を再現
        parts = []
        for child in cmd_p.children:
            if hasattr(child, "name") and child.name == "img":
                alt = child.get("alt", "")
                src = child.get("src", "")
                if "key-d.png" in src: parts.append("2+")
                elif "key-dr.png" in src: parts.append("")  # 236の一部
                elif "key-dl.png" in src: parts.append("")  # 214の一部
                elif "key-r.png" in src: parts.append("6+")
                elif "key-l.png" in src: parts.append("4+")
                elif "key-u.png" in src: parts.append("8+")
                elif "key-plus.png" in src: parts.append("")
                elif "key-lc" in src: parts.append("[key-lc]")
                elif "key-dc" in src: parts.append("[key-dc]")
                elif "arrow_3" in src: parts.append(">")
                elif "punch_l" in src: parts.append("弱P")
                elif "punch_m" in src: parts.append("中P")
                elif "punch_h" in src: parts.append("強P")
                elif "kick_l" in src: parts.append("弱K")
                elif "kick_m" in src: parts.append("中K")
                elif "kick_h" in src: parts.append("強K")
                elif "punch.png" in src: parts.append("P P")
                elif "kick.png" in src: parts.append("K K")
                elif alt: parts.append(alt)
            elif hasattr(child, "string") and child.string:
                t = child.string.strip()
                if t: parts.append(t)
            elif isinstance(child, str):
                t = child.strip()
                if t: parts.append(t)
        cmd = " ".join(p for p in parts if p)
        cmd = re.sub(r'\s+', ' ', cmd).strip()

    return name, cmd


def get_move_type(row, current_type):
    """行が見出し行であればタイプ名を返す、データ行であればNone"""
    heading_td = row.find("td", attrs={"colspan": True})
    if heading_td:
        span = heading_td.find("span")
        return span.get_text(strip=True) if span else heading_td.get_text(strip=True)
    return None


def scrape_character(session, char_id):
    """1キャラのフレームデータをスクレイピング"""
    url = BASE_URL.format(char_id=char_id)
    print(f"  取得中: {char_id}...", end=" ", flush=True)

    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ エラー: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print("❌ テーブルが見つかりません")
        return None

    tbody = table.find("tbody")
    if not tbody:
        print("❌ tbodyが見つかりません")
        return None

    moves = []
    current_type = "通常技"

    for row in tbody.find_all("tr"):
        # 見出し行チェック
        heading = get_move_type(row, current_type)
        if heading:
            current_type = heading
            continue

        tds = row.find_all("td")
        if len(tds) < 5:
            continue

        # 最初のtdは技名
        name_td = tds[0]
        name, cmd_c = parse_move_name(name_td)
        if not name:
            continue

        move = {
            "name": name,
            "cmd_c": cmd_c,
            "type": current_type,
        }

        # 残りのカラムを取得
        for td in tds[1:]:
            key = get_column_key(td)
            if key:
                val = get_text_clean(td)
                if val:
                    move[key] = val

        moves.append(move)

    print(f"✅ {len(moves)}技")
    return moves


def update_sw_cache_version():
    """Service Workerのキャッシュバージョンを更新"""
    if not SW_FILE.exists():
        return
    content = SW_FILE.read_text(encoding="utf-8")
    # sf6-frame-v1 → sf6-frame-v2 のようにインクリメント
    match = re.search(r"sf6-frame-v(\d+)", content)
    if match:
        old_ver = int(match.group(1))
        new_ver = old_ver + 1
        content = content.replace(f"sf6-frame-v{old_ver}", f"sf6-frame-v{new_ver}")
        SW_FILE.write_text(content, encoding="utf-8")
        print(f"\n✅ Service Worker キャッシュバージョン更新: v{old_ver} → v{new_ver}")


def main():
    print("=" * 50)
    print("SF6 Frame Data 更新スクリプト")
    print("CAPCOM公式サイトからフレームデータを取得します")
    print("=" * 50)

    session = requests.Session()

    all_data = {}
    success = 0
    fail = 0

    for char_id in CHARACTERS:
        moves = scrape_character(session, char_id)
        if moves:
            data_key = KEY_MAP.get(char_id, char_id)
            all_data[data_key + "_frame"] = moves
            success += 1
        else:
            fail += 1
        time.sleep(1)  # サーバー負荷軽減

    print(f"\n取得結果: {success}キャラ成功 / {fail}キャラ失敗")

    if success == 0:
        print("❌ データが取得できませんでした")
        print("   CAPCOM公式がアクセスを制限している可能性があります")
        print("   ブラウザ手動取得モードを使ってください:")
        print("   python update_frame_data.py --manual")
        sys.exit(1)

    # official_data.js として書き出し
    js_content = "window.officialData = " + json.dumps(all_data, ensure_ascii=False)
    OUTPUT_FILE.write_text(js_content, encoding="utf-8")
    size_kb = len(js_content.encode("utf-8")) / 1024
    print(f"\n✅ {OUTPUT_FILE.name} を更新しました ({size_kb:.0f} KB)")

    # Service Workerのキャッシュバージョン更新
    update_sw_cache_version()

    print("\n🎉 完了！GitHub PagesにpushすればiPhoneにも反映されます")


if __name__ == "__main__":
    main()
