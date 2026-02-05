import time

import requests
from typing import Dict, List, Optional, Any


class API:
    """Classe pour gérer les appels à l'API Bicloo"""

    TOKEN_EXPIRES_IN = 30*60

    def __init__(self):
        self.base_url = "https://api.cyclocity.fr/contracts/nantes"
        self.jcd_url = "https://api.jcdecaux.com/vls/v3"
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
        self.access_token_expires_at = time.monotonic() + API.TOKEN_EXPIRES_IN

        return True

    def get_jcd(self, endpoint: str) -> Any:
        """Effectue une requête GET à l'API JCDecaux"""
        url = f"{self.jcd_url}/{endpoint}?apiKey=frifk0jbxfefqqniqez09tw4jvk37wyf823b5j1i&contract=nantes"
        response = requests.get(url)
        if response.status_code != 200:
            print("Response:", response.status_code, response.text)
            raise Exception(f"Erreur lors de la requête à l'endpoint {endpoint}")
        return response.json()

    def get_bicloo(self, endpoint: str, contentType : Optional[str] = None) -> Any:
        """Effectue une requête GET à l'API Bicloo"""
        url = f"{self.base_url}/{endpoint}"

        if not self.access_token or self.access_token_expires_at < time.monotonic():
            if not self.generate_token():
                raise Exception("Erreur lors de la récupération des headers")

        response = requests.get(url, headers={
            'Authorization': f'Taknv1 {self.access_token}',
            "Content-Type": contentType if contentType else "application/json",
            'Accept': '*/*'
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

def get_stations(api: API) -> list[Any]:
    return api.get_jcd("stations")

def get_bikes(api: API, station_number: int | None = None) -> list[Any]:
    endpoint="bikes" if station_number is None else f"bikes?stationNumber={station_number}"
    # One bike format in the list: {'id': '1d8c4358-0983-430d-a5bd-c860bfbc39b3', 'number': 51466, 'contractName': 'nantes', 'type': 'ELECTRICAL', 'frameId': 'NS101', 'status': 'NOT_RECOGNIZED', 'statusLabel': 'Non reconnu', 'hasBattery': True, 'battery': {'percentage': 0, 'level': 0}, 'hasLock': False, 'rating': {'count': 0}, 'checked': True, 'createdAt': '2025-04-17T13:43:46.651833', 'updatedAt': '2025-10-29T19:30:27.362569', 'isReserved': False, 'energySource': 1}
    return api.get_bicloo(endpoint, "application/vnd.bikes.v4+json")