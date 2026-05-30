# =============================================================================
# Gestion des fuseaux horaires — frontière UTC ↔ Europe/Paris
# =============================================================================
#
# Convention du projet :
#   - Stockage SQLite : timestamps NAÏFS interprétés comme UTC, format
#     'YYYY-MM-DD HH:MM:SS[.ffffff]'. Sans tzinfo dans la string, pour
#     compatibilité avec la comparaison lexicographique des index existants.
#   - Interface utilisateur (CLI, noms de fichiers clean_YYYY-MM-DD.sql,
#     affichage) : heure locale Paris, DST géré automatiquement par zoneinfo.
#   - Toute conversion se fait via ce module, aux frontières (parsing args,
#     queries SQL, agrégation par heure-du-jour).
#
# Pourquoi pas tout en local : `datetime.now()` naïf est piégeux (DST → heure
# qui saute ou se répète), et la machine de scrap peut ne pas être en
# Europe/Paris. UTC est monotone et indépendant du fuseau machine.
# =============================================================================

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Paris")
UTC_TZ = timezone.utc


def now_utc_naive() -> datetime:
    """Instant courant en UTC, sans tzinfo. À utiliser pour les écritures DB."""
    return datetime.now(UTC_TZ).replace(tzinfo=None)


def local_to_utc_naive(local_dt: datetime) -> datetime:
    """Naïf interprété comme heure locale Paris → UTC naïf."""
    return local_dt.replace(tzinfo=LOCAL_TZ).astimezone(UTC_TZ).replace(tzinfo=None)


def utc_naive_to_local(utc_dt: datetime) -> datetime:
    """Naïf interprété comme UTC → heure locale Paris (naïf)."""
    return utc_dt.replace(tzinfo=UTC_TZ).astimezone(LOCAL_TZ).replace(tzinfo=None)


def local_day_bounds_utc(jour: date) -> tuple[datetime, datetime]:
    """Bornes UTC naïves de la journée locale Paris `jour`.

    Renvoie (start, end) tels que `start <= t < end` capture exactement les
    instants UTC dont la projection en Europe/Paris tombe le jour `jour`.
    En hiver la fenêtre fait 24 h, mais aux passages DST elle fait 23 h ou 25 h.
    """
    start_local = datetime(jour.year, jour.month, jour.day)
    end_local = start_local + timedelta(days=1)
    return local_to_utc_naive(start_local), local_to_utc_naive(end_local)
