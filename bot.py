import os
import re
import logging
import tempfile
from pathlib import Path

import instaloader
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
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

COLLECTING = 0


# --- /start ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🖼️ Criar PDF com imagens", callback_data='criar_pdf')]]
    await update.message.reply_text(
        "Olá! Posso fazer três coisas:\n\n"
        "📄➡️🖼️ Envie um PDF e converto cada página em imagem.\n\n"
        "📸🎬 Envie um link do Instagram (foto, vídeo ou reel) e baixo o arquivo.\n\n"
        "🖼️➡️📄 Clique no botão abaixo para criar um PDF com suas imagens.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# --- Criar PDF com imagens ---

async def start_create_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['pdf_images'] = []
    await query.message.reply_text(
        "Envie as imagens, uma por uma.\n"
        "Quando terminar, envie /pronto.\n"
        "Para cancelar, envie /cancelar."
    )
    return COLLECTING


async def collect_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'pdf_images' not in context.user_data:
        context.user_data['pdf_images'] = []

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    else:
        file_id = update.message.document.file_id

    context.user_data['pdf_images'].append(file_id)
    count = len(context.user_data['pdf_images'])
    await update.message.reply_text(f"Imagem {count} recebida! ✅ Envie mais ou /pronto.")
    return COLLECTING


async def finish_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_ids = context.user_data.pop('pdf_images', [])

    if not file_ids:
        await update.message.reply_text("Nenhuma imagem foi enviada. Operação cancelada.")
        return ConversationHandler.END

    await update.message.reply_text(f"Criando PDF com {len(file_ids)} imagem(ns)... ⏳")

    with tempfile.TemporaryDirectory() as tmpdir:
        img_paths = []
        for i, file_id in enumerate(file_ids):
            tg_file = await context.bot.get_file(file_id)
            dest = Path(tmpdir) / f"img_{i:03d}"
            await tg_file.download_to_drive(dest)
            img_paths.append(dest)

        try:
            pil_images = [Image.open(p).convert('RGB') for p in img_paths]
            pdf_path = Path(tmpdir) / "resultado.pdf"
            pil_images[0].save(
                str(pdf_path),
                save_all=True,
                append_images=pil_images[1:],
            )
        except Exception as e:
            logger.error(f"Erro ao criar PDF: {e}")
            await update.message.reply_text("Erro ao criar o PDF. Tente novamente.")
            return ConversationHandler.END

        with open(pdf_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename="imagens.pdf",
            )

    await update.message.reply_text("✅ PDF criado e enviado!")
    return ConversationHandler.END


async def cancel_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('pdf_images', None)
    await update.message.reply_text("Criação de PDF cancelada.")
    return ConversationHandler.END


# --- Download do Instagram ---

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


# --- Converter PDF em imagens ---

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


# --- Main ---

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create_pdf, pattern='^criar_pdf$')],
        states={
            COLLECTING: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, collect_image),
                CommandHandler('pronto', finish_pdf),
            ]
        },
        fallbacks=[CommandHandler('cancelar', cancel_pdf)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
    app.run_polling()


if __name__ == "__main__":
    main()
