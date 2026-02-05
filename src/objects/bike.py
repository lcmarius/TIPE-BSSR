from enum import Enum
from typing import Optional, Union


class BikeStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    AVAILABLE_IN_STOCK = "AVAILABLE_IN_STOCK"
    TO_BE_REPARED = "TO_BE_REPARED"
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

    def __init__(self, bike_id: str, number: int, status: Optional[Union[BikeStatus, str]] = None):
        self.id = bike_id
        self.number = number
        # status gardé en mémoire (cache) mais pas stocké en DB
        self.status = BikeStatus.from_str(status) if isinstance(status, str) else status

    def __str__(self):
        return f"Bike(id='{self.id}', number={self.number}, status='{self.status}')"
