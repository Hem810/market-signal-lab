"""Small independent one-symbol cash-account oracle, fixtures only."""

import math


def reference(prices, weights, capital=1000, fee=0, slip=0):
    cash = capital
    shares = 0
    out = []
    for (op, close), weight in zip(prices, weights):
        desired = shares if weight is None else math.floor(weight * (cash + shares * op) / op)
        delta = desired - shares
        if delta > 0:
            delta = min(delta, math.floor(cash / (op * (1 + fee + slip))))
        cash -= delta * op + abs(delta) * op * (fee + slip)
        shares += delta
        out.append(cash + shares * close)
    return out
