import sys
sys.path.insert(0, '.')
from main import _pipeline

raw, eda, schema_violations, mp, alerts = _pipeline()
print('raw shape:', raw.shape)
print('missingness:', mp)
print('schema violations:', len(schema_violations))
print('alerts:', len(alerts))
print(raw.head(2))
