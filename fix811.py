from pathlib import Path

p = Path('/root/400-ai-finder/tests/test_stage811_locked_controlled_live_ux_runner.py')
text = p.read_text(encoding='utf-8')
old = '    "Authorization: Bearer ***\n'
new = '    "Authorization: Bearer ***",\n'
if old not in text:
    raise SystemExit('target fragment not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')
print('fixed canary line')
