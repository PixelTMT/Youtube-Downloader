from flask import Flask, request, Response, jsonify, stream_with_context
import yt_dlp
import os
import requests
import ffmpeg
from waitress import serve
import signal
from slugify import slugify
import threading
import time
import concurrent.futures
from retry import retry

app = Flask(__name__, static_folder='./Webpage', static_url_path='')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

mimetypes = {
    'mp4': 'video/mp4',
    'webm': 'video/webm',
    'mkv': 'video/x-matroska',
    'mp3': 'audio/mpeg',
    'm4a': 'audio/mp4',
    'opus': 'audio/opus',
}

# --- Parallel Streamer Functions ---

def split(end, step):
    """Splits a range into smaller parts."""
    return [(start, min(start + step, end)) for start in range(0, end, step)]

def get_size(url, headers={'User-Agent': 'Mozilla/5.0'}):
    """Gets the content length of a URL."""
    try:
        res = requests.head(url, headers=headers, timeout=10)
        res.raise_for_status()
        fs = res.headers.get('Content-Length')
        if fs:
            return int(fs)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to get size for {url}. Error: {e}")
    raise ValueError(f"Could not get file size from {url}")

def parallel_stream_generator(url, user_headers={'User-Agent': 'Mozilla/5.0'}):
    """
    Downloads and streams a file in parallel.
    It uses a thread pool to download chunks of the file simultaneously into an
    in-memory buffer, and then yields the chunks in order to the client.
    """
    try:
        total_size = get_size(url, user_headers)
    except ValueError as e:
        app.logger.error(f"Could not get file size for streaming: {e}")
        yield f"Error: {e}".encode()
        return

    part_size = 1024 * 1024  # 1MB parts
    parts = split(total_size, part_size)
    
    buffer = {}
    buffer_lock = threading.Lock()
    
    # Using a session for connection pooling
    session = requests.Session()

    @retry(tries=3, delay=1)
    def download_part(start, end):
        """Worker function to download a single part."""
        try:
            part_headers = user_headers.copy()
            part_headers['Range'] = f'bytes={start}-{end-1}'
            res = session.get(url, headers=part_headers, timeout=30)
            res.raise_for_status()
            
            with buffer_lock:
                buffer[start] = res.content
        except Exception as e:
            app.logger.error(f"Error in worker downloading part {start}-{end}: {e}")
            with buffer_lock:
                # Place an error marker to be handled by the main streaming loop
                buffer[start] = e

    # Use a thread pool to download parts in parallel.
    # Limiting max_workers helps control memory usage and thread overhead.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # Submit all download tasks to the executor
        for part_start, part_end in parts:
            executor.submit(download_part, part_start, part_end)

        # Main streaming loop to yield parts in order
        current_pos = 0
        while current_pos < total_size:
            next_part = None
            with buffer_lock:
                # Check if the next sequential part is in the buffer
                if current_pos in buffer:
                    next_part = buffer.pop(current_pos)

            if next_part is not None:
                # If the part was an error, stop the generator
                if isinstance(next_part, Exception):
                    error_message = f"Download failed for part at offset {current_pos}: {next_part}"
                    app.logger.error(error_message)
                    raise IOError(error_message)
                
                yield next_part
                current_pos += len(next_part)
            else:
                # Wait for the part to be downloaded
                time.sleep(0.01)

@app.route('/')
def index():
    return app.send_static_file('index.html')

@stream_with_context
def generate(proc):
    """Generator to stream ffmpeg's stdout."""
    try:
        while True:
            chunk = proc.stdout.read(64*1024)
            if not chunk:
                break
            yield chunk
    except GeneratorExit:
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
            c='copy',
            movflags='frag_keyframe+empty_moov+faststart',
            f='mp4'
        )
        
        stream = stream.global_args('-hide_banner', '-loglevel', 'error')
        proc = stream.run_async(pipe_stdout=True, pipe_stderr=True)

    except ffmpeg.Error as e:
        return jsonify({"error": "ffmpeg execution failed", "details": e.stderr.decode() if e.stderr else 'No details'}), 500

    safe_name = slugify(filename, True) + '.mp4'
    headers = {'Content-Disposition': f'attachment; filename="{safe_name}"'}
    return Response(generate(proc), mimetype='video/mp4', headers=headers)


@app.route('/stream_download', methods=['POST'])
def stream_download():
    data = request.json
    url = data.get('url')
    filename = data.get('filename')

    if not url or not filename:
        return jsonify({"error": "Invalid Request"}), 400

    _, _, ext = filename.rpartition('.')
    ext = ext.lower()

    mimetype = mimetypes.get(ext, 'application/octet-stream')
    safe_name = slugify(filename, True) + '.' + ext
    headers = {'Content-Disposition': f'attachment; filename="{safe_name}"'}

    try:
        # Use the parallel stream generator for all downloads
        generator = parallel_stream_generator(url)
        return Response(stream_with_context(generator), mimetype=mimetype, headers=headers)

    except Exception as e:
        app.logger.error(f"Failed to stream from {url}. Error: {e}", exc_info=True)
        return jsonify({"error": "Failed to process stream", "details": str(e)}), 500


@app.route('/api/video_details', methods=['POST'])
def get_video_details():
    data = request.json
    link = data['url']
    return extract_and_filter_formats(link)

def extract_and_filter_formats(link):
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
            if(f.get('format_note') == 'storyboard' or f['ext'] == "webm"):
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

DEBUG = True # Set to False for production deployment

if __name__ == '__main__':
    port = 14032
    print(f"App has Started port {port}")
    if DEBUG:
        app.run(debug=True, host="0.0.0.0", port=port)
    else:
        serve(app, host="0.0.0.0", port=port)