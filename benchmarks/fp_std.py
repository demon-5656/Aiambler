import sys


def fp_kernel(i: int) -> float:
    x = (i % 1009) * 0.0009910802775024777
    y = ((i * 17 + 13) % 997) * 0.0010030090270812437
    for _ in range(8):
        x = x * 1.000000119 + y * 0.999999937 + 0.000001
        y = y * 0.999999911 + x * 0.000000173 + 0.000002
    return x * y + x / (y + 1.0)


n = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000_000
print(f"{sum(fp_kernel(i) for i in range(n)):.10g}")

