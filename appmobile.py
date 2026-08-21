from flask import Flask, render_template, request, send_file, after_this_request
import yt_dlp
import os
import uuid
import shutil

app = Flask(__name__)

BASE_DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)


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

    # Pasta temporária única por requisição, evita conflito entre downloads simultâneos
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(BASE_DOWNLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(session_dir, '%(title)s.%(ext)s'),
        'keepvideo': False,
        'ffmpeg_location': r'C:\ffmpeg\bin\ffmpeg.exe',
        'js_runtimes': {'deno': {}},
        'remote_components': ['ejs:github'],
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'quiet': False,
        'noprogress': False,
    }

    try:
        print(f"Iniciando download: {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Como o postprocessor converte pra mp3, a extensão final muda
            mp3_path = os.path.splitext(filename)[0] + '.mp3'

        if not os.path.exists(mp3_path):
            raise FileNotFoundError("Arquivo MP3 não encontrado após a conversão.")

        # Apaga a pasta temporária DEPOIS que o arquivo terminar de ser enviado
        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(session_dir, ignore_errors=True)
            except Exception as e:
                print(f"Erro ao limpar pasta temporária: {e}")
            return response

        return send_file(
            mp3_path,
            as_attachment=True,
            download_name=os.path.basename(mp3_path)
        )

    except Exception as e:
        print(f"ERRO: {e}")
        shutil.rmtree(session_dir, ignore_errors=True)
        return render_template(
            'index.html',
            message=f"Ocorreu um erro durante o download: {str(e)}"
        )


if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001
    )