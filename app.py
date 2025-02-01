from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import threading
from pathlib import Path

app = Flask(__name__, static_folder='.', static_url_path='')
DOWNLOAD_FOLDER = 'downloads'
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

class DownloadTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.files = {}

    def add_file(self, url, filename):
        with self.lock:
            self.files[url] = filename

    def get_file(self, url):
        with self.lock:
            return self.files.get(url)

tracker = DownloadTracker()

def download_task(link, format_id, combine=False):
    ydl_opts = {
        'format': f'{format_id}' + ('+bestaudio' if combine else ''),
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'progress_hooks': [lambda d: tracker.add_file(link, d.get('filename'))],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            tracker.add_file(link, ydl.prepare_filename(info))
    except Exception as e:
        print(f"Download error: {str(e)}")

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/formats', methods=['POST'])
def get_formats():
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
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                formats.append({
                    'format_id': f['format_id'],
                    'resolution': f.get('format_note', f['ext']),
                    'extension': f['ext'],
                    'filesize': f.get('filesize', 0)
                })
            elif f.get('acodec') != 'none':
                formats.append({
                    'format_id': f['format_id'],
                    'bitrate': f.get('abr', 0),
                    'extension': f['ext'],
                    'filesize': f.get('filesize', 0)
                })
    
    return jsonify(formats)

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    link = data['url']
    format_id = data['format_id']
    combine = data['combine']
    
    thread = threading.Thread(target=download_task, args=(link, format_id, combine))
    thread.start()
    
    return jsonify({'status': 'Download started', 'download_url': f'/download-file/{link}'})

@app.route('/download-file/<path:url>')
def download_file(url):
    filename = tracker.get_file(url)
    if filename and os.path.exists(filename):
        return send_file(filename, as_attachment=True)
    return jsonify({'error': 'File not ready or not found'}), 404

if __name__ == '__main__':
    app.run(port=8000, debug=True)
