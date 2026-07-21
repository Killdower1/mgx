"""
Transaction classifier for Difotoin API data.
Classifies each raw transaction record into funnel stages.
"""
from typing import TypedDict
from enum import Enum

class TransactionRole(str, Enum):
    SESSION = "session"           # Foto session (type=null/"", has capture)
    UNLOCK = "unlock"             # Paid unlock (type=unlock-photo, amount>0)
    FREE_UNLOCK = "free_unlock"   # Free unlock (type=unlock-photo, amount=0, payment_type=free-unlock)
    VOUCHER_UNLOCK = "voucher_unlock"  # Voucher unlock
    PRINT = "print"               # Print payment (type=print, amount>0)
    UNKNOWN = "unknown"           # Cannot classify

class ClassifiedTransaction(TypedDict):
    id: str
    role: str
    outlet_name: str
    outlet_id: str
    date: str
    amount: float
    type: str
    payment_type: str
    payment_status: str
    parent_id: str | None
    has_capture: bool
    has_unlocked_photo: bool
    is_revenue: bool  # True if type in (unlock, print) and amount > 0 and paid

def classify_transaction(txn: dict) -> ClassifiedTransaction:
    """Classify a raw API transaction record into its funnel role."""
    details = txn.get("details", []) or []
    has_capture = any((d.get("capture_qty") or 0) > 0 for d in details)
    has_unlocked = any((d.get("unlocked_photo") or 0) > 0 for d in details)
    
    tx_type_raw = txn.get("type")
    tx_type = tx_type_raw or ""
    payment_type = txn.get("payment_type") or ""
    payment_status = txn.get("payment_status") or ""
    amount = float(txn.get("processed_gross_amount") or 0)
    
    # Determine role
    if tx_type == "print":
        role = TransactionRole.PRINT
    elif tx_type == "unlock-photo":
        if payment_type == "free-unlock":
            role = TransactionRole.FREE_UNLOCK
        elif payment_type == "voucher-unlock":
            role = TransactionRole.VOUCHER_UNLOCK
        elif amount > 0:
            role = TransactionRole.UNLOCK
        else:
            role = TransactionRole.UNKNOWN
    elif tx_type_raw in (None, "") and has_capture:
        role = TransactionRole.SESSION
    else:
        role = TransactionRole.UNKNOWN
    
    # Revenue = unlock/print with amount > 0 and paid
    is_revenue = (
        role in (TransactionRole.UNLOCK, TransactionRole.PRINT)
        and amount > 0
        and payment_status == "paid"
    )
    
    return ClassifiedTransaction(
        id=str(txn.get("id", "")),
        role=role.value,
        outlet_name=str(txn.get("outlet_name", "")).strip(),
        outlet_id=str(txn.get("outlet_id", "")),
        date=str(txn.get("date", ""))[:10],
        amount=amount,
        type=tx_type,
        payment_type=payment_type,
        payment_status=payment_status,
        parent_id=txn.get("parent_id"),
        has_capture=has_capture,
        has_unlocked_photo=has_unlocked,
        is_revenue=is_revenue,
    )

def classify_transactions(txns: list[dict]) -> list[ClassifiedTransaction]:
    """Classify a list of raw transaction records."""
    return [classify_transaction(t) for t in txns]

def summarize_funnel(classified: list[ClassifiedTransaction]) -> dict:
    """Summarize funnel metrics from classified transactions."""
    sessions = sum(1 for c in classified if c["role"] == "session")
    unlocks = sum(1 for c in classified if c["role"] in ("unlock", "free_unlock", "voucher_unlock"))
    unlocks_paid = sum(1 for c in classified if c["role"] == "unlock")
    prints = sum(1 for c in classified if c["role"] == "print")
    revenue = sum(c["amount"] for c in classified if c["is_revenue"])
    
    conversion_rate = (unlocks / sessions * 100) if sessions > 0 else 0
    print_rate = (prints / unlocks_paid * 100) if unlocks_paid > 0 else 0
    
    return {
        "sessions": sessions,
        "unlocks": unlocks,
        "unlocks_paid": unlocks_paid,
        "prints": prints,
        "revenue": revenue,
        "conversion_rate": round(conversion_rate, 2),
        "print_rate": round(print_rate, 2),
    }
