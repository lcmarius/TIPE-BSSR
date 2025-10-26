import time

import requests
from typing import Dict, List, Optional

from src.objects.bike import Bike
from src.objects.station import Station

class BiclooAPI:
    """Classe pour gérer les appels à l'API Bicloo"""

    TOKEN_EXPIRES_IN = 30*60

    def __init__(self):
        self.base_url = "https://api.cyclocity.fr/contracts/nantes"
        self.auth_url = "https://api.cyclocity.fr/auth/environments/PRD/client_tokens"
        self.access_token = None
        self.access_token_expires_at = None
        self.refresh_token = None

    def generate_token(self) -> bool:
        """Génère un token d'accès pour l'API"""
        payload = {
            "code": "vls.web.nantes:PRD",
            "key": "d7d30faca33532872541d2bb4b9f703d05bed3fb6106fdce3eb05913331901d1"
        }

        response = requests.post(self.auth_url, json=payload)
        if response.status_code != 200:
          print("Response:", response.status_code, response.text)
          return False

        data = response.json()
        self.access_token = data.get('accessToken')
        self.refresh_token = data.get('refreshToken')
        self.access_token_expires_at = time.monotonic() + BiclooAPI.TOKEN_EXPIRES_IN

        return True

    def get(self, endpoint: str, contentType : Optional[str] = None) -> Dict:
        """Effectue une requête GET à l'API Bicloo"""
        url = f"{self.base_url}/{endpoint}"

        if not self.access_token or self.access_token_expires_at < time.monotonic():
            if not self.generate_token():
                raise Exception("Erreur lors de la récupération des headers")

        response = requests.get(url, headers={
            'Authorization': f'Taknv1 {self.access_token}',
            'Accept': '*/*',
            'Content-Type': contentType if contentType else 'application/json'
        })
        if response.status_code != 200:
            print("Response:", response.status_code, response.text)
            raise Exception(f"Erreur lors de la requête à l'endpoint {endpoint}")

        return response.json()

# https://data.nantesmetropole.fr/explore/dataset/244400404_disponibilite-temps-reel-velos-libre-service-naolib-gbfs/table/?sort=-id
#     gbfs/v3/station_information.json
#     bikes
#     bikes/{id}
#statut vélo:
# AVAILABLE
# AVAILABLE_IN_STOCK
# TO_BE_REPARED
# NOT_RECOGNIZED
# MAINTENANCE
# STOLEN
# DESTROYED
# RENTED
# REGULATION
# SCRAPPED

# En fonction du statut on le catalogue à un endroit spécifique. Il existe:
# Le stockage: AVAIALBLE_IN_STOCK, TO_BE_REPARED,MAINTENANCE
# En station (donc pour chaque station = un endroit): AVAILABLE
# Perdus (poubelle): SCRAPPED, DESTROYED, STOLEN, NOT_RECOGNIZED

def register_stations(bicloo_api: BiclooAPI) -> Dict[int, Station]:
    """Crée un dictionnaire de toutes les stations"""

    stations_data = bicloo_api.get("gbfs/v3/station_information.json")['data']['stations']
    stations_dict = {}

    for station_data in stations_data:
        nom_fr = ""
        for name_obj in station_data.get('name', []):
            if name_obj.get('language') == 'fr':
                nom_fr = name_obj.get('text', '')
                break

        station = Station(
            station_id=int(station_data['station_id']),
            name=nom_fr,
            capacity=station_data['capacity'],
            address=station_data.get('address', ''),
            geo_long=station_data['lon'],
            geo_lat=station_data['lat']
        )

        stations_dict[station.id] = station

    return stations_dict

def register_bikes(bicloo_api: BiclooAPI) -> Dict[str, Bike]:
    bikes_data = bicloo_api.get("bikes", "application/vnd.bikes.v4+json")
    bikes_dict = {}

    for bike_data in bikes_data:
        velo = Bike(
            bike_id=bike_data['id'],
            number=bike_data['number'],
            created_at=bike_data['createdAt']
        )
        bikes_dict[velo.id] = velo

    return bikes_dict

if __name__ == "__main__":
    api= BiclooAPI()
    print("=== Récupération des stations ===")
    stations = register_stations(api)
    print(f"Nombre de stations récupérées: {len(stations)}")
    print("\n=== Récupération des vélos ===")
    bikes = register_bikes(api)
    print(f"Nombre de vélos récupérés: {len(bikes)}")

