import os
import re
import logging
import tempfile
from pathlib import Path

import instaloader
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

INSTAGRAM_RE = re.compile(
    r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)'
)

VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Posso fazer duas coisas:\n\n"
        "📄➡️🖼️ Envie um PDF e converto cada página em imagem.\n\n"
        "📸🎬 Envie um link do Instagram (foto, vídeo ou reel) e baixo o arquivo para você."
    )


async def handle_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = INSTAGRAM_RE.search(text)
    if not match:
        return

    shortcode = match.group(1)
    await update.message.reply_text("Baixando do Instagram... ⏳")

    with tempfile.TemporaryDirectory() as tmpdir:
        loader = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern='',
        )

        try:
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            loader.download_post(post, target=Path(tmpdir))
        except Exception as e:
            logger.error(f"Erro ao baixar do Instagram: {e}")
            await update.message.reply_text(
                "Não consegui baixar o conteúdo. Verifique se o link é público e válido."
            )
            return

        media_exts = VIDEO_EXTS | IMAGE_EXTS
        media_files = sorted(
            f for f in Path(tmpdir).rglob('*')
            if f.is_file() and f.suffix.lower() in media_exts
        )

        if not media_files:
            await update.message.reply_text("Nenhum arquivo de mídia encontrado.")
            return

        for file_path in media_files:
            ext = file_path.suffix.lower()
            try:
                with open(file_path, 'rb') as f:
                    if ext in VIDEO_EXTS:
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=f,
                        )
                    else:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=f,
                        )
            except Exception as e:
                logger.error(f"Erro ao enviar {file_path.name}: {e}")
                await update.message.reply_text("Erro ao enviar o arquivo.")

        await update.message.reply_text("✅ Pronto!")


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document

    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Por favor, envie um arquivo PDF.")
        return

    await update.message.reply_text("Recebi o PDF! Convertendo as páginas... ⏳")

    with tempfile.TemporaryDirectory() as tmpdir:
        tg_file = await context.bot.get_file(doc.file_id)
        pdf_path = Path(tmpdir) / "arquivo.pdf"
        await tg_file.download_to_drive(pdf_path)

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
    app.run_polling()


if __name__ == "__main__":
    main()
