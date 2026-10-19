from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import uuid
import shutil
import dns_doh

# Algumas redes bloqueiam o DNS do YouTube; usa DNS sobre HTTPS como alternativa
dns_doh.enable()

app = Flask(__name__)

BASE_DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

# Remove pastas temporárias que sobraram de execuções anteriores
# (ex: servidor encerrado no meio de um download)
for name in os.listdir(BASE_DOWNLOAD_DIR):
    path = os.path.join(BASE_DOWNLOAD_DIR, name)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)

# Opções do yt-dlp específicas de cada formato
FORMATS = {
    'mp3': {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # O client "android" evita a exigência de PO token, que causa
        # "HTTP Error 403: Forbidden" no client "web"
        'extractor_args': {'youtube': {'player_client': ['android']}},
    },
    'mp4': {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'merge_output_format': 'mp4',
        'extractor_args': {'youtube': {'player_client': ['mweb']}},
    },
}


def close_then_cleanup(body, folder):
    """Repassa o arquivo e apaga a pasta assim que o envio termina ou é interrompido."""
    try:
        yield from body
    finally:
        body.close()
        shutil.rmtree(folder, ignore_errors=True)


@app.route('/')
def index():
    return render_template('index.html', message=None, selected_format='mp3')


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url', '').strip()
    fmt = request.form.get('format', 'mp3')
    if fmt not in FORMATS:
        fmt = 'mp3'

    if not url:
        return render_template(
            'index.html',
            message="Por favor, insira uma URL válida.",
            selected_format=fmt
        )

    # Pasta temporária única por requisição, evita conflito entre downloads simultâneos
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(BASE_DOWNLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    ydl_opts = {
        **FORMATS[fmt],
        'outtmpl': os.path.join(session_dir, '%(title)s.%(ext)s'),
        # Link de vídeo dentro de playlist baixa só o vídeo;
        # link de playlist pura baixa só o primeiro item
        'noplaylist': True,
        'playlist_items': '1',
        'keepvideo': False,
        'ffmpeg_location': r'C:\ffmpeg\bin\ffmpeg.exe',
        # Runtime JavaScript e script solver para os desafios do YouTube
        # (sem eles o download falha com "This video is not available")
        'js_runtimes': {'deno': {}},
        'remote_components': ['ejs:github'],
        'quiet': False,
        'noprogress': False,
    }

    try:
        print(f"Iniciando download ({fmt}): {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'entries' in info:
                info = info['entries'][0]
            filename = ydl.prepare_filename(info)
            # A conversão (mp3) ou o merge (mp4) mudam a extensão final
            file_path = os.path.splitext(filename)[0] + '.' + fmt

        if not os.path.exists(file_path):
            raise FileNotFoundError("Arquivo não encontrado após o download.")

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )
        # after_this_request não serve aqui: ele roda com o arquivo ainda
        # aberto, e no Windows não dá pra apagar arquivo aberto
        response.response = close_then_cleanup(response.response, session_dir)
        return response

    except Exception as e:
        print(f"ERRO: {e}")
        shutil.rmtree(session_dir, ignore_errors=True)
        return render_template(
            'index.html',
            message=f"Ocorreu um erro durante o download: {str(e)}",
            selected_format=fmt
        )


if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001
    )
