import sys

import numpy as np


n = int(sys.argv[1]) if len(sys.argv) > 1 else 256
idx = np.arange(n * n, dtype=np.float64)
a = (((idx * 13 + 7) % 101) * 0.01).reshape(n, n)
b = (((idx * 17 + 3) % 97) * 0.01).reshape(n, n)
c = a @ b
print(f"{float(c.sum()):.10g}")

