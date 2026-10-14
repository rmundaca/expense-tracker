import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

@dataclass
class ParsedTransaction:
    amount: float
    currency: str = "CLP"
    date: str = ""
    merchant: Optional[str] = None
    description: Optional[str] = None
    tx_type: str = "expense"  # expense, income, transfer
    raw_text: str = ""
    bank_code: str = "generic"
    account_hint: Optional[str] = None  # e.g. "credito", "corriente", "vista"
    reference: Optional[str] = None  # the bank's operation id: two emails with the same one are one movement
    clp_amount: Optional[float] = None  # foreign-currency movement: the pesos the bank actually charged


def is_marketing_footer_line(line: str) -> bool:
    """Detects if a line is part of marketing or footer disclaimers."""
    footer_keywords = [
        "información importante", "este es un mensaje automático",
        "no responda a este mensaje", "derechos reservados", "all rights reserved"
    ]
    line_lower = line.lower()
    return any(k in line_lower for k in footer_keywords)


def clean_html_to_text(html_content: str) -> str:
    """Safely extracts plain text from email HTML with intelligent table handling."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove script and style elements
        for element in soup(["script", "style", "meta", "link", "head"]):
            element.decompose()

        # Handle table rows intelligently so tabular key-values are preserved on single lines
        for tr in soup.find_all("tr"):
            if tr.find("table"):
                continue  # Let inner leaf tables be formatted first
            cells = []
            for cell in tr.find_all(["th", "td"]):
                txt = " ".join(cell.get_text().split())
                if txt:
                    cells.append(txt)
            if not cells:
                continue
            if len(cells) == 2:
                # Key: Value pair (e.g. "Monto: $70.000" or "Nombre: Ferreteria Central")
                k, v = cells[0].rstrip(":"), cells[1]
                tr.replace_with(soup.new_string(f"{k}: {v}\n"))
            elif len(cells) > 2:
                tr.replace_with(soup.new_string(" | ".join(cells) + "\n"))
            elif len(cells) == 1:
                tr.replace_with(soup.new_string(f"{cells[0]}\n"))

        raw = soup.get_text(separator="\n")
        lines = []
        for line in raw.splitlines():
            cleaned = " ".join(line.split())
            if cleaned:
                # Stop parsing if marketing / benefits disclaimer starts
                if is_marketing_footer_line(cleaned):
                    break
                lines.append(cleaned)
        return "\n".join(lines)
    except Exception:
        return html_content


def _clean_chilean_number(raw_num: str) -> Optional[float]:
    if not raw_num:
        return None
    raw_num = raw_num.strip()
    if "." in raw_num and "," in raw_num:
        last_dot = raw_num.rfind(".")
        last_comma = raw_num.rfind(",")
        if last_comma > last_dot:
            # Chilean/European: 1.250,50
            clean_num = raw_num.replace(".", "").replace(",", ".")
        else:
            # US format: 1,250.50
            clean_num = raw_num.replace(",", "")
    elif "." in raw_num:
        parts = raw_num.split(".")
        if len(parts[-1]) == 3 or len(parts) > 2:
            clean_num = raw_num.replace(".", "")
        else:
            clean_num = raw_num
    elif "," in raw_num:
        clean_num = raw_num.replace(",", ".")
    else:
        clean_num = raw_num
    try:
        val = float(clean_num)
        return abs(val) if val > 0 else None
    except ValueError:
        return None


def detect_currency(text: str) -> str:
    """Detects if transaction is in USD, EUR or CLP."""
    if not text:
        return "CLP"
    if re.search(r"\b(?:usd|d[oó]lares|dolar|dólar)\b|us\$|u\$s|us\s*\$", text, re.IGNORECASE):
        return "USD"
    if re.search(r"\b(?:eur|euros|euro)\b|€", text, re.IGNORECASE):
        return "EUR"
    return "CLP"


NON_TRANSACTIONAL_KEYWORDS = [
    "aviso de seguridad", "modificacion de datos", "modificación de datos",
    "clave de internet", "clave de acceso", "cartola consolidada",
    "cartola de cuenta", "resumen de productos", "bienvenido a", "bienvenida a",
    "bloqueo de tarjeta", "comprobante de envio de clave", "comprobante de envío de clave",
    "actualizacion de datos", "actualización de datos", "encuesta de satisfaccion",
    "encuesta de satisfacción", "aviso de inicio de sesion", "aviso de inicio de sesión",
    "dispositivo nuevo", "registro de dispositivo", "codigo de seguridad", "código de seguridad",
    "transferencias diarias", "limite de transferencia", "límite de transferencia",
    "aviso de ingreso", "resumen semanal", "noticia", "beneficio", "promocion", "promoción"
]

TRANSACTIONAL_KEYWORDS = [
    "transferencia", "comprobante", "pago", "compra", "cargo", "abono",
    "deposito", "depósito", "giro", "transaccion", "transacción", "monto transferido"
]

def is_non_transactional_email(subject: str, text: str) -> bool:
    """Detects informational, security or administrative bank emails that do not represent a financial transaction."""
    sub_lower = (subject or "").lower()
    # 1. If subject contains clear transactional keywords, it is definitely transactional
    if any(k in sub_lower for k in TRANSACTIONAL_KEYWORDS):
        return False

    # 2. Check subject for non-transactional indicators
    if any(k in sub_lower for k in NON_TRANSACTIONAL_KEYWORDS):
        return True

    # 3. If text is provided, inspect upper body text (avoiding marketing disclaimers in footers)
    header_text = (text or "")[:1200].lower()
    if any(k in header_text for k in TRANSACTIONAL_KEYWORDS):
        return False

    ADMINISTRATIVE_PHRASES = [
        "aviso de seguridad", "clave de internet", "clave de acceso",
        "cartola consolidada", "cartola de cuenta", "bloqueo de tarjeta",
        "encuesta de satisfacci", "aviso de inicio de sesi", "dispositivo nuevo",
        "código de seguridad", "codigo de seguridad", "comprobante de envio de clave"
    ]
    return any(p in header_text for p in ADMINISTRATIVE_PHRASES)


# A monetary number: 45.990 | 1.250,50 | 1,250.50 | 4,57 | 15000
_AMOUNT_NUMBER = r"([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:[.,][0-9]{1,2})?|[0-9]{3,})"
_RUT_SUFFIX_RE = re.compile(r"\s?-\s?[0-9kK](?![0-9])")


def _looks_like_rut(text: str, number_end: int) -> bool:
    """A number followed by a check digit ("12.345.678-9") is a RUT, not an amount."""
    return _RUT_SUFFIX_RE.match(text, number_end) is not None


def parse_chilean_amount(text: str) -> Optional[float]:
    """
    Parses Chilean and foreign currency amounts (CLP, USD, EUR) accurately without
    accidentally matching dates, account numbers (e.g. Cuenta N° 123.456.789), or RUTs.
    """
    if not text:
        return None

    # Contextual keywords that disqualify a nearby number from being a monetary amount
    DISQUALIFYING_PREFIXES = r"(?:cuenta|cta|n°|nro|número|tarjeta|rut|cliente|folio|operaci[oó]n|c[oó]digo|tel[eé]fono|ip)"

    # Tier 0: Explicit foreign currency symbol / code (e.g. "US$4,57", "US$ 4.57", "USD 12.50", "US $ 4,57")
    for m in re.finditer(
        r"(?:US\$|U\$S|US\s*\$|USD|EUR|€)\s*([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:[.,][0-9]{1,2})?|[0-9]+)",
        text,
        re.IGNORECASE
    ):
        prefix_context = text[max(0, m.start() - 30):m.start()].lower()
        if not re.search(DISQUALIFYING_PREFIXES + r"\s*[:#.]?\s*$", prefix_context):
            val = _clean_chilean_number(m.group(1))
            if val is not None:
                return val

    # Tier 1: Explicit financial keyword followed by amount (e.g. "Monto: $ 45.990", "compra por US$4,57", "Total pagado: 12.000").
    # Whole words only ("transporte" is not "por"), and the words between keyword and number must not name
    # an account, card or RUT ("Gracias por usar su Tarjeta ****1234"). A bare "por" needs the amount right after it.
    for m in re.finditer(
        r"\b(?:(?:monto|total|valor|importe|pagado|transferido|cargo|abono|girado|compra(?:\s+por)?|pago(?:\s+por)?)\b([^0-9$]{0,40})|por\s*(?=US\$|U\$S|US\s*\$|USD|\$|CLP))"
        r"[:=]?\s*(?:US\$|U\$S|US\s*\$|USD|\$|CLP)?\s*" + _AMOUNT_NUMBER,
        text,
        re.IGNORECASE
    ):
        if m.group(1) and re.search(r"(?<![a-záéíóúñ])" + DISQUALIFYING_PREFIXES + r"(?![a-záéíóúñ])", m.group(1).lower()):
            continue
        if _looks_like_rut(text, m.end(2)):
            continue
        val = _clean_chilean_number(m.group(2))
        if val is not None:
            return val

    # Tier 2: Explicit currency symbol $ or CLP followed by number (e.g. "$ 45.990", "$15000")
    for m in re.finditer(r"(?:\$|CLP)\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?|[0-9]{3,})", text, re.IGNORECASE):
        prefix_context = text[max(0, m.start() - 30):m.start()].lower()
        if not re.search(DISQUALIFYING_PREFIXES + r"\s*[:#.]?\s*$", prefix_context):
            val = _clean_chilean_number(m.group(1))
            if val is not None:
                return val

    # Tier 3: Explicit CLP, USD, EUR or pesos following the number (e.g. "45.990 CLP", "50000 pesos", "4,57 USD")
    for m in re.finditer(r"([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:[.,][0-9]{1,2})?|[0-9]{3,})\s*(?:CLP|pesos|USD|d[oó]lares|EUR|euros)", text, re.IGNORECASE):
        prefix_context = text[max(0, m.start() - 30):m.start()].lower()
        if not re.search(DISQUALIFYING_PREFIXES + r"\s*[:#.]?\s*$", prefix_context):
            val = _clean_chilean_number(m.group(1))
            if val is not None:
                return val

    # Tier 4: Thousands-separated Chilean number with dot ONLY if context contains transaction verbs
    has_tx_context = bool(re.search(r"(?:compra|pago|transferencia|cargo|abono|transacci[oó]n|descuento)", text, re.IGNORECASE))
    if has_tx_context:
        for m in re.finditer(r"\b([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?)\b", text):
            prefix_context = text[max(0, m.start() - 35):m.start()].lower()
            suffix_context = text[m.end():min(len(text), m.end() + 15)].lower()
            # If followed by hyphen (like RUT "12.345.678-9"), ignore
            if suffix_context.strip().startswith("-"):
                continue
            # If preceded by account / card / client / phone words, ignore
            if re.search(DISQUALIFYING_PREFIXES, prefix_context):
                continue
            val = _clean_chilean_number(m.group(1))
            if val is not None:
                return val

    return None


_REFERENCE_RE = re.compile(
    # Labelled as an operation: any id with digits ("ID de transacción 8200000007", "Transacción BCAMOVIL01...")
    r"(?:\bID\s+de\s+transacci[oó]n|\btransacci[oó]n|c[oó]digo\s+de\s+autorizaci[oó]n|n°\s+de\s+operaci[oó]n)"
    r"\s*:?\s*((?=[A-Z_]*[0-9])[A-Z0-9_]{6,60})\b"
    # A bare "ID" also names customer numbers of paid bills ("Empresa: Gas Sur ID: 0900000005"): letters required
    r"|\bID\s*:\s*((?=[A-Z0-9_]*[A-Z])(?=[A-Z_]*[0-9])[A-Z0-9_]{6,60})\b",
    re.IGNORECASE,
)


def extract_bank_reference(text: str) -> Optional[str]:
    """The bank's operation id ("ID: TEF_IPE26...", "Transacción BCAMOVIL01..."); placeholders like "ID: 00" are not ids."""
    match = _REFERENCE_RE.search(text or "")
    return (match.group(1) or match.group(2)).upper() if match else None


def _valid_date(year: int, month: int, day: int) -> bool:
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def parse_chilean_date(text: str) -> Optional[str]:
    """Extracts 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' from text; None when there is no valid date."""
    if not text:
        return None

    # DD/MM/YYYY or DD-MM-YYYY, optionally followed by HH:MM(:SS)
    for match in re.finditer(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", text):
        d, m, y, hh, mm, ss = match.groups()
        day, month, year = int(d), int(m), int(y)
        if not _valid_date(year, month, day):
            continue
        if hh and mm and int(hh) < 24 and int(mm) < 60:
            return f"{year:04d}-{month:02d}-{day:02d} {int(hh):02d}:{int(mm):02d}:{int(ss or 0):02d}"
        return f"{year:04d}-{month:02d}-{day:02d}"

    # "DD de <mes> de YYYY"
    for match in re.finditer(r"(\d{1,2})\s+de\s+([a-zA-Z]+)\s+(?:del?\s+)?(\d{4})", text, re.IGNORECASE):
        day, month, year = int(match.group(1)), MONTHS_ES.get(match.group(2).lower()), int(match.group(3))
        if month and _valid_date(year, month, day):
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def detect_account_hint(text: str) -> Optional[str]:
    """Which kind of account an email refers to: 'credito', 'corriente', 'vista' or None."""
    t = (text or "").lower()
    if re.search(r"tarjeta\s+de\s+cr[eé]dito|\bcmr\b|\btc\b", t):
        return "credito"
    if "cuenta corriente" in t:
        return "corriente"
    if re.search(r"cuenta\s+(?:vista|rut)", t):
        return "vista"
    return None


class BaseBankParser:
    bank_code: str = "generic"
    bank_name: str = "Generic Bank"

    def can_parse(self, sender: str, subject: str) -> bool:
        raise NotImplementedError

    def parse(self, subject: str, body_text: str, body_html: str) -> Optional[ParsedTransaction]:
        raise NotImplementedError
