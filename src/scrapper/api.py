import time
import logging

import requests

logger = logging.getLogger(__name__)


class API:
    """Classe pour gérer les appels à l'API Bicloo"""

    TOKEN_EXPIRES_IN = 30 * 60

    def __init__(self):
        self.base_url = "https://api.cyclocity.fr/contracts/nantes"
        self.auth_url = "https://api.cyclocity.fr/auth/environments/PRD/client_tokens"
        self.access_token = None
        self.token_expires_at = 0.0

    def _refresh_token(self):
        """Génère un token d'accès si expiré"""
        if self.access_token and time.monotonic() < self.token_expires_at:
            return
        payload = {
            "code": "vls.web.nantes:PRD",
            "key": "d7d30faca33532872541d2bb4b9f703d05bed3fb6106fdce3eb05913331901d1"
        }
        response = requests.post(self.auth_url, json=payload, timeout=30)
        response.raise_for_status()
        self.access_token = response.json()['accessToken']
        self.token_expires_at = time.monotonic() + self.TOKEN_EXPIRES_IN

    def get(self, endpoint: str, content_type: str = 'application/json'):
        """Effectue une requête GET à l'API Bicloo"""
        self._refresh_token()
        response = requests.get(
            f"{self.base_url}/{endpoint}",
            headers={
                'Authorization': f'Taknv1 {self.access_token}',
                'Content-Type': content_type,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def get_stations(api: API) -> list[dict]:
    return api.get("gbfs/v3/station_information.json")['data']['stations']


def get_station_status(api: API) -> list[dict]:
    return api.get("gbfs/v3/station_status.json")['data']['stations']


def get_bikes(api: API) -> list[dict]:
    return api.get("bikes", "application/vnd.bikes.v4+json")
