"""
Suggests category / account / type for a movement, in order of reliability:
  1. Deterministic rules (RuleMapping).
  2. Memory: the last thing the user confirmed for the same merchant (exact, normalized).
  3. Naive Bayes over the words of everything the user confirmed (category only).

Learning data lives in ml_training_samples (one row per merchant, upserted). The Naive Bayes
model is rebuilt in memory from that table whenever it changes; nothing is stored on disk.
Every user has their own database, so there is one Classifier per database (see ClassifierRegistry).
"""
import math
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.schemas import Account, Category, MLTrainingSample
from app.services.rules_engine import RulesEngine, normalize_text

STOP_WORDS = {
    "de", "la", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con", "no",
    "una", "su", "al", "lo", "como", "mas", "pero", "sus", "le", "ya", "o", "este", "si", "porque",
    "esta", "son", "entre", "cuando", "muy", "sin", "sobre", "ser", "tiene", "tambien", "me", "hasta",
    "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra",
    "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mi", "antes", "algunos",
    "comprobante", "transaccion", "notificacion", "pago", "cargo", "abono", "banco", "tarjeta", "chile",
}

MIN_NB_CONFIDENCE = 0.35


def tokenize(text: str) -> List[str]:
    words = re.findall(r"\b[a-z0-9]{3,}\b", normalize_text(text))
    return [w for w in words if w not in STOP_WORDS]


def merchant_key(merchant: Optional[str]) -> Optional[str]:
    key = normalize_text(merchant)[:150]
    return key if len(key) >= 3 else None


class NaiveBayes:
    """Multinomial Naive Bayes with Laplace smoothing, pure Python (runs on the 32-bit NAS)."""

    def __init__(self, texts: List[str], labels: List[int]):
        self.class_counts: Dict[int, int] = defaultdict(int)
        self.word_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.total_words: Dict[int, int] = defaultdict(int)
        vocab = set()
        for text, label in zip(texts, labels):
            self.class_counts[label] += 1
            for token in tokenize(text):
                vocab.add(token)
                self.word_counts[label][token] += 1
                self.total_words[label] += 1
        self.vocab_size = max(len(vocab), 1)
        self.total = sum(self.class_counts.values())

    def predict(self, text: str) -> Tuple[Optional[int], float]:
        tokens = tokenize(text)
        if not self.total or not tokens:
            return None, 0.0
        scores = {}
        for label, count in self.class_counts.items():
            score = math.log(count / self.total)
            denom = self.total_words[label] + self.vocab_size
            for token in tokens:
                score += math.log((self.word_counts[label].get(token, 0) + 1) / denom)
            scores[label] = score
        best = max(scores, key=scores.get)
        top = scores[best]
        norm = sum(math.exp(s - top) for s in scores.values())
        return best, round(1.0 / norm, 3)


@dataclass
class ClassificationResult:
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    tx_type: str = "expense"
    source: str = "none"  # rule, memory, ml, none
    confidence: float = 0.0


class Classifier:
    def __init__(self):
        self._lock = threading.Lock()
        self._dirty = True
        self._memory: Dict[str, MLTrainingSample] = {}
        self._nb: Optional[NaiveBayes] = None

    def invalidate(self):
        self._dirty = True

    def _ensure_trained(self, db: Session):
        with self._lock:
            if not self._dirty:
                return
            memory, texts, labels = {}, [], []
            for s in db.query(MLTrainingSample).order_by(MLTrainingSample.id).all():
                db.expunge(s)
                key = s.merchant_key or merchant_key(s.text)
                if key:
                    memory[key] = s
                if s.category_id:
                    texts.append(s.text)
                    labels.append(s.category_id)
            self._memory = memory
            self._nb = NaiveBayes(texts, labels) if texts else None
            self._dirty = False

    def classify(self, db: Session, merchant: Optional[str] = "", description: Optional[str] = "",
                 sender: Optional[str] = "") -> ClassificationResult:
        categories = {c.id: c for c in db.query(Category).filter(Category.is_active == True).all()}
        rule = RulesEngine.match(db, merchant, description, sender)
        if rule.matched:
            tx_type = rule.tx_type or "expense"
            # A rule whose category was archived still decides the type, but never suggests that category
            category_id = rule.category_id if tx_type != "transfer" and rule.category_id in categories else None
            if category_id:
                tx_type = categories[category_id].type  # an income category makes it income
            return ClassificationResult(
                category_id=category_id, account_id=rule.account_id,
                destination_account_id=rule.destination_account_id,
                tx_type=tx_type, source="rule", confidence=1.0,
            )

        self._ensure_trained(db)
        valid_accounts = {a.id for a in db.query(Account.id).all()}

        for key in (merchant_key(merchant), merchant_key(f"{merchant or ''} {description or ''}")):
            sample = self._memory.get(key) if key else None
            if sample:
                category_id = sample.category_id if sample.category_id in categories else None
                tx_type = sample.tx_type or "expense"
                if tx_type != "transfer" and category_id:
                    tx_type = categories[category_id].type  # legacy CSV samples were all stored as "expense"
                return ClassificationResult(
                    category_id=category_id,
                    account_id=sample.account_id if sample.account_id in valid_accounts else None,
                    destination_account_id=sample.destination_account_id if sample.destination_account_id in valid_accounts else None,
                    tx_type=tx_type, source="memory", confidence=0.95,
                )

        if self._nb:
            category_id, confidence = self._nb.predict(f"{merchant or ''} {description or ''}")
            category = categories.get(category_id)
            if category and confidence >= MIN_NB_CONFIDENCE:
                return ClassificationResult(
                    category_id=category.id, tx_type=category.type,
                    source="ml", confidence=confidence,
                )
        return ClassificationResult()

    def learn(self, db: Session, merchant: Optional[str], description: Optional[str],
              category_id: Optional[int], account_id: Optional[int], tx_type: str,
              destination_account_id: Optional[int] = None, source: str = "user"):
        """Records (or overwrites) what the user confirmed for this merchant. Caller commits."""
        if tx_type not in ("expense", "income", "transfer"):
            return
        if tx_type != "transfer" and not category_id:
            return
        text = f"{merchant or ''} {description or ''}".strip()
        key = merchant_key(merchant) or merchant_key(text)
        if not key:
            return
        # Sessions run with autoflush off: remember the samples added in this session, so a batch
        # (CSV import) never duplicates a key without rescanning every pending object on each row
        added = db.info.setdefault("ml_samples_added", {})
        sample = added.get(key)
        if sample is None or sample not in db:  # not added yet, or discarded by a rollback
            sample = db.query(MLTrainingSample).filter(MLTrainingSample.merchant_key == key).first()
        if not sample:
            sample = MLTrainingSample(merchant_key=key)
            db.add(sample)
            added[key] = sample
        sample.text = text[:1000]
        sample.category_id = category_id if tx_type != "transfer" else None
        sample.account_id = account_id
        sample.destination_account_id = destination_account_id if tx_type == "transfer" else None
        sample.tx_type = tx_type
        sample.source = source
        self.invalidate()


def database_key(db: Session) -> str:
    """Identifies the (per-user) database a session is bound to."""
    return str(db.get_bind().url)


class ClassifierRegistry:
    """Same interface as Classifier, dispatching to the Classifier of the session's database."""

    def __init__(self):
        self._lock = threading.Lock()
        self._classifiers: Dict[str, Classifier] = {}

    def _for(self, db: Session) -> Classifier:
        key = database_key(db)
        with self._lock:
            if key not in self._classifiers:
                self._classifiers[key] = Classifier()
            return self._classifiers[key]

    def classify(self, db: Session, *args, **kwargs) -> ClassificationResult:
        return self._for(db).classify(db, *args, **kwargs)

    def learn(self, db: Session, *args, **kwargs):
        self._for(db).learn(db, *args, **kwargs)

    def invalidate(self, db: Optional[Session] = None):
        """Invalidates the session's classifier, or all of them without a session."""
        with self._lock:
            targets = [self._classifiers.get(database_key(db))] if db is not None else list(self._classifiers.values())
        for c in targets:
            if c:
                c.invalidate()

    def forget(self, db_url: str):
        """Drops the classifier of a database that no longer exists (deleted user)."""
        with self._lock:
            self._classifiers.pop(db_url, None)


classifier_service = ClassifierRegistry()
