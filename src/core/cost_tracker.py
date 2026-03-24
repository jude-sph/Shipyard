import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import MODEL_PRICING
from src.core.models.core import CostEntry, CostSummary

logger = logging.getLogger(__name__)


class CostTracker:
    def __init__(self, model: str, cost_log_path: Path | None = None):
        self.model = model
        self.cost_log_path = cost_log_path
        self._entries: list[CostEntry] = []
        pricing = MODEL_PRICING.get(model, {})
        self._input_rate = pricing.get("input_per_mtok", 0.0)
        self._output_rate = pricing.get("output_per_mtok", 0.0)
        if not pricing:
            logger.warning(f"No pricing data for model '{model}', cost will show $0.00")

    def record(
        self,
        call_type: str,
        stage: str,
        input_tokens: int,
        output_tokens: int,
        actual_cost: float | None = None,
        level: int = 0,
    ) -> CostEntry:
        if actual_cost is not None:
            cost = actual_cost
        else:
            cost = (input_tokens * self._input_rate + output_tokens * self._output_rate) / 1_000_000
        entry = CostEntry(
            call_type=call_type,
            stage=stage,
            level=level,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
        self._entries.append(entry)
        source = "actual" if actual_cost is not None else "estimated"
        logger.debug(
            f"API call: {call_type} [{stage}] level={level} | "
            f"{input_tokens} in / {output_tokens} out | ${cost:.4f} ({source})"
        )
        return entry

    def get_summary(self) -> CostSummary:
        return CostSummary(breakdown=list(self._entries))

    def format_cost_line(self) -> str:
        s = self.get_summary()
        calls = s.api_calls
        return (
            f"Cost: {calls} API call{'s' if calls != 1 else ''} | "
            f"{s.total_input_tokens:,} input tokens | "
            f"{s.total_output_tokens:,} output tokens | "
            f"${s.total_cost_usd:.4f}"
        )

    def flush_log(
        self,
        run_type: str,
        source_file: str,
        mode: str,
        layers: list[str],
    ) -> None:
        """Append a JSONL entry to cost_log_path with run metadata and per-stage breakdown."""
        if self.cost_log_path is None:
            return
        summary = self.get_summary()
        stage_breakdown: dict[str, dict] = {}
        for entry in self._entries:
            if entry.stage not in stage_breakdown:
                stage_breakdown[entry.stage] = {
                    "api_calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                }
            stage_breakdown[entry.stage]["api_calls"] += 1
            stage_breakdown[entry.stage]["input_tokens"] += entry.input_tokens
            stage_breakdown[entry.stage]["output_tokens"] += entry.output_tokens
            stage_breakdown[entry.stage]["cost_usd"] += entry.cost_usd

        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": run_type,
            "source_file": source_file,
            "mode": mode,
            "layers": layers,
            "model": self.model,
            "totals": {
                "api_calls": summary.api_calls,
                "input_tokens": summary.total_input_tokens,
                "output_tokens": summary.total_output_tokens,
                "cost_usd": summary.total_cost_usd,
            },
            "stages": stage_breakdown,
        }
        self.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cost_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_record) + "\n")

    def reset(self) -> None:
        self._entries.clear()
