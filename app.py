import select
import time
from flask import Flask, request, Response, jsonify, send_file, stream_with_context
import yt_dlp
import os, shutil
from mutagen.easyid3 import EasyID3
import mutagen.id3
import requests
import threading
import ffmpeg
from waitress import serve
import subprocess
import signal
from slugify import slugify
app = Flask(__name__, static_folder='./Webpage', static_url_path='')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))


@app.route('/')
def index():
    return app.send_static_file('index.html')

def probe_content_length(url, timeout=5):
    # Try HEAD first, fallback to GET with range zero if HEAD not supported
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        cl = r.headers.get('Content-Length')
        if cl:
            return int(cl)
    except Exception:
        pass
    # fallback: try a ranged GET for first byte
    try:
        r = requests.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=timeout)
        cl = r.headers.get('Content-Range')  # format: bytes 0-0/12345
        if cl and '/' in cl:
            total = cl.split('/', 1)[1]
            return int(total)
    except Exception:
        pass
    return None


@stream_with_context
def generate(proc):
    try:
        while True:
            chunk = proc.stdout.read(64*1024)
            if not chunk:
                break
            yield chunk
    except GeneratorExit:
        # client disconnected -> terminate ffmpeg
        try:
            proc.send_signal(signal.SIGTERM)
        except Exception:
            proc.kill()
        raise
    finally:
        try: proc.stdout.close()
        except: pass
        try: proc.kill()
        except: pass

@app.route('/stream_combine', methods=['POST'])
def stream_combine():
    data = request.json
    video_url = data.get('videoURL')
    audio_url = data.get('audioURL')
    filename = data.get('filename', 'output')

    if not video_url or not audio_url:
        return jsonify({"error": "videoURL and audioURL required"}), 400

    try:
        video_input = ffmpeg.input(video_url)
        audio_input = ffmpeg.input(audio_url)

        stream = ffmpeg.output(
            video_input.video,
            audio_input.audio,
            'pipe:1',
            c='copy',                                       # no re-encode
            movflags='frag_keyframe+empty_moov+faststart',
            f='mp4'
        )
        
        # Add global arguments
        stream = stream.global_args('-hide_banner', '-loglevel', 'error')

        proc = stream.run_async(pipe_stdout=True, pipe_stderr=True)

    except ffmpeg.Error as e:
        return jsonify({"error": "ffmpeg execution failed", "details": e.stderr.decode() if e.stderr else 'No details'}), 500

    safe_name = slugify(filename, True) + '.mp4'
    headers = {'Content-Disposition': f'attachment; filename="{safe_name}"'}
    return Response(generate(proc), mimetype='video/mp4', headers=headers)


@app.route('/fullformats', methods=['POST'])
def get_fullformats():
    data = request.json
    link = data['url']
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extractor_args': {'youtube': {'skip': ['dash', 'hls']}}
    }
    
    formats = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        for f in info['formats']:
            formats.append(f)
    
    return jsonify(formats)

@app.route('/info', methods=['POST'])
def get_info():
    data = request.json
    link = data['url']
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extractor_args': {'youtube': {'skip': ['dash', 'hls']}}
    }
    
    formats = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        formats.append(info)
            
    
    return jsonify(formats)

@app.route('/formats', methods=['POST'])
def get_formats():
    data = request.json
    link = data['url']
    return get_format(link)

def get_format(link):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extractor_args': {'youtube': {'skip': ['dash', 'hls']}}
    }
    
    formats = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        
        for f in info['formats']:
            if(f.get('format_note') == 'storyboard'):
                continue
            formats.append({
                    'codec': f.get('acodec', f.get('vcodec', f.get('acodec'))),
                    'format': f['format'],
                    'sampleRate': f.get('asr'),
                    'bitrate': f.get('abr'),
                    'extension': f['ext'],
                    'filesize': f.get('filesize', 0),
                    'url': f.get('url')
                })
    
    return jsonify({
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'formats': formats
    })

# Prepare API client

if __name__ == '__main__':
    port = 14032
    print(f"App has Started port {port}")
    serve(app, host="0.0.0.0", port=port)