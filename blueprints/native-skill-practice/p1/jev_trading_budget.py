"""Decision 8/A2 cost bounds, enforced before dispatch and on returned usage.

The 1,000-token planning bound is not a tokenizer. Each native SDK attempt
therefore reserves the vendor's default 64k context ceiling conservatively as
65,536 tokens; danger-zone overrides are unavailable. Unknown attempts keep
that reserve. A successful response over 1,000 input tokens stops its model's
remaining schedule. Retry metadata comes from the adopted SDK transport.
"""
from decimal import Decimal

from jev_trading_scoring import MODELS

PRICE_PER_TOKEN = Decimal("0.042") / 1000000
ASSUMED_INPUT_TOKENS = 1000
CONTEXT_TOKEN_CEILING = 65536
MODEL_TOKEN_CAP = 9_204_000
TOTAL_TOKEN_CAP = 18_408_000
MODEL_USD_CAP = Decimal("0.386568")
TOTAL_USD_CAP = Decimal("0.773136")


class JevBudget:
    def __init__(self, planned_calls, *, max_attempts):
        if set(planned_calls) != set(MODELS) or any(type(n) is not int or n < 0 for n in planned_calls.values()):
            raise ValueError("Jev preflight requires both model schedules")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
            raise ValueError("Jev retry bound must match the adopted SDK")
        estimates = {model: n * ASSUMED_INPUT_TOKENS for model, n in planned_calls.items()}
        if any(n > MODEL_TOKEN_CAP or n * PRICE_PER_TOKEN > MODEL_USD_CAP for n in estimates.values()) or \
                sum(estimates.values()) > TOTAL_TOKEN_CAP or sum(estimates.values()) * PRICE_PER_TOKEN > TOTAL_USD_CAP:
            raise ValueError("Jev preflight exceeds the token/USD bound")
        self.max_attempts = max_attempts
        self.planned_calls = dict(planned_calls)
        self.known = dict.fromkeys(MODELS, 0)
        self.held = dict.fromkeys(MODELS, 0)
        self.active = dict.fromkeys(MODELS, 0)
        self.stopped = dict.fromkeys(MODELS, False)
        self.unknown_attempts = dict.fromkeys(MODELS, 0)
        self.bounded = dict.fromkeys(MODELS, True)
        self.global_stop = False

    def reserve(self, model):
        amount = CONTEXT_TOKEN_CEILING * self.max_attempts
        own = self.known[model] + self.held[model] + amount
        total = sum(self.known.values()) + sum(self.held.values()) + amount
        if self.global_stop or total > TOTAL_TOKEN_CAP or total * PRICE_PER_TOKEN > TOTAL_USD_CAP:
            self.global_stop = True
            return False
        if self.stopped[model] or own > MODEL_TOKEN_CAP or own * PRICE_PER_TOKEN > MODEL_USD_CAP:
            self.stopped[model] = True
            return False
        self.held[model] += amount
        self.active[model] = amount
        return True

    def unknown(self, model):
        if self.active[model]:
            self.unknown_attempts[model] += self.max_attempts
            self.active[model] = 0

    def record(self, model, input_tokens, retries):
        if not self.active[model]:
            raise ValueError("Jev usage requires a pre-dispatch reservation")
        if type(input_tokens) is int and input_tokens > CONTEXT_TOKEN_CEILING:
            # A response that contradicts the vendor ceiling cannot establish
            # bounded spend. Stop this model and retain the unresolved reserve.
            self.bounded[model] = False
            self.stopped[model] = True
            self.unknown(model)
            return "TOKEN_BOUND_STOP"
        if type(input_tokens) is not int or input_tokens < 0 or \
                type(retries) is not int or not 0 <= retries < self.max_attempts:
            self.unknown(model)
            return "UNKNOWN_USAGE"
        self.held[model] -= self.active[model]
        self.active[model] = 0
        self.known[model] += input_tokens
        # A successful final attempt does not establish whether earlier
        # retried errors were billed. Keep their conservative upper bounds.
        self.held[model] += retries * CONTEXT_TOKEN_CEILING
        self.unknown_attempts[model] += retries
        if input_tokens > ASSUMED_INPUT_TOKENS:
            self.stopped[model] = True
            return "TOKEN_BOUND_STOP"
        return "VALID"

    def snapshot(self):
        models = {model: {"known_input_tokens": self.known[model], "reserved_input_tokens": self.held[model],
            "known_usd": str(self.known[model] * PRICE_PER_TOKEN),
            "upper_bound_usd": str((self.known[model] + self.held[model]) * PRICE_PER_TOKEN) if self.bounded[model] else None,
            "within_vendor_ceiling": self.bounded[model],
            "unknown_attempts": self.unknown_attempts[model], "stopped": self.stopped[model],
            "cap_usd": str(MODEL_USD_CAP)} for model in MODELS}
        known, held = sum(self.known.values()), sum(self.held.values())
        return {"models": models, "known_input_tokens": known, "reserved_input_tokens": held,
            "usd": str(known * PRICE_PER_TOKEN) if not held else None,
            "known_usd": str(known * PRICE_PER_TOKEN),
            "upper_bound_usd": str((known + held) * PRICE_PER_TOKEN) if all(self.bounded.values()) else None,
            "cap_usd": str(TOTAL_TOKEN_CAP * PRICE_PER_TOKEN), "global_stop": self.global_stop}
