import re
from typing import Optional
from app.services.bank_parsers.base import (
    _AMOUNT_NUMBER, BaseBankParser, ParsedTransaction, _clean_chilean_number, clean_html_to_text,
    detect_account_hint, detect_currency, parse_chilean_amount, parse_chilean_date, is_non_transactional_email
)

# Labelled amounts that win over the first amount in the text: "Utilizado: USD$243,00 ... Monto pagado: USD$136,10"
# is a payment of 136,10, and "Empresa: Gas Sur Monto: $67.987 ... Total: $88.987" a payment of 88.987.
_PAID_FOREIGN_RE = re.compile(r"monto\s+pagado\s*:\s*(?:US\$|USD\s*\$?|U\$S)\s*" + _AMOUNT_NUMBER, re.IGNORECASE)
_TOTAL_RE = re.compile(r"\b(?:monto\s+total|total(?:\s+pagado)?)\s*:\s*\$\s*" + _AMOUNT_NUMBER, re.IGNORECASE)
# The pesos charged for a payment in dollars: "Tipo de cambio: $985 Monto: $134.106"
_CLP_CHARGED_RE = re.compile(r"\bmonto\s*:\s*\$\s*" + _AMOUNT_NUMBER, re.IGNORECASE)
# Incoming transfer notice: "Le informamos que Juan Pérez le ha transferido $70.000"
_RECEIVED_RE = re.compile(r"que\s+(.{2,80}?)\s+le\s+ha\s+transferido", re.IGNORECASE)


def _labelled(regex, text: str):
    match = regex.search(text)
    return _clean_chilean_number(match.group(1)) if match else None


class BancoChileParser(BaseBankParser):
    bank_code = "bchile"
    bank_name = "Banco de Chile / Edwards"

    def can_parse(self, sender: str, subject: str) -> bool:
        s = sender.lower()
        sub = subject.lower()
        return ("bancochile" in s or "bancoedwards" in s or "bchile" in s or "banco de chile" in sub or "banco edwards" in sub)

    def parse(self, subject: str, body_text: str, body_html: str) -> Optional[ParsedTransaction]:
        text = body_text or clean_html_to_text(body_html)
        if is_non_transactional_email(subject, text):
            return None

        combined_text = f"{subject}\n{text}"
        sub_lower = subject.lower()

        # Determine transaction type
        received = _RECEIVED_RE.search(text)
        is_income = any(w in sub_lower for w in ["transferencia recibida", "abono", "deposito"]) \
            or ("abono a su cuenta" in text.lower()) or bool(received)
        tx_type = "income" if is_income else "expense"

        # Amount extraction
        amount = _labelled(_PAID_FOREIGN_RE, text) or _labelled(_TOTAL_RE, text) or parse_chilean_amount(text)
        if not amount:
            amount = parse_chilean_amount(combined_text)
        if not amount:
            return None

        # Merchant / Recipient extraction
        merchant = received.group(1).strip() if received else None
        # 1. Transfer sentence pattern: e.g. "transferencia de fondos a Ferreteria Central, el día 31..."
        tef_match = None if merchant else re.search(
            r"transferencia(?:\s+de\s+fondos)?\s+a\s+([^\n\r,.;]+?)(?:,\s*el\s+d[ií]a|\s+el\s+d[ií]a|\s+desde|$)",
            text,
            re.IGNORECASE
        )
        if tef_match:
            cand = tef_match.group(1).strip()
            if len(cand) >= 2 and cand.lower() not in ["un tercero", "terceros", "otra cuenta"]:
                merchant = cand

        # 2. Key-value label in tabular format (e.g. "Nombre: Ferreteria Central", "Destinatario: Ferreteria Central")
        if not merchant:
            merch_match = re.search(
                r"(?:comercio|establecimiento|lugar|destinatario|nombre\s+del\s+destinatario|a\s+nombre\s+de|empresa|servicio|pago\s+a|transferencia\s+a|hacia|nombre)\s*[:=]\s*([^\n\r<]{2,60})",
                text,
                re.IGNORECASE
            )
            if merch_match:
                cand = merch_match.group(1).strip()
                if cand.lower() not in ["nombre", "rut", "cuenta", "banco", "mail", "fecha", "monto", "id", "mensaje", "datos del destinatario", "datos de la transferencia"]:
                    merchant = cand

        # 3. Card purchase pattern: "con Tarjeta de Crédito ****4321 en TIENDA ONLINE SPA el 01/09/2026"
        if not merchant:
            card_merch = re.search(
                r"\ben\s+([A-Z0-9\s*.\-_/]{2,60}?)\s+(?:el\s+\d{1,2}[/.-]|el\s+d[ií]a|\.|$)",
                text,
                re.IGNORECASE
            )
            if card_merch:
                cand = card_merch.group(1).strip()
                if len(cand) >= 2 and cand.lower() not in ["app mi banco", "banco en línea", "banco en linea", "linea", "línea"]:
                    merchant = cand

        # 4. Fallback regex for unstructured texts
        if not merchant:
            merch_match = re.search(
                r"(?:comercio|establecimiento|lugar|destinatario|nombre\s+del\s+destinatario|a\s+nombre\s+de|empresa|servicio|pago\s+a|transferencia\s+a|hacia)\s*[:=]?\s*([^\n\r<]{2,60})",
                text,
                re.IGNORECASE
            )
            if merch_match:
                cand = merch_match.group(1).strip()
                if cand.lower() not in ["nombre", "rut", "cuenta", "banco", "mail", "fecha", "monto", "id", "mensaje", "datos del destinatario"]:
                    merchant = cand

        # 5. Check subject for recipient: e.g. "Transferencia a Juan Perez"
        if not merchant:
            sub_merch = re.search(r"(?:transferencia\s+a|pago\s+a|compra\s+en)\s+([a-zA-Z0-9\s.]{2,40})", subject, re.IGNORECASE)
            if sub_merch:
                merchant = sub_merch.group(1).strip()

        # A generic "Banco de Chile" would teach the classifier one meaning for every unrecognized email
        if not merchant:
            merchant = subject.strip() or "Banco de Chile"

        # Clean merchant of artifacts
        merchant = re.sub(r"\s+", " ", merchant).strip(" -:;,")

        # Date extraction
        date_match = re.search(r"(?:fecha|hora|realizada el)\s*[:=]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", text, re.IGNORECASE)
        date_str = parse_chilean_date(date_match.group(1)) if date_match else parse_chilean_date(text)

        # Currency detection (CLP vs USD vs EUR)
        currency = detect_currency(combined_text)
        account_hint = detect_account_hint(combined_text)
        clp_amount = _labelled(_CLP_CHARGED_RE, text) if currency != "CLP" else None

        return ParsedTransaction(
            amount=amount,
            currency=currency,
            date=date_str,
            merchant=merchant,
            description=f"{subject} - {merchant}",
            tx_type=tx_type,
            raw_text=text[:600],
            bank_code=self.bank_code,
            account_hint=account_hint,
            clp_amount=clp_amount,
        )
