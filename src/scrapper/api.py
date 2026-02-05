import time
import logging

import requests
from typing import Optional, Any

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retry with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Request failed after {max_retries} attempts: {e}")
            raise last_exception
        return wrapper
    return decorator


class API:
    """Classe pour gérer les appels à l'API Bicloo"""

    TOKEN_EXPIRES_IN = 30 * 60

    def __init__(self):
        self.base_url = "https://api.cyclocity.fr/contracts/nantes"
        self.auth_url = "https://api.cyclocity.fr/auth/environments/PRD/client_tokens"
        self.access_token = None
        self.access_token_expires_at = None

    def generate_token(self) -> bool:
        """Génère un token d'accès pour l'API"""
        payload = {
            "code": "vls.web.nantes:PRD",
            "key": "d7d30faca33532872541d2bb4b9f703d05bed3fb6106fdce3eb05913331901d1"
        }
        response = requests.post(self.auth_url, json=payload, timeout=30)
        if response.status_code != 200:
            logger.warning(f"Token generation failed: {response.status_code}")
            return False

        data = response.json()
        self.access_token = data.get('accessToken')
        self.access_token_expires_at = time.monotonic() + API.TOKEN_EXPIRES_IN
        return True

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def get(self, endpoint: str, content_type: Optional[str] = None) -> Any:
        """Effectue une requête GET à l'API Bicloo"""
        url = f"{self.base_url}/{endpoint}"

        if not self.access_token or self.access_token_expires_at < time.monotonic():
            if not self.generate_token():
                raise requests.exceptions.RequestException("Erreur génération token")

        response = requests.get(url, headers={
            'Authorization': f'Taknv1 {self.access_token}',
            'Content-Type': content_type or 'application/json',
            'Accept': '*/*'
        }, timeout=30)

        if response.status_code != 200:
            logger.warning(f"API error: {response.status_code} {response.text}")
            raise requests.exceptions.RequestException(f"Erreur endpoint {endpoint}")

        return response.json()


def get_stations(api: API) -> list[dict]:
    """Récupère les infos stations (pour init)"""
    return api.get("stations")


def get_station_status(api: API) -> list[dict]:
    """Récupère le status temps réel des stations"""
    data = api.get("gbfs/v3/station_status.json")
    return data['data']['stations']


def get_bikes(api: API, station_number: int | None = None) -> list[dict]:
    """Récupère les vélos (optionnel: par station)"""
    endpoint = "bikes" if station_number is None else f"bikes?stationNumber={station_number}"
    return api.get(endpoint, "application/vnd.bikes.v4+json")
