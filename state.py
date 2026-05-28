"""
state.py — Gestion de l'état persistant du bot (JSON).

Stocke :
  - Les résidences vues au dernier run (pour le diff)
  - Les chat_ids abonnés aux alertes
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))

_DEFAULT_STATE = {
    "last_seen": {},    # uid -> {nom, ville, dept, places, ibail_url}
    "subscribers": [],  # liste de chat_ids (int)
}


def _load() -> dict:
    if not STATE_FILE.exists():
        return _DEFAULT_STATE.copy()
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Impossible de lire state.json: %s", e)
        return _DEFAULT_STATE.copy()


def _save(state: dict) -> None:
    try:
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.error("Impossible d'écrire state.json: %s", e)


# ── Résidences ──────────────────────────────────────────────────────────────

def get_last_seen() -> dict:
    """Retourne {uid: residence_dict} du dernier run."""
    return _load().get("last_seen", {})


def save_seen(residences: list) -> None:
    """Met à jour la liste des résidences vues."""
    state = _load()
    state["last_seen"] = {r.uid: r.to_dict() for r in residences}
    _save(state)


def compute_diff(new_residences: list) -> tuple[list, list]:
    """
    Compare les nouvelles résidences avec l'état précédent.

    Retourne (nouvelles, disparues) où :
    - nouvelles : résidences avec de nouvelles places (pas vues avant, ou +de places)
    - disparues : résidences qui n'ont plus de places
    """
    prev = get_last_seen()
    new_map = {r.uid: r for r in new_residences}

    nouvelles = []
    for uid, res in new_map.items():
        if uid not in prev:
            nouvelles.append(res)  # nouvelle résidence dispo
        elif res.places > prev[uid].get("places", 0):
            nouvelles.append(res)  # plus de places qu'avant

    disparues = [
        prev[uid] for uid in prev
        if uid not in new_map
    ]

    return nouvelles, disparues


# ── Abonnés ─────────────────────────────────────────────────────────────────

def get_subscribers() -> list[int]:
    return _load().get("subscribers", [])


def add_subscriber(chat_id: int) -> bool:
    """Ajoute un abonné. Retourne True si ajouté, False si déjà présent."""
    state = _load()
    subs = state.get("subscribers", [])
    if chat_id in subs:
        return False
    subs.append(chat_id)
    state["subscribers"] = subs
    _save(state)
    return True


def remove_subscriber(chat_id: int) -> bool:
    """Supprime un abonné. Retourne True si supprimé."""
    state = _load()
    subs = state.get("subscribers", [])
    if chat_id not in subs:
        return False
    state["subscribers"] = [s for s in subs if s != chat_id]
    _save(state)
    return True
