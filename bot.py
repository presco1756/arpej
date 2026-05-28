"""
bot.py — Bot Telegram ARPEJ Monitor.

Commandes :
  /start  → s'abonner aux alertes automatiques
  /stop   → se désabonner
  /dispo  → voir les dispos maintenant
  /help   → aide

Le bot vérifie ibail.arpej.fr toutes les CHECK_INTERVAL_MIN minutes.
Si de nouvelles places apparaissent en IDF (profil étudiant/apprenti/jeune actif),
tous les abonnés reçoivent une alerte.
"""

import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import scraper
import state

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "15"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_residence_list(residences: list) -> str:
    if not residences:
        return "Aucune résidence disponible pour ton profil en ce moment. 😴"
    lines = [f"🔎 <b>{len(residences)} résidence(s) disponible(s)</b> :\n"]
    for r in residences:
        lines.append(r.telegram_msg())
        lines.append("")  # ligne vide entre chaque
    lines.append(
        f"<i>Mis à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i>"
    )
    return "\n".join(lines)


async def _send_to_all(app: Application, message: str) -> None:
    subscribers = state.get_subscribers()
    if not subscribers:
        logger.info("Aucun abonné, pas d'envoi.")
        return
    for chat_id in subscribers:
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning("Impossible d'envoyer à %s : %s", chat_id, e)


# ── Job planifié ─────────────────────────────────────────────────────────────

async def job_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Vérifie les disponibilités et alerte si nouvelles places."""
    logger.info("▶ Check planifié...")
    try:
        residences = scraper.fetch_disponibles()
    except Exception as e:
        logger.error("Erreur scraping : %s", e)
        return

    nouvelles, disparues = state.compute_diff(residences)
    state.save_seen(residences)

    if not nouvelles:
        logger.info("Pas de nouvelles disponibilités.")
        return

    logger.info("%d nouvelle(s) résidence(s) !", len(nouvelles))

    msg_lines = ["🚨 <b>Nouvelles places disponibles !</b>\n"]
    for r in nouvelles:
        msg_lines.append(r.telegram_msg())
        msg_lines.append("")
    msg_lines.append(
        f"<i>Alerte du {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i>"
    )

    await _send_to_all(context.application, "\n".join(msg_lines))


# ── Commandes ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    added = state.add_subscriber(chat_id)

    if added:
        await update.message.reply_text(
            "✅ <b>Abonnement activé !</b>\n\n"
            "Tu recevras une alerte dès qu'une nouvelle place se libère "
            "dans une résidence ARPEJ en <b>Île-de-France</b> "
            "(profil : étudiant, apprenti, jeune actif).\n\n"
            "📋 Commandes :\n"
            "/dispo — voir les places disponibles maintenant\n"
            "/stop — se désabonner\n"
            "/help — aide",
            parse_mode=ParseMode.HTML,
        )
        # Envoi immédiat des dispos actuelles
        await _send_current_dispo(update)
    else:
        await update.message.reply_text(
            "Tu es déjà abonné(e) ! 👍\n"
            "Utilise /dispo pour voir les places actuelles.",
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    removed = state.remove_subscriber(chat_id)
    if removed:
        await update.message.reply_text(
            "🛑 Désabonné(e). Tu ne recevras plus d'alertes.\n"
            "Reviens avec /start quand tu veux !"
        )
    else:
        await update.message.reply_text(
            "Tu n'étais pas abonné(e). Utilise /start pour commencer."
        )


async def cmd_dispo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Je vérifie en temps réel…")
    await _send_current_dispo(update)


async def _send_current_dispo(update: Update) -> None:
    try:
        residences = scraper.fetch_disponibles()
        state.save_seen(residences)
    except Exception as e:
        await update.message.reply_text(
            f"❌ Erreur lors de la vérification : {e}\nRéessaie dans quelques minutes."
        )
        return

    msg = _format_residence_list(residences)
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 <b>ARPEJ Monitor — Aide</b>\n\n"
        "Ce bot surveille les disponibilités ARPEJ en <b>Île-de-France</b> "
        "pour les profils : étudiant, apprenti / alternant, jeune actif.\n\n"
        "<b>Commandes :</b>\n"
        "/start — activer les alertes automatiques\n"
        "/dispo — vérifier les disponibilités maintenant\n"
        "/stop — désactiver les alertes\n"
        "/help — afficher cette aide\n\n"
        f"<i>Vérification toutes les {CHECK_INTERVAL_MIN} minutes.</i>\n"
        "<i>Seules les résidences avec bouton 'Réserver' sont remontées "
        "(les résidences réservataires n'apparaissent pas).</i>",
        parse_mode=ParseMode.HTML,
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commandes
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("dispo", cmd_dispo))
    app.add_handler(CommandHandler("help", cmd_help))

    # Job planifié
    job_queue = app.job_queue
    job_queue.run_repeating(
        job_check,
        interval=CHECK_INTERVAL_MIN * 60,
        first=30,  # premier run 30s après le démarrage
        name="arpej_check",
    )

    logger.info(
        "🤖 Bot démarré — vérification toutes les %d minutes.", CHECK_INTERVAL_MIN
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
