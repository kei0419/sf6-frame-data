import json
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('official_data.js', 'r', encoding='utf-8') as f:
    content = f.read()

json_str = content[content.find('{'):]
data = json.loads(json_str)

def get_blockstun(move):
    try:
        b = int(move.get('block', 0))
        r = int(re.search(r'\d+', move.get('recovery', '0')).group())
        a = move.get('active', '')
        if '-' in a:
            parts = a.split('-')
            a_frames = int(re.search(r'\d+', parts[1]).group()) - int(re.search(r'\d+', parts[0]).group()) + 1
        else:
            a_frames = int(re.search(r'\d+', a).group()) if a else 1
        return b + r + (a_frames - 1)
    except:
        return 0

ed_moves = data.get('ed_frame', [])
ed_target_names = ['立ち中P', '立ち中K', '立ち強P', 'しゃがみ強K']
ed_data = {}

for move in ed_moves:
    name = move.get('name', '')
    for t_name in ed_target_names:
        if t_name in name and 'ジャンプ' not in name:
            block_adv = move.get('block', '')
            try:
                b_adv_int = int(block_adv)
            except:
                b_adv_int = 0
            bstun = get_blockstun(move)
            cancel_adv = bstun - 31
            ed_data[t_name] = {'block_adv': b_adv_int, 'cancel_adv': cancel_adv}

def calc_total(move):
    startup = move.get('startup', '')
    active = move.get('active', '')
    recovery = move.get('recovery', '')
    m = re.search(r'全体\s*(\d+)', recovery)
    if m: return int(m.group(1))
    try:
        s_match = re.search(r'\d+', startup)
        r_match = re.search(r'\d+', recovery)
        if not s_match or not r_match: return 0
        s = int(s_match.group())
        r = int(r_match.group())
        a = 0
        if '-' in active:
            parts = active.split('-')
            s_act_match = re.search(r'\d+', parts[0])
            e_act_match = re.search(r'\d+', parts[1])
            if s_act_match and e_act_match:
                a = int(e_act_match.group()) - int(s_act_match.group()) + 1
        else:
            a_match = re.search(r'\d+', active)
            if a_match: a = int(a_match.group())
        if s > 0 and a > 0 and r > 0: return (s - 1) + a + r
        return 0
    except: return 0

results = {}
for char_key, moves in data.items():
    char_name = char_key.replace('_frame', '').capitalize()
    char_moves = []
    for move in moves:
        name = move.get('name', '')
        type_ = move.get('type', '')
        if type_ == '通常技' and ('中P' in name or '中K' in name) and 'ジャンプ' not in name:
            total = calc_total(move)
            if total >= 24:
                char_moves.append({'name': name, 'total': total})
    if char_moves:
        results[char_name] = char_moves

# Create Markdown grouped by Character
with open('ed_killstep_matrix_by_char.md', 'w', encoding='utf-8') as f:
    f.write("---\n")
    f.write("tags: [sf6, ed, killstep, tactic]\n")
    f.write("---\n\n")
    f.write("# キャラ別 エドのキルステ狩りマトリクス\n\n")
    f.write("相手の全体24F以上の中攻撃をキルステップで空振らせた場合のエド側の有利フレーム一覧です。\n\n")
    
    for char, opp_moves in results.items():
        f.write(f"## {char}\n")
        f.write("| エドの技 | 相手の空振り技 (全体F) | 打ち切りF | キルステF | エド有利F |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        for t_name in ed_target_names:
            if t_name not in ed_data:
                continue
            ed_b = ed_data[t_name]['block_adv']
            ed_c = ed_data[t_name]['cancel_adv']
            
            for i, m in enumerate(opp_moves):
                adv = ed_c + m['total']
                adv_str = f"+{adv}F" if adv >= 0 else f"{adv}F"
                
                # 最初だけ技名を表示し、それ以降は空白にする
                display_t_name = t_name if i == 0 else " "
                
                f.write(f"| {display_t_name} | {m['name']} ({m['total']}F) | {ed_b}F | {ed_c}F | **{adv_str}** |\n")
        f.write("\n---\n\n")
