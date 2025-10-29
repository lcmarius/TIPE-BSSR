import math
from enum import Enum



class Station:

    def __init__(self, station_number: int, name: str, capacity: int,
                 address: str, geo_long: float, geo_lat: float, connected: bool = True):
        self.number = station_number
        self.name = name
        self.capacity = capacity
        self.address = address
        self.long = geo_long
        self.lat = geo_lat
        self.connected = connected

    def __str__(self):
        return f"Station(number={self.number}, nom='{self.name}', capacity={self.capacity})"

    def distance_to(self, other: 'Station') -> float:
        """Calcule la distance haversine (en mètres) entre cette station et une autre"""
        R = 6371000  # Rayon de la Terre en mètres

        lat1_rad = math.radians(self.lat)
        lat2_rad = math.radians(other.lat)
        delta_lat = math.radians(other.lat - self.lat)
        delta_long = math.radians(other.long - self.long)

        """
        Formule de Haversine:
        a = sin²(Δφ/2) + cos φ1 * cos φ2 * sin²(Δλ/2)
        c = 2 * atan2(√a, √(1−a))
        d = R * c
        ϕ est la latitude, λ la longitude, R le rayon de la Terre
        """
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_long / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

class TargetedStation(Station):

    @staticmethod
    def from_station(station: Station, bike_count: int, bike_target: int):
        return TargetedStation(station.id, station.name, station.capacity, station.address, station.long, station.lat, bike_count, bike_target)

    def __init__(self, station_id: int, name: str, capacity: int,
                 address: str, geo_long: float, geo_lat: float, bike_count: int, bike_target: int):
        super().__init__(station_id, name, capacity, address, geo_long, geo_lat)
        self.bike_count = bike_count
        self.bike_target = bike_target


    def bike_gap(self) -> int:
        """
        Calcule l'écart entre le nombre de vélos actuel et le nombre de vélos cible
        Un écart positif signifie qu'il y a plus de vélos que le cible (besoin de retirer des vélos)
        Un écart négatif signifie qu'il y a moins de vélos que le cible (besoin d'ajouter des vélos)
        Un écart de 0 signifie que la station est équilibrée
        """
        return self.bike_count-self.bike_target

    def is_loading(self):
        return self.bike_gap() > 0

    def is_unloading(self):
        return self.bike_gap() < 0

    def is_equilibrated(self):
        return self.bike_gap() == 0

    def __str__(self):
        return f"TargetedStation(id={self.id}, nom='{self.name}', capacity={self.capacity}, bike_count={self.bike_count}, bike_target={self.bike_target})"