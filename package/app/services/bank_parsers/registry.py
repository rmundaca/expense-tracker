from datetime import datetime
from typing import List, Optional

from app.services.bank_parsers.base import (
    BaseBankParser, ParsedTransaction, clean_html_to_text, extract_bank_reference, is_non_transactional_email
)
from app.services.bank_parsers.bchile import BancoChileParser
from app.services.bank_parsers.bci import BciParser
from app.services.bank_parsers.generic import GenericBankParser


class BankParserRegistry:
    """Banks with real-email-tuned parsers first; everything else goes through the generic parser."""

    def __init__(self):
        self.generic = GenericBankParser()
        self.parsers: List[BaseBankParser] = [BancoChileParser(), BciParser()]

    def parse_email(self, sender: str, subject: str, body_text: str, body_html: str,
                    fallback_date: Optional[str] = None) -> Optional[ParsedTransaction]:
        if is_non_transactional_email(subject, body_text or body_html):
            return None
        parser = next((p for p in self.parsers if p.can_parse(sender, subject)), None)
        parsed = parser.parse(subject, body_text, body_html) if parser else None
        if not parsed:
            parsed = self.generic.parse(subject, body_text, body_html)
        if parsed and not parsed.date:
            parsed.date = fallback_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if parsed and not parsed.reference:
            parsed.reference = extract_bank_reference(body_text or clean_html_to_text(body_html))
        return parsed


parser_registry = BankParserRegistry()
