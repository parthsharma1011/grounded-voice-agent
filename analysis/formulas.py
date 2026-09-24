from __future__ import annotations

import math

from analysis.settings import Z_95


def wilson(k, n, z=Z_95):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - hw), min(1.0, centre + hw))


def binom_cdf(k, n, p):
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k, n, alpha=0.05):
    def solve(f, lo=0.0, hi=1.0):
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) >= alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) <= alpha / 2)
    return lower, upper


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def mcnemar_midp(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    point = math.comb(n, k) / 2**n
    return min(1.0, 2 * tail - point)


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for i, (key, p) in enumerate(items):
        val = min(1.0, (m - i) * p)
        running = max(running, val)
        adj[key] = running
    return adj


def newcombe_paired(a, b, c, d, z=Z_95):
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n, z)
    l2, u2 = wilson(a + c, n, z)
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    phi = 0.0 if den == 0 else (a * d - b * c) / den
    theta = p1 - p2
    delta = math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    eps = math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return theta, theta - delta, theta + eps


def cochran_q(matrix):
    k = len(matrix[0])
    cols = [sum(r[j] for r in matrix) for j in range(k)]
    rows = [sum(r) for r in matrix]
    N = sum(rows)
    num = (k - 1) * (k * sum(c * c for c in cols) - N * N)
    den = k * N - sum(r * r for r in rows)
    q = num / den if den else 0.0
    p = math.exp(-q / 2) if k == 3 else None
    return q, p


def fisher_exact(a, b, c, d):
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d

    def prob(x):
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)

    p_obs = prob(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p_obs * (1 + 1e-9)))


def wilcoxon_signed_rank(diffs):
    d = [x for x in diffs if x != 0]
    n = len(d)
    ranked = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[ranked[j + 1]]) == abs(d[ranked[i]]):
            j += 1
        r = (i + j) / 2 + 1
        for t in range(i, j + 1):
            ranks[ranked[t]] = r
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24
    z = (w_plus - mean) / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2))
    r_effect = abs(z) / math.sqrt(n)
    return {"n": n, "W_plus": w_plus, "z": z, "p": p, "r": r_effect}


def cohens_kappa(pairs):
    n = len(pairs)
    labels = sorted({label for p in pairs for label in p})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum((sum(1 for a, _ in pairs if a == label) / n) * (sum(1 for _, b in pairs if b == label) / n) for label in labels)
    kappa = None if pe >= 1 else (po - pe) / (1 - pe)
    return {"n": n, "labels": labels, "po": po, "pe": pe, "kappa": kappa}


def gwet_ac1(pairs, labels):
    n = len(pairs)
    q = len(labels)
    po = sum(1 for a, b in pairs if a == b) / n
    pis = {label: (sum(1 for a, _ in pairs if a == label) + sum(1 for _, b in pairs if b == label)) / (2 * n) for label in labels}
    pe = sum(p * (1 - p) for p in pis.values()) / (q - 1)
    return (po - pe) / (1 - pe)
