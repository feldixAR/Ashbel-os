"""
CostTracker — in-memory cost accumulation per model per session.

Thread-safe. Accumulates cost from all model_router.call() invocations.
Provides per-model and total cost queries.

Stage 5: in-memory only.
Stage 6 (scheduler): daily reset + DB write added there.

Usage:
    cost_tracker.record(model_key, tokens_in, tokens_out,
                         cost_per_1k_in, cost_per_1k_out)
    cost_tracker.total_today()   # → float USD
    cost_tracker.by_model()      # → dict[str, float]
    cost_tracker.summary()       # → dict with full breakdown
"""

import logging
import threading
import datetime

log = logging.getLogger(__name__)


class CostTracker:

    def __init__(self):
        self._lock   = threading.Lock()
        self._data:  dict = {}   # model_key → {"calls": int, "cost_usd": float,
                                 #               "tokens_in": int, "tokens_out": int}
        self._day    = datetime.date.today().isoformat()

    # ── Recording ─────────────────────────────────────────────────────────────

    def record(
        self,
        model_key:       str,
        tokens_in:       int,
        tokens_out:      int,
        cost_per_1k_in:  float,
        cost_per_1k_out: float,
    ) -> float:
        """
        Record a model call. Returns the cost of this specific call in USD.
        """
        call_cost = (tokens_in  / 1000.0 * cost_per_1k_in +
                     tokens_out / 1000.0 * cost_per_1k_out)

        with self._lock:
            self._check_day_reset()
            entry = self._data.setdefault(model_key, {
                "calls": 0, "cost_usd": 0.0,
                "tokens_in": 0, "tokens_out": 0,
            })
            entry["calls"]      += 1
            entry["cost_usd"]   += call_cost
            entry["tokens_in"]  += tokens_in
            entry["tokens_out"] += tokens_out

        log.debug(f"[CostTracker] {model_key} "
                  f"in={tokens_in} out={tokens_out} cost=${call_cost:.5f}")
        return call_cost

    # ── Queries ───────────────────────────────────────────────────────────────

    def total_today(self) -> float:
        """Total USD cost accumulated in the current day."""
        with self._lock:
            return round(sum(v["cost_usd"] for v in self._data.values()), 6)

    def by_model(self) -> dict:
        """Cost per model_key → float USD."""
        with self._lock:
            return {k: round(v["cost_usd"], 6) for k, v in self._data.items()}

    def summary(self) -> dict:
        """Full breakdown: total, by_model, calls, tokens."""
        with self._lock:
            total = sum(v["cost_usd"]   for v in self._data.values())
            calls = sum(v["calls"]      for v in self._data.values())
            t_in  = sum(v["tokens_in"]  for v in self._data.values())
            t_out = sum(v["tokens_out"] for v in self._data.values())
            models = {
                k: {
                    "calls":      v["calls"],
                    "cost_usd":   round(v["cost_usd"],   6),
                    "tokens_in":  v["tokens_in"],
                    "tokens_out": v["tokens_out"],
                }
                for k, v in self._data.items()
            }
        return {
            "day":          self._day,
            "total_usd":    round(total, 6),
            "total_calls":  calls,
            "tokens_in":    t_in,
            "tokens_out":   t_out,
            "by_model":     models,
        }

    def reset(self) -> None:
        """Clear all accumulated data. Called by scheduler at day boundary."""
        with self._lock:
            self._data.clear()
            self._day = datetime.date.today().isoformat()
        log.info("[CostTracker] reset")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _check_day_reset(self) -> None:
        """Auto-reset if calendar day has changed. Called under lock."""
        today = datetime.date.today().isoformat()
        if today != self._day:
            log.info(f"[CostTracker] day changed {self._day} → {today}, resetting")
            self._data.clear()
            self._day = today


# ── Singleton ─────────────────────────────────────────────────────────────────
cost_tracker = CostTracker()
