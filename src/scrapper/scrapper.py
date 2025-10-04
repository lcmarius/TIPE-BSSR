import requests
from datetime import datetime
from typing import Dict, List, Optional

class Station:
    """Classe représentant une station"""

    def __init__(self, station_id: int, nom_fr: str, capacite_max: int,
                 adresse: str, longitude: float, latitude: float):
        self.id = station_id
        self.nom_fr = nom_fr
        self.capacite_max = capacite_max
        self.adresse = adresse
        self.longitude = longitude
        self.latitude = latitude

    def __repr__(self):
        return f"Station(id={self.id}, nom='{self.nom_fr}', capacite={self.capacite_max})"

class Velo:
    """Classe représentant un vélo Bicloo"""

    def __init__(self, velo_id: str, number: int, created_at: str):
        self.id = velo_id
        self.number = number
        self.created_at = created_at

    def __repr__(self):
        return f"Velo(id='{self.id}', number={self.number}, created_at='{self.created_at}')"

class VeloAPI:
    """Classe pour gérer les appels à l'API Bicloo"""

    def __init__(self):
        self.base_url = "https://api.cyclocity.fr/contracts/nantes"
        self.auth_url = "https://api.cyclocity.fr/auth/environments/PRD/client_tokens"
        self.access_token = None
        self.refresh_token = None

    def generate_token(self) -> bool:
        """Génère un token d'accès pour l'API"""
        payload = {
            "code": "vls.web.nantes:PRD",
            "key": "d7d30faca33532872541d2bb4b9f703d05bed3fb6106fdce3eb05913331901d1"
        }

        response = requests.post(self.auth_url, json=payload)
        if response.status_code != 200:
          raise Exception("Erreur lors de la génération du token d'authentification")

        data = response.json()
        self.access_token = data.get('accessToken')
        self.refresh_token = data.get('refreshToken')

    def get_headers(self) -> dict:
        """Retourne les headers avec le token d'authentification"""
        if not self.access_token:
            if not self.generate_token():
                return {}

        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def get_stations_info(self) -> Optional[List[dict]]:
        """Récupère les informations statiques des stations"""
        url = f"{self.base_url}/gbfs/v3/station_information.json"

        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Erreur lors de la récupération des informations des stations")
        data = response.json()
        return data['data']['stations']

    def get_bikes_info(self) -> Optional[List[dict]]:
        """Récupère les informations des vélos"""
        url = f"{self.base_url}/bikes"
        headers = self.get_headers()

        if not headers:
            raise Exception("Erreur lors de la récupération des headers")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception("Erreur lors de la récupération des informations des vélos")


        return response.json()

    def get_bike_info(self) -> Optional[dict]:
        """Récupère les informations des vélos"""
        url = f"{self.base_url}/bikes"
        headers = self.get_headers()

        if not headers:
            raise Exception("Erreur lors de la récupération des headers")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception("Erreur lors de la récupération des informations des vélos")

        return response.json()

def register_stations() -> Dict[int, Station]:
    """Crée un dictionnaire de toutes les stations"""
    api = VeloAPI()
    stations_data = api.get_stations_info()
    stations_dict = {}

    for station_data in stations_data:
        nom_fr = ""
        for name_obj in station_data.get('name', []):
            if name_obj.get('language') == 'fr':
                nom_fr = name_obj.get('text', '')
                break

        station = Station(
            station_id=int(station_data['station_id']),
            nom_fr=nom_fr,
            capacite_max=station_data['capacity'],
            adresse=station_data.get('address', ''),
            longitude=station_data['lon'],
            latitude=station_data['lat']
        )

        stations_dict[station.id] = station

    return stations_dict

def register_bikes() -> Dict[str, Velo]:
    api = VeloAPI()
    bikes_data = api.get_bikes_info()
    bikes_dict = {}

    for bike_data in bikes_data:
        velo = Velo(
            velo_id=bike_data['id'],
            number=bike_data['number'],
            created_at=bike_data['createdAt']
        )

        bikes_dict[velo.id] = velo

    return bikes_dict

def main():
    """Fonction principale pour tester le code"""
    print("=== Récupération des stations ===")
    stations = register_stations()
    print(f"Nombre de stations récupérées: {len(stations)}")
    print("\n=== Récupération des vélos ===")
    bikes = register_bikes()
    print(f"Nombre de vélos récupérés: {len(bikes)}")

