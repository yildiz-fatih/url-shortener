import string
from sqids import Sqids

SQIDS_MIN_LENGTH = 5
SQIDS_ALPHABET = string.ascii_lowercase + string.ascii_uppercase + string.digits

sqids = Sqids(alphabet=SQIDS_ALPHABET, min_length=SQIDS_MIN_LENGTH)


# Encode database ID to short code
def encode_id(id: int) -> str:
    return sqids.encode([id])


# Decode short code back to database ID
def decode_short_code(short_code: str) -> int | None:
    try:
        decoded = sqids.decode(short_code)
        if decoded:
            return decoded[0]
        return None
    except Exception:
        return None
