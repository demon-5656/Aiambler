import re

total = 0.0
with open("benchmarks/prices.txt", encoding="utf-8") as fh:
    for line in fh:
        if "price" not in line:
            continue
        for item in re.findall(r"[-+]?\d+(?:\.\d+)?", line):
            total += float(item)
print(int(total) if total == int(total) else total)

