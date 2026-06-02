import os
import logging
import tempfile
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from pdf2image import convert_from_path

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Envie um arquivo PDF e eu vou converter cada página em imagem para você. 📄➡️🖼️"
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document

    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Por favor, envie um arquivo PDF.")
        return

    await update.message.reply_text("Recebi o PDF! Convertendo as páginas... ⏳")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Baixar o arquivo
        tg_file = await context.bot.get_file(doc.file_id)
        pdf_path = Path(tmpdir) / "arquivo.pdf"
        await tg_file.download_to_drive(pdf_path)

        # Converter para imagens
        try:
            images = convert_from_path(str(pdf_path), dpi=150, fmt="png")
        except Exception as e:
            logger.error(f"Erro ao converter PDF: {e}")
            await update.message.reply_text(
                "Não consegui converter o PDF. Verifique se o arquivo não está corrompido."
            )
            return

        total = len(images)
        if total == 0:
            await update.message.reply_text("O PDF parece estar vazio.")
            return

        await update.message.reply_text(f"Total de páginas: {total}. Enviando...")

        for i, img in enumerate(images, start=1):
            img_path = Path(tmpdir) / f"pagina_{i:03d}.png"
            img.save(str(img_path), "PNG")

            with open(img_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=f,
                    caption=f"Página {i}/{total}",
                )

        await update.message.reply_text("✅ Conversão concluída!")


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
    app.run_polling()


if __name__ == "__main__":
    main()
