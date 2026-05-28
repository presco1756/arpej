"""
scraper.py — Scrape ibail.arpej.fr pour les résidences disponibles en IDF.

Logique réservataires :
  - Les résidences réservataires (partenaires uniquement) n'ont PAS de bouton
    "Réserver (X)" sur la liste publique d'ibail.arpej.fr.
  - On ne scrape que les résidences avec ce bouton → elles sont toutes
    bookables publiquement (non-réservataires).

Logique profil :
  - Inclut : étudiant, apprenti/alternant, jeune actif, généralistes
  - Exclut : résidences réservées aux chercheurs uniquement
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)

IBAIL_URL = "https://ibail.arpej.fr/residences/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Départements Île-de-France
IDF_DEPARTMENTS = {"75", "77", "78", "91", "92", "93", "94", "95"}

# Mots-clés à exclure (résidences chercheurs uniquement)
EXCLUDE_KEYWORDS = ["chercheur", "chercheurs", "researcher", "internat"]


@dataclass
class Residence:
    nom: str
    ville: str
    dept: str
    places: int
    ibail_url: str

    @property
    def uid(self) -> str:
        """ID stable pour le diff (numéro ibail)."""
        parts = self.ibail_url.rstrip("/").split("/")
        return parts[-1] if parts else self.ibail_url

    def to_dict(self) -> dict:
        return {
            "nom": self.nom,
            "ville": self.ville,
            "dept": self.dept,
            "places": self.places,
            "ibail_url": self.ibail_url,
        }

    def telegram_msg(self) -> str:
        emoji = _profile_emoji(self.nom)
        return (
            f"{emoji} <b>{self.nom}</b>\n"
            f"📍 {self.ville} — dép. <b>{self.dept}</b>\n"
            f"🛏 <b>{self.places}</b> place(s) disponible(s)\n"
            f'🔗 <a href="{self.ibail_url}">Voir &amp; postuler</a>'
        )


def _profile_emoji(nom: str) -> str:
    nom_l = nom.lower()
    if any(k in nom_l for k in ["jeune actif", "jeunes actifs"]):
        return "💼"
    if any(k in nom_l for k in ["apprenti", "alternant"]):
        return "🔧"
    return "🎓"


def _is_excluded(nom: str) -> bool:
    nom_l = nom.lower()
    return any(kw in nom_l for kw in EXCLUDE_KEYWORDS)


def fetch_disponibles(debug: bool = False) -> list[Residence]:
    """
    Retourne la liste des résidences IDF disponibles, filtrées par profil.
    Raises requests.RequestException en cas d'erreur réseau.
    """
    session = requests.Session()
    resp = session.get(IBAIL_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    if debug:
        print("=== HTML BRUT (premiers 1000 chars) ===")
        print(resp.text[:1000])
        print("=== FIN DEBUG ===\n")

    residences: list[Residence] = []

    # Parcours séquentiel de tous les éléments pertinents
    current_dept: str | None = None
    current_nom: str = ""
    current_ville: str = ""

    for el in soup.find_all(["h2", "h3", "p", "a", "div", "span", "li"]):
        text = el.get_text(strip=True)
        if not text:
            continue

        # ── Département ────────────────────────────────────────────
        if el.name == "h2":
            m = re.match(r"^(\d{2,3})\s*[\(\[]", text)
            if m:
                current_dept = m.group(1)
            continue

        # ── Nom de résidence ───────────────────────────────────────
        if el.name == "h3":
            current_nom = text
            current_ville = ""  # reset ville pour ce nouveau bloc
            continue

        # ── Ville (code postal suivi d'un nom de ville) ────────────
        if re.match(r"^\d{5}\s+\w", text) and el.name in ("p", "div", "span", "li"):
            # Nettoyer les icônes éventuelles (🔓🔒 ou SVG convertis)
            clean = re.sub(r"[🔓🔒🔐🔑]", "", text).strip()
            current_ville = clean
            continue

        # ── Lien Réserver ──────────────────────────────────────────
        if el.name == "a":
            m_places = re.search(r"[Rr]éserver\s*\((\d+)\)", text)
            if not m_places:
                continue
            if current_dept not in IDF_DEPARTMENTS:
                continue

            places = int(m_places.group(1))
            href = el.get("href", "")
            if not href:
                continue
            ibail_url = (
                href if href.startswith("http")
                else f"https://ibail.arpej.fr{href}"
            )

            # Filtre profil
            if _is_excluded(current_nom):
                logger.debug("Exclu (profil) : %s", current_nom)
                continue

            res = Residence(
                nom=current_nom or "Résidence inconnue",
                ville=current_ville or f"Dép. {current_dept}",
                dept=current_dept,
                places=places,
                ibail_url=ibail_url,
            )
            residences.append(res)
            logger.debug(
                "✅ Trouvée : %s — %d place(s) [%s]",
                res.nom, res.places, res.ibail_url
            )

    logger.info(
        "%d résidence(s) IDF disponibles à %s",
        len(residences),
        datetime.now().strftime("%H:%M"),
    )
    return residences
