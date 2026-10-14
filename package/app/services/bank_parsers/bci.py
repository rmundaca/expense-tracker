import re
from typing import Optional
from app.services.bank_parsers.base import (
    BaseBankParser, ParsedTransaction, clean_html_to_text, detect_account_hint, detect_currency,
    parse_chilean_amount, parse_chilean_date
)

class BciParser(BaseBankParser):
    bank_code = "bci"
    bank_name = "Banco BCI"

    def can_parse(self, sender: str, subject: str) -> bool:
        s = sender.lower()
        sub = subject.lower()
        return ("bci.cl" in s or "bci" in sub or "banco bci" in s or "banco bci" in sub)

    def parse(self, subject: str, body_text: str, body_html: str) -> Optional[ParsedTransaction]:
        text = body_text or clean_html_to_text(body_html)
        sub_lower = subject.lower()
        text_lower = text.lower()

        # 1. Determine transaction type (income vs expense)
        is_income = (
            any(w in sub_lower for w in ["abono", "transferencia recibida", "recibido", "recibiste"]) or
            any(w in text_lower for w in ["has recibido", "monto recibido", "abono a su cuenta", "abono a tu cuenta", "transferencia recibida"])
        )
        tx_type = "income" if is_income else "expense"

        # 2. Extract amount
        amount = None
        amt_match = re.search(r"(?:monto\s+recibido|monto\s+transferido|monto|valor|total)\s*[:=]?\s*(\$?\s*[0-9\.,]+)", text, re.IGNORECASE)
        if amt_match:
            amount = parse_chilean_amount(amt_match.group(1))
        if not amount:
            amount = parse_chilean_amount(text)
        if not amount:
            return None

        # 3. Extract Merchant / Sender / Recipient
        merchant = None
        if is_income:
            # Pattern: "Has recibido una transferencia de fondos de María González Rojas hacia tu cuenta..."
            from_match = re.search(
                r"(?:transferencia(?:\s+de\s+fondos)?\s+de|recibido\s+(?:una\s+)?transferencia(?:\s+de\s+fondos)?\s+de)\s+([^\n\r<,.;]+?)(?:\s+hacia|\s+a\s+tu|\s+el|\s+por|$)",
                text,
                re.IGNORECASE
            )
            if from_match:
                cand = from_match.group(1).strip()
                if len(cand) >= 2 and cand.lower() not in ["fondos", "cuenta", "bci"]:
                    merchant = cand

        if not merchant:
            # Sent transfer: "transferencia de fondos a [Nombre]"
            to_match = re.search(
                r"transferencia(?:\s+de\s+fondos)?\s+a\s+([^\n\r,.;]+?)(?:,\s*el\s+d[ií]a|\s+el\s+d[ií]a|\s+desde|\s+hacia|$)",
                text,
                re.IGNORECASE
            )
            if to_match:
                cand = to_match.group(1).strip()
                if len(cand) >= 2 and cand.lower() not in ["un tercero", "terceros", "otra cuenta"]:
                    merchant = cand

        if not merchant:
            # Table key-value: e.g. "Destinatario: ...", "Comercio: ...", "A nombre de: ..."
            merch_match = re.search(r"(?:destinatario|nombre\s+destinatario|remitente|comercio|a\s+nombre\s+de)\s*[:=]\s*([^\n\r<]{2,60})", text, re.IGNORECASE)
            if merch_match:
                merchant = merch_match.group(1).strip()

        if not merchant:
            # Purchase: "compra en [Comercio]"
            compra_match = re.search(r"(?:compra|pago)\s+en\s+([^\n\r<,.]{2,50})", text, re.IGNORECASE)
            if compra_match:
                merchant = compra_match.group(1).strip()

        if not merchant:
            merchant = "Banco BCI"

        merchant = re.sub(r"\s+", " ", merchant).strip(" -:;,")

        # 4. Extract Date
        date_match = re.search(r"(?:fecha\s+de\s+la\s+transferencia|fecha|hora)\s*[:=]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", text, re.IGNORECASE)
        date_str = parse_chilean_date(date_match.group(1)) if date_match else parse_chilean_date(text)

        # 5. Extract Message/Concept if present in table
        msg_match = re.search(r"mensaje\s*[:=]\s*([^\n\r<]{2,80})", text, re.IGNORECASE)
        comment = msg_match.group(1).strip() if msg_match else ""

        # Build clean description
        if is_income:
            desc = f"Transferencia recibida de {merchant}"
            if comment:
                desc += f" - {comment}"
        else:
            desc = f"{subject} - {merchant}" if merchant != "Banco BCI" else subject
            if comment:
                desc += f" - {comment}"

        currency = detect_currency(f"{subject}\n{text}")
        account_hint = detect_account_hint(f"{subject}\n{text}")

        return ParsedTransaction(
            amount=amount,
            currency=currency,
            date=date_str,
            merchant=merchant,
            description=desc,
            tx_type=tx_type,
            raw_text=text[:600],
            bank_code=self.bank_code,
            account_hint=account_hint
        )
