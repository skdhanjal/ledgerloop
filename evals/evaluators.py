def extraction_exact(pred: dict, truth: dict) -> dict:
    """Field-level exact match on the fields that matter."""
    fields = ["vendor", "invoice_no", "po_number", "total", "subtotal", "tax"]
    hits = {f: pred.get(f) == truth.get(f) for f in fields}
    return {"score": sum(hits.values()) / len(fields), "per_field": hits}


def decision_correct(pred: str, truth: str) -> dict:
    return {"score": float(pred == truth), "predicted": pred, "expected": truth}


def exception_detection(pred: list[str], truth: list[str]) -> dict:
    """Set comparison - precision and recall, not a single number.

    They fail differently: a missed exception is a wrong payment, a spurious
    one is wasted analyst time. Averaging them hides which is happening.
    """
    p, t = set(pred), set(truth)
    tp = len(p & t)
    return {
        "precision": tp / len(p) if p else 1.0,
        "recall": tp / len(t) if t else 1.0,
        "missed": sorted(t - p),
        "spurious": sorted(p - t),
    }


def evidence_grounded(verdict: dict, trajectory: list[dict]) -> dict:
    """Rule-based hallucination check - no model needed.

    Every figure quoted in the root cause must appear in some tool result.
    This catches the most common failure (confident unsupported claims) with
    a regex and a set difference.
    """
    import re
    quoted = set(re.findall(r"\d+\.\d{2}", verdict.get("root_cause", "")))
    observed = set()
    for step in trajectory:
        observed |= set(re.findall(r"\d+\.\d{2}", str(step.get("result", ""))))

    unsupported = quoted - observed
    return {"score": 0.0 if unsupported else 1.0,
            "unsupported_figures": sorted(unsupported)}


def trajectory_efficiency(trajectory: list[dict], expected_tools: set) -> dict:
    """Did it take a sensible path, not just reach a good answer?"""
    used = [s["tool"] for s in trajectory]
    return {
        "necessary_tools_used": expected_tools <= set(used),
        "redundant_calls": len(used) - len(set(used)),
        "total_calls": len(used),
    }