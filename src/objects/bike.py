class Bike:

    def __init__(self, bike_id: str, number: int):
        self.id = bike_id
        self.number = number

    def __str__(self):
        return f"Bike(id='{self.id}', number={self.number})"
