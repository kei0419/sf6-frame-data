import json
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('official_data.js', 'r', encoding='utf-8') as f:
    content = f.read()

json_str = content[content.find('{'):]
data = json.loads(json_str)

ed_moves = data.get('ed_frame', [])
for move in ed_moves:
    name = move.get('name', '')
    if 'P' in name or 'K' in name or 'キルステップ' in name:
        print(f"{name}: 発生{move.get('startup')}, 持続{move.get('active')}, 硬直{move.get('recovery')}, ガード{move.get('block')}")
