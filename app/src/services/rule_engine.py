from datetime import timedelta
from typing import List, Optional, Tuple
import re

from src.models import AlertSeverity, RuleAlert, RuleDefinition, TelemetryPayload
from src.services.repository import get_telemetry_history, add_alert, get_rules as get_rules_from_db

COMPARATORS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class ZenRuleEngine:
    @staticmethod
    def parse_expression(expression: str) -> Tuple[str, str, float, Optional[int]]:
        expression = expression.strip().lower()
        duration = None
        if " for " in expression:
            condition_part, duration_part = expression.split(" for ", 1)
            m = re.match(r"(\d+)\s*minute[s]?", duration_part.strip())
            if m:
                duration = int(m.group(1))
            else:
                raise ValueError(f"Unsupported duration expression: {duration_part}")
        else:
            condition_part = expression

        m = re.match(r"^(?P<field>[a-z_]+)\s*(?P<op>>=|<=|>|<|==|!=)\s*(?P<value>[0-9]+(?:\.[0-9]+)?)$", condition_part.strip())
        if not m:
            raise ValueError(f"Unsupported rule expression: {expression}")

        field = m.group("field")
        op = m.group("op")
        value = float(m.group("value"))
        return field, op, value, duration

    @classmethod
    def evaluate_rule(cls, rule: RuleDefinition, payload: TelemetryPayload) -> Optional[RuleAlert]:
        field, comparator, threshold, duration = cls.parse_expression(rule.expression)

        if not hasattr(payload, field):
            return None

        reading = getattr(payload, field)
        if reading is None:
            return None

        if duration is None:
            match_result = COMPARATORS[comparator](reading, threshold)
        else:
            history = get_telemetry_history(payload.patient_id)
            window_start = payload.timestamp - timedelta(minutes=duration)
            relevant_history = [h for h in history if h.timestamp >= window_start and getattr(h, field, None) is not None]

            if not relevant_history:
                return None

            match_result = all(
                COMPARATORS[comparator](getattr(h, field), threshold)
                for h in relevant_history + [payload]
            )

        if not match_result:
            return None

        return RuleAlert(
            alert_id=f"{rule.rule_id}_{payload.patient_id}_{int(payload.timestamp.timestamp())}",
            patient_id=payload.patient_id,
            observed_at=payload.timestamp,
            rule=rule.rule_id,
            severity=rule.severity,
            message=f"Rule {rule.name} triggered: {rule.expression} (current={reading})",
            tags=[rule.rule_id],
        )

    @classmethod
    def evaluate_rules(cls, payload: TelemetryPayload) -> List[RuleAlert]:
        rules = get_rules_from_db()
        alerts: List[RuleAlert] = []
        for rule in rules:
            try:
                alert = cls.evaluate_rule(rule, payload)
                if alert:
                    alerts.append(alert)
                    add_alert(alert)
            except ValueError:
                continue
        return alerts

    @staticmethod
    def get_rules() -> List[RuleDefinition]:
        return get_rules_from_db()


def evaluate_rules(payload: TelemetryPayload) -> List[RuleAlert]:
    return ZenRuleEngine.evaluate_rules(payload)


def get_rules() -> List[RuleDefinition]:
    return ZenRuleEngine.get_rules()
