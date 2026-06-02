# PDF Bot — Telegram

Bot que recebe PDFs e devolve cada página como imagem PNG.

## Estrutura

```
pdf_bot/
├── bot.py            # código principal
├── requirements.txt  # dependências Python
├── Procfile          # processo para Railway
├── nixpacks.toml     # instala poppler (necessário para pdf2image)
└── README.md
```

## Deploy no Railway

### 1. Suba o projeto para o GitHub

Crie um repositório no GitHub e envie esta pasta:

```bash
git init
git add .
git commit -m "primeiro commit"
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

### 2. Crie o projeto no Railway

1. Acesse [railway.app](https://railway.app) e faça login
2. Clique em **New Project → Deploy from GitHub repo**
3. Selecione o repositório criado

### 3. Configure a variável de ambiente

No painel do Railway, vá em **Variables** e adicione:

| Variável    | Valor                        |
|-------------|------------------------------|
| `BOT_TOKEN` | o token do seu BotFather     |

### 4. Deploy

O Railway detecta o `Procfile` automaticamente e sobe o bot como **worker** (sem porta HTTP — correto para bots com polling).

## Testando localmente

```bash
pip install -r requirements.txt
export BOT_TOKEN="seu_token_aqui"
python bot.py
```

> Necessário ter o **poppler** instalado localmente:
> - Ubuntu/Debian: `sudo apt install poppler-utils`
> - Mac: `brew install poppler`

## Limites do Telegram

- Arquivos até **20 MB** via `getFile` (limite da API gratuita do Telegram)
- Imagens enviadas até **10 MB** por foto
- PDFs com muitas páginas podem demorar — o bot avisa o progresso
