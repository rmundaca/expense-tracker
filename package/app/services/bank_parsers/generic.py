import re
from typing import Optional

from app.services.bank_parsers.base import (
    BaseBankParser, ParsedTransaction, clean_html_to_text, detect_account_hint, detect_currency,
    parse_chilean_amount, parse_chilean_date,
)

INCOME_SUBJECT_WORDS = ("abono", "transferencia recibida", "pago recibido", "deposito", "depósito", "recibiste")
INCOME_BODY_PHRASES = ("has recibido", "ha recibido una transferencia", "abono a su cuenta", "abono a tu cuenta")

# "Label: value" pairs that name the counterparty in bank notification tables
MERCHANT_LABEL_RE = re.compile(
    r"(?:comercio|establecimiento|lugar|destinatario|nombre\s+(?:del\s+)?destinatario|a\s+nombre\s+de|empresa)"
    r"\s*[:=]\s*([^\n\r<]{2,60})",
    re.IGNORECASE,
)
PURCHASE_RE = re.compile(r"\bcompra\s+en\s+([^\n\r<,.]{2,50})", re.IGNORECASE)
AMOUNT_LABEL_RE = re.compile(r"(?:monto(?:\s+transferido)?|total(?:\s+cargado)?|valor)\s*[:=]?\s*(\$?\s*[0-9.,]+)", re.IGNORECASE)
DATE_LABEL_RE = re.compile(
    r"(?:fecha(?:\s+y\s+hora)?|hora|realizada\s+el)\s*[:=]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)",
    re.IGNORECASE,
)


class GenericBankParser(BaseBankParser):
    """Parser for banks without a dedicated one; tuned to the common Chilean notification layouts."""
    bank_code = "generic"
    bank_name = "Banco"

    def can_parse(self, sender: str, subject: str) -> bool:
        return True

    def parse(self, subject: str, body_text: str, body_html: str) -> Optional[ParsedTransaction]:
        text = body_text or clean_html_to_text(body_html)
        combined = f"{subject}\n{text}"
        sub_lower, text_lower = subject.lower(), text.lower()

        is_income = any(w in sub_lower for w in INCOME_SUBJECT_WORDS) or any(p in text_lower for p in INCOME_BODY_PHRASES)

        amount = None
        amt_match = AMOUNT_LABEL_RE.search(text)
        if amt_match:
            amount = parse_chilean_amount(amt_match.group(1))
        amount = amount or parse_chilean_amount(text)
        if not amount:
            return None

        merchant = None
        for regex in (MERCHANT_LABEL_RE, PURCHASE_RE):
            match = regex.search(text)
            if match:
                merchant = re.sub(r"\s+", " ", match.group(1)).strip(" -:;,")
                break

        date_match = DATE_LABEL_RE.search(text)
        date_str = parse_chilean_date(date_match.group(1)) if date_match else parse_chilean_date(text)

        return ParsedTransaction(
            amount=amount,
            currency=detect_currency(combined),
            date=date_str or "",
            merchant=merchant or subject.strip()[:60] or "Movimiento bancario",
            description=subject.strip(),
            tx_type="income" if is_income else "expense",
            raw_text=text[:600],
            bank_code=self.bank_code,
            account_hint=detect_account_hint(combined),
        )
