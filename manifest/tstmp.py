import os
from datetime import datetime

for root, dirs, _ in os.walk('.'):
    for dn in dirs:
        path = os.path.join(root, dn)
        if '_' in dn:
            continue
        date = datetime.utcfromtimestamp(os.path.getmtime(path)).strftime('%Y%m%d')
        os.rename(path, os.path.join(root, f'{date}_{dn}'))