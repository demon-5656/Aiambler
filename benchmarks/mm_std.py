import sys


n = int(sys.argv[1]) if len(sys.argv) > 1 else 128
a = [((i * 13 + 7) % 101) * 0.01 for i in range(n * n)]
b = [((i * 17 + 3) % 97) * 0.01 for i in range(n * n)]
c = [0.0] * (n * n)

for i in range(n):
    row = i * n
    for k in range(n):
        aik = a[row + k]
        brow = k * n
        for j in range(n):
            c[row + j] += aik * b[brow + j]

print(f"{sum(c):.10g}")

