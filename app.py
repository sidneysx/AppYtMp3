from flask import Flask, render_template, request, send_file, jsonify, abort
from yt_dlp.postprocessor import PostProcessor
import yt_dlp
import os
import uuid
import shutil
import threading
import time
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

# Quantos downloads rodam ao mesmo tempo; os demais esperam na fila
MAX_SIMULTANEOUS = 3
download_slots = threading.Semaphore(MAX_SIMULTANEOUS)

# Arquivo pronto que ninguém buscou (ex: aba fechada) é apagado depois disso
JOB_EXPIRATION = 30 * 60

# Downloads por id. O download roda em segundo plano; o navegador acompanha
# por /progress/<id> e busca o arquivo em /file/<id> quando fica pronto.
# Assim nenhuma requisição demora, o que evita o erro 524 do Cloudflare
# (ele derruba respostas que levam mais de 100 segundos).
jobs = {}
jobs_lock = threading.Lock()


class PartSizesPP(PostProcessor):
    """Roda antes do download. No MP4 o vídeo e o áudio vêm em partes separadas,
    e o tamanho de cada uma define quanto ela vale na % total."""

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self, info):
        parts = info.get('requested_formats') or [info]
        sizes = [p.get('filesize') or p.get('filesize_approx') for p in parts]
        if all(sizes):
            self.job['weights'] = [size / sum(sizes) for size in sizes]
        else:
            self.job['weights'] = [1 / len(parts)] * len(parts)
        return [], info


def on_download_progress(job, d):
    if d['status'] not in ('downloading', 'finished'):
        return

    # Fração baixada de cada parte, na ordem em que foram baixadas
    parts = job['parts']
    total = d.get('total_bytes') or d.get('total_bytes_estimate')
    if d['status'] == 'finished':
        parts[d['filename']] = 1.0
    elif total:
        parts[d['filename']] = min(d.get('downloaded_bytes', 0) / total, 1.0)
    else:
        parts.setdefault(d['filename'], 0.0)

    job['stage'] = 'baixando'
    job['percent'] = int(100 * sum(w * f for w, f in zip(job['weights'], parts.values())))


def on_postprocess(job, d):
    # Conversão para MP3 ou junção do vídeo com o áudio no MP4
    if d['status'] == 'started' and d['postprocessor'] in ('ExtractAudio', 'Merger'):
        job['stage'] = 'convertendo'


def run_download(job, url, fmt):
    ydl_opts = {
        **FORMATS[fmt],
        'outtmpl': os.path.join(job['dir'], '%(title)s.%(ext)s'),
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
        'progress_hooks': [lambda d: on_download_progress(job, d)],
        'postprocessor_hooks': [lambda d: on_postprocess(job, d)],
        'quiet': False,
        'noprogress': False,
    }

    try:
        with download_slots:
            job['stage'] = 'preparando'
            print(f"Iniciando download ({fmt}): {url}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.add_post_processor(PartSizesPP(job), when='before_dl')
                info = ydl.extract_info(url, download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                filename = ydl.prepare_filename(info)
                # A conversão (mp3) ou o merge (mp4) mudam a extensão final
                file_path = os.path.splitext(filename)[0] + '.' + fmt

        if not os.path.exists(file_path):
            raise FileNotFoundError("Arquivo não encontrado após o download.")

        job['file'] = file_path
        job['percent'] = 100
        job['stage'] = 'pronto'

    except Exception as e:
        print(f"ERRO: {e}")
        shutil.rmtree(job['dir'], ignore_errors=True)
        job['error'] = f"Ocorreu um erro durante o download: {str(e)}"
        job['stage'] = 'erro'

    job['finished_at'] = time.monotonic()


def remove_expired_jobs():
    now = time.monotonic()
    with jobs_lock:
        expired = [
            job_id for job_id, job in jobs.items()
            if job['finished_at'] and now - job['finished_at'] > JOB_EXPIRATION
        ]
        for job_id in expired:
            shutil.rmtree(jobs.pop(job_id)['dir'], ignore_errors=True)


def close_then_cleanup(body, folder):
    """Repassa o arquivo e apaga a pasta assim que o envio termina ou é interrompido."""
    try:
        yield from body
    finally:
        body.close()
        shutil.rmtree(folder, ignore_errors=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url', '').strip()
    fmt = request.form.get('format', 'mp3')
    if fmt not in FORMATS:
        fmt = 'mp3'

    if not url:
        return jsonify(error="Por favor, insira uma URL válida."), 400

    remove_expired_jobs()

    # Pasta temporária única por download, evita conflito entre downloads simultâneos
    job_id = str(uuid.uuid4())
    session_dir = os.path.join(BASE_DOWNLOAD_DIR, job_id)
    os.makedirs(session_dir, exist_ok=True)

    job = {
        'stage': 'fila',  # fila -> preparando -> baixando -> convertendo -> pronto | erro
        'percent': 0,
        'weights': [1.0],
        'parts': {},
        'dir': session_dir,
        'file': None,
        'error': None,
        'finished_at': None,
    }
    with jobs_lock:
        jobs[job_id] = job

    threading.Thread(target=run_download, args=(job, url, fmt), daemon=True).start()
    return jsonify(id=job_id)


@app.route('/progress/<job_id>')
def progress(job_id):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    return jsonify(stage=job['stage'], percent=job['percent'], error=job['error'])


@app.route('/file/<job_id>')
def download_file(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job['stage'] != 'pronto':
            abort(404)
        del jobs[job_id]

    response = send_file(
        job['file'],
        as_attachment=True,
        download_name=os.path.basename(job['file'])
    )
    # after_this_request não serve aqui: ele roda com o arquivo ainda
    # aberto, e no Windows não dá pra apagar arquivo aberto
    response.response = close_then_cleanup(response.response, job['dir'])
    return response


if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001
    )
