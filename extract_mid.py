import json
import re

with open('official_data.js', 'r', encoding='utf-8') as f:
    content = f.read()

json_str = content[content.find('{'):]
data = json.loads(json_str)

def calc_total(move):
    startup = move.get('startup', '')
    active = move.get('active', '')
    recovery = move.get('recovery', '')
    
    m = re.search(r'全体\s*(\d+)', recovery)
    if m:
        return int(m.group(1))
        
    try:
        s_match = re.search(r'\d+', startup)
        r_match = re.search(r'\d+', recovery)
        if not s_match or not r_match:
            return ''
            
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
            if a_match:
                a = int(a_match.group())
            
        if s > 0 and a > 0 and r > 0:
            return (s - 1) + a + r
        return ''
    except Exception as e:
        return f'Err'

results = {}
for char_key, moves in data.items():
    char_name = char_key.replace('_frame', '').capitalize()
    char_moves = []
    for move in moves:
        name = move.get('name', '')
        type_ = move.get('type', '')
        
        if type_ == '通常技' and ('中P' in name or '中K' in name) and 'ジャンプ' not in name:
            total = calc_total(move)
            char_moves.append(f"- **{name}**: 全体 {total}F (発生{move.get('startup')}, 持続{move.get('active')}, 硬直{move.get('recovery')})")
    
    if char_moves:
        results[char_name] = char_moves

with open('mid_frames_direct.md', 'w', encoding='utf-8') as f:
    for char, moves in results.items():
        f.write(f'### {char}\n')
        for m in moves:
            f.write(m + '\n')
