import json,subprocess,re,os
OV={}  # fresh
for it in range(12):
    json.dump(OV,open('sizes_nov.json','w'))
    subprocess.run(['python3','build_nov.py'],check=True,capture_output=True)
    out=subprocess.run(['python3','check_cards.py','cards_nov.json','render_nov'],capture_output=True,text=True).stdout
    bad=[l for l in out.splitlines() if '!!' in l]
    hb=[l.split()[0] for l in bad if re.search(r'бот×h|край×h|заголовок у края',l)]
    if not hb: break
    src=open('build_nov.py').read()
    for n in hb:
        if n not in OV:
            OV[n]=float(re.search(r'\("'+n+r'", "[a-z]+", "[^"]*", [^,]*?"[^"]*", ([\d.]+)',src).group(1))
        OV[n]=round(OV[n]-0.75,2)
print(json.dumps(OV,ensure_ascii=False)); print('\n'.join(bad))
