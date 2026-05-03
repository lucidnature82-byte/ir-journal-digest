import json

with open('data/2026-05.json', encoding='utf-8') as f:
    d = json.load(f)

cvir = [a for a in d if a.get('journal') == 'CVIR']
jvir = [a for a in d if a.get('journal') == 'JVIR']

print(f"=== JVIR ===")
print(f"  total:           {len(jvir)}")
print(f"  abstract 있음:   {sum(1 for a in jvir if a.get('abstract'))}")
print(f"  summary 있음:    {sum(1 for a in jvir if a.get('summary'))}")
print(f"  summary null:    {sum(1 for a in jvir if not a.get('summary') and a.get('abstract'))}")

print(f"\n=== CVIR ===")
print(f"  total:           {len(cvir)}")
print(f"  abstract 있음:   {sum(1 for a in cvir if a.get('abstract'))}")
print(f"  summary 있음:    {sum(1 for a in cvir if a.get('summary'))}")
print(f"  summary null:    {sum(1 for a in cvir if not a.get('summary') and a.get('abstract'))}")

print(f"\n=== CVIR 샘플 (abstract 있는데 summary 없는 것) ===")
samples = [a for a in cvir if not a.get('summary') and a.get('abstract')][:3]
for a in samples:
    print(f"  PMID {a.get('pmid')}: abstract len={len(a.get('abstract',''))}, title={(a.get('title') or '')[:60]}")