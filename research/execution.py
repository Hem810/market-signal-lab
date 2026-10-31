"""Synthetic completed-bar execution experiments, no daily-bar path inference."""


def schedule(quantity, policy, profile=(0.2, 0.3, 0.5)):
    if policy == "immediate":
        return [quantity, 0, 0]
    w = [1 / 3] * 3 if policy == "twap" else profile
    a = [int(quantity * x) for x in w]
    a[-1] += quantity - sum(a)
    return a


def execute(quantity, policy, bars, arrival=100.0, participation=0.1):
    slices = schedule(quantity, policy)
    residual = 0
    fills = []
    for i, (price, volume) in enumerate(bars):
        wanted = slices[i] + residual
        filled = min(wanted, int(volume * participation))
        residual = wanted - filled
        fills.append((i, filled, price))  # only current completed bar observed
    cost = sum(q * p * 0.0006 for _, q, p in fills)
    return dict(
        policy=policy,
        filled=sum(q for _, q, p in fills),
        residual=residual,
        cost=cost,
        shortfall=sum(q * (p - arrival) for _, q, p in fills) + cost,
        fills=fills,
    )
