class Bike:

    def __init__(self, bike_id: str, number: int, created_at: str):
        self.id = bike_id
        self.number = number
        self.created_at = created_at

    def __str(self):
        return f"Bike(id='{self.id}', number={self.number}, created_at='{self.created_at}')"