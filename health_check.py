from pathlib import Path
import py_compile
import sys

root = Path(__file__).resolve().parents[1]
errors = []
for py in root.rglob('*.py'):
    if '.venv' in py.parts or '__pycache__' in py.parts:
        continue
    try:
        py_compile.compile(str(py), doraise=True)
        print('[OK]', py.relative_to(root))
    except Exception as e:
        errors.append((py, e))
        print('[ERROR]', py.relative_to(root), e)
if errors:
    sys.exit(1)
print('\nAll Python files passed syntax check.')
