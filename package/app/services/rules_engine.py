import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.schemas import RuleMapping


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text.lower().strip())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text)


def term_matches(term: str, norm_target: str) -> bool:
    """
    Whole-word match of a (possibly multi-word) term: "bono" matches "pago bono" but not "abono",
    "curso" does not match "recursos". Punctuation inside the term ("c. verde", "apple.com") is literal.
    """
    clean = normalize_text(term.strip().strip("\"'"))
    if not clean:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(clean) + r"(?![a-z0-9])", norm_target) is not None


_TOKEN_RE = re.compile(r"(\"[^\"]+\"|'[^']+'|\bAND\b|\bOR\b|[()])", re.IGNORECASE)


def evaluate_boolean_pattern(pattern: str, target_str: str) -> bool:
    """
    Evaluates `pattern` against `target_str`. Supports OR / AND (case-insensitive), parentheses
    and quoted phrases, e.g. `jumbo OR (uber AND eats) OR "santa isabel"`.
    """
    norm_target = normalize_text(target_str)
    if not pattern or not norm_target:
        return False

    tokens, pos = [], 0
    for match in _TOKEN_RE.finditer(pattern):
        if match.start() > pos and pattern[pos:match.start()].strip():
            tokens.append(pattern[pos:match.start()].strip())
        tokens.append(match.group(0).strip())
        pos = match.end()
    if pattern[pos:].strip():
        tokens.append(pattern[pos:].strip())

    idx = 0

    def peek():
        return tokens[idx] if idx < len(tokens) else None

    def advance():
        nonlocal idx
        idx += 1

    def parse_or():
        value = parse_and()
        while peek() and peek().upper() == "OR":
            advance()
            value = parse_and() or value
        return value

    def parse_and():
        value = parse_primary()
        while peek() and peek().upper() == "AND":
            advance()
            value = parse_primary() and value
        return value

    def parse_primary():
        tok = peek()
        if tok is None:
            return False
        advance()
        if tok == "(":
            value = parse_or()
            if peek() == ")":
                advance()
            return value
        return term_matches(tok, norm_target)

    return parse_or()


@dataclass
class RuleMatchResult:
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    tx_type: Optional[str] = None
    rule_name: Optional[str] = None

    @property
    def matched(self) -> bool:
        return self.rule_name is not None


class RulesEngine:
    @staticmethod
    def match(db: Session, merchant: Optional[str] = "", description: Optional[str] = "",
              sender: Optional[str] = "") -> RuleMatchResult:
        """Returns the first active rule (highest priority, then oldest) that matches."""
        rules = db.query(RuleMapping).filter(RuleMapping.is_active == True).order_by(
            RuleMapping.priority.desc(), RuleMapping.id
        ).all()

        fields = {
            "merchant": normalize_text(merchant),
            "description": normalize_text(description),
            "sender": normalize_text(sender),
        }
        fields["any"] = " ".join(v for v in fields.values() if v)

        for rule in rules:
            target = fields.get(rule.match_field or "any", fields["any"])
            if not target:
                continue
            if rule.is_regex:
                try:
                    matched = re.search(normalize_text(rule.pattern), target) is not None
                except re.error:
                    matched = False
            else:
                matched = evaluate_boolean_pattern(rule.pattern, target)
            if matched:
                return RuleMatchResult(
                    category_id=rule.category_id,
                    account_id=rule.account_id,
                    destination_account_id=rule.destination_account_id,
                    tx_type=rule.tx_type or "expense",
                    rule_name=rule.name or rule.pattern,
                )
        return RuleMatchResult()
