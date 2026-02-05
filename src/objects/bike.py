from enum import Enum
from typing import Union

class BikeStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    AVAILABLE_IN_STOCK = "AVAILABLE_IN_STOCK"
    TO_BE_REPAIRED = "TO_BE_REPAIRED"
    NOT_RECOGNIZED = "NOT_RECOGNIZED"
    MAINTENANCE = "MAINTENANCE"
    STOLEN = "STOLEN"
    DESTROYED = "DESTROYED"
    RENTED = "RENTED"
    REGULATION = "REGULATION"
    SCRAPPED = "SCRAPPED"

    @classmethod
    def from_str(cls, value: str) -> "BikeStatus":
        if isinstance(value, cls):
            return value
        normalized = value.strip().upper().replace(" ", "_")
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown BikeStatus: {value!r}")


class Bike:

    def __init__(self, bike_id: str, number: int, status: Union[BikeStatus, str], created_at: str = ""):
        self.id = bike_id
        self.number = number
        self.status = BikeStatus.from_str(status) if isinstance(status, str) else status
        self.created_at = created_at

    def __str__(self):
        return f"Bike(id='{self.id}', number={self.number}, status='{self.status}', created_at='{self.created_at}')"
