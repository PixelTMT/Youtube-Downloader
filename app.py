from flask import Flask, request, Response, jsonify, stream_with_context
import yt_dlp
import os
import requests
import ffmpeg
from waitress import serve
import signal
from slugify import slugify

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

@app.route('/')
def index():
    return app.send_static_file('index.html')

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
    headers = {'Content-Disposition': f'attachment; filename="{filename + '.mp4'}"'}
    return Response(generate(proc), mimetype='video/mp4', headers=headers)


@app.route('/stream_download', methods=['POST'])
def stream_download():
    data = request.json
    url = data.get('url')
    filename = data.get('filename')
    thumbnail_url = data.get('thumbnailURL')
    is_video_only = data.get('videoOnly', False)

    if not url or not filename:
        return jsonify({"error": "Invalid Request"}), 400

    _, _, ext = filename.rpartition('.')
    ext = ext.lower()

    video_exts = ['mp4', 'webm', 'mkv']
    audio_exts = ['mp3', 'm4a', 'opus']

    stream = None
    proc = None

    mimetype = mimetypes.get(ext, 'application/octet-stream')

    try:
        if ext in video_exts:
            output_kwargs = {}
            if ext == 'mp4':
                output_kwargs['movflags'] = 'frag_keyframe+empty_moov+faststart'

            if is_video_only:
                video_input = ffmpeg.input(url)
                silent_audio = ffmpeg.input('anullsrc', f='lavfi')
                stream = ffmpeg.output(
                    video_input.video, silent_audio.audio, 'pipe:1',
                    c_v='copy', c_a='aac', shortest=None, f=ext, **output_kwargs
                )
            else:
                input_stream = ffmpeg.input(url)
                stream = ffmpeg.output(
                    input_stream, 'pipe:1', c='copy', f=ext, **output_kwargs
                )

        elif ext in audio_exts:
            output_kwargs = {}
            if ext == 'm4a':
                output_kwargs['movflags'] = 'frag_keyframe+empty_moov+faststart'

            audio_input = ffmpeg.input(url)
            if thumbnail_url:
                thumbnail_input = ffmpeg.input(thumbnail_url)
                stream = ffmpeg.output(
                    audio_input.audio, thumbnail_input.video, 'pipe:1',
                    map=['0:a', '1:v'], c='copy', **{'disposition:v': 'attached_pic'},
                    f=ext, **output_kwargs
                )
            else:
                stream = ffmpeg.output(
                    audio_input.audio, 'pipe:1', c='copy', f=ext, **output_kwargs
                )
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        stream = stream.global_args('-hide_banner', '-loglevel', 'error')
        proc = stream.run_async(pipe_stdout=True, pipe_stderr=True)

    except ffmpeg.Error as e:
        return jsonify({"error": "ffmpeg execution failed", "details": e.stderr.decode() if e.stderr else 'No details'}), 500

    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    return Response(generate(proc), mimetype=mimetype, headers=headers)

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