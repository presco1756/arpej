# 🏠 ARPEJ Monitor Bot

Bot Telegram qui surveille les disponibilités ARPEJ en **Île-de-France**
pour les profils : étudiant, apprenti / alternant, jeune actif.

> Seules les résidences avec un bouton "Réserver" public sont remontées.
> Les résidences réservataires (partenaires uniquement) n'apparaissent
> pas dans la liste publique d'ibail.arpej.fr — elles sont donc
> automatiquement exclues.

---

## 1. Créer le bot Telegram

1. Ouvre Telegram, cherche **@BotFather**
2. Envoie `/newbot`
3. Choisis un nom, puis un username (ex: `arpej_monitor_bot`)
4. Copie le **token** donné (ex: `123456789:ABCdef...`)

---

## 2. Configuration

```bash
cp .env.example .env
# Édite .env et mets ton TELEGRAM_TOKEN
```

---

## 3. Lancement

### Option A — En local (dev / test)

```bash
pip install -r requirements.txt
python bot.py
```

### Option B — Docker (recommandé pour laisser tourner)

```bash
docker build -t arpej-bot .
docker run -d --name arpej-bot --restart always \
  -v $(pwd)/state.json:/app/state.json \
  --env-file .env \
  arpej-bot
```

### Option C — Railway.app

1. Crée un compte sur [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo
3. Dans l'onglet Variables, ajoute :

```bash
TELEGRAM_TOKEN=ton_token_botfather
CHECK_INTERVAL_MIN=15
```

4. Déploie le service. Railway utilisera le `Dockerfile` via `railway.json`.

Pour garder les abonnés après un redémarrage ou un redéploiement, ajoute un
Volume Railway monté sur `/data`, puis ajoute aussi :

```bash
STATE_FILE=/data/state.json
```

Sans volume, le bot fonctionne, mais `state.json` est recréé après chaque
redémarrage de l'instance.

### Option D — Sur un serveur / VPS

```bash
# Avec screen pour garder actif après déconnexion SSH
screen -S arpej-bot
python bot.py
# Ctrl+A puis D pour détacher
```

---

## 4. Utilisation du bot

| Commande | Description |
|----------|-------------|
| `/start` | S'abonner aux alertes + voir les dispos actuelles |
| `/dispo` | Vérifier les disponibilités maintenant |
| `/stop`  | Se désabonner des alertes |
| `/help`  | Aide |

---

## 5. Debug / Ajustements

Si tu veux vérifier ce que le scraper voit exactement :

```python
# test_scraper.py
from scraper import fetch_disponibles
residences = fetch_disponibles(debug=True)
for r in residences:
    print(r.nom, r.ville, r.places, r.ibail_url)
```

Si des résidences réservataires passent quand même :
→ Ouvre leur page ibail (ibail.arpej.fr/residences/ID) et cherche
  le texte ou CSS class qui les distingue, puis ajoute un filtre
  dans `scraper.py > fetch_disponibles()`.

---

## Structure des fichiers

```
arpej-bot/
├── bot.py          # Bot Telegram (commandes + scheduler)
├── scraper.py      # Scraping ibail.arpej.fr
├── state.py        # Persistance JSON (abonnés + dernier état)
├── requirements.txt
├── Dockerfile
├── .env.example
└── state.json      # Créé automatiquement au premier run
```
