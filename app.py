from flask import Flask, render_template, request
import yt_dlp
import os

app = Flask(__name__)

# Cria a pasta downloads caso ela não exista
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html', message=None)


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url', '').strip()

    if not url:
        return render_template(
            'index.html',
            message="Por favor, insira uma URL válida."
        )

    ydl_opts = {
        # Melhor qualidade de áudio disponível
        'format': 'bestaudio/best',

        # Converter para MP3
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],

        # Local onde será salvo
        'outtmpl': os.path.join(
            DOWNLOAD_DIR,
            '%(title)s.%(ext)s'
        ),

        # Não manter o arquivo original
        'keepvideo': False,

        # O yt-dlp localiza o FFmpeg automaticamente pelo PATH do sistema.
        # Certifique-se de que o FFmpeg está instalado e adicionado ao PATH
        # (veja instruções no README.md).

        # Runtime JavaScript usado para resolver os desafios do YouTube
        'js_runtimes': {
            'deno': {}
        },

        # Necessário para baixar o script solver do challenge JS (n challenge).
        # Sem isso, o yt-dlp não resolve o desafio e o download falha com
        # "This video is not available".
        'remote_components': ['ejs:github'],

        # Força o client "android" do YouTube. Isso evita a exigência de
        # PO token (que depende do servidor bgutil rodando em segundo
        # plano) e resolve o erro "HTTP Error 403: Forbidden" que ocorre
        # quando o client "web" tenta baixar sem um token válido.
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
            }
        },

        # Evita mensagens excessivas
        'quiet': False,

        # Mostra progresso
        'noprogress': False,
    }

    try:
        print(f"Iniciando download: {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        message = "Download concluído com sucesso!"

    except Exception as e:
        print(f"ERRO: {e}")

        message = f"Ocorreu um erro durante o download: {str(e)}"

    return render_template(
        'index.html',
        message=message
    )


if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001
    )
