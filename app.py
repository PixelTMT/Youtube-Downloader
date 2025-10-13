from flask import Flask, request, Response, jsonify, send_file
import yt_dlp
import os, shutil
from mutagen.easyid3 import EasyID3
import mutagen.id3
import requests
import threading
import ffmpeg
from waitress import serve
import subprocess
import random

app = Flask(__name__, static_folder='./Webpage', static_url_path='')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))


@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/proxy', methods=['POST'])
def proxy():
    data = request.json
    url = data['url']
    original = data['original']
    filename = data['filename']
    saveLocation = Download(link=url, original=original, filelocation=filename)
    return send_file(saveLocation, as_attachment=True, download_name=filename)

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

@app.route('/watch', methods=['GET'])
def get_video():
    link = request.args.get('v')

    ydl_opts = {
        'format': 'best[ext=mp4]',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
        'outtmpl':
        '%(title)s.%(ext)s',  # formatting the file name to be VideoName.mp4
    }
    try:
        # attempt to download without errors
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            filename = f"{info['title']}.{info['ext']}"
            fileLocation = filename
            saveLocation = Download(link, '', fileLocation, ydl_opts)
            return send_file(saveLocation, as_attachment=True, download_name=filename)
    except:
        # message to be printed in the case of error
        print("Download error!")

@app.route('/combine', methods=['POST'])
def Download_Combine():
    # download and save both video and audio in downloads folder
    data = request.json
    videoURL = data['videoURL']
    audioURL = data['audioURL']
    original = data['original']
    filename = data['filename']

    try:
        # attempt to download without errors
        #urls = [videoURL, audioURL]
        #with concurrent.futures.ThreadPoolExecutor() as executor:
        #    for url in urls:
        #        executor.submit(Download, url)
        # Download both formats concurrently
        import concurrent.futures
        videoName = slugify('v_' + filename, True) + '#'
        audioName = slugify('a_' + filename, True) + '#'

        with concurrent.futures.ThreadPoolExecutor() as executor:
            video_future = executor.submit(Download, videoURL, original, videoName)
            audio_future = executor.submit(Download, audioURL, original, audioName)
            concurrent.futures.wait([video_future, audio_future])
            videoName = video_future.result()
            audioName = audio_future.result()
        # Combine with ffmpeg
        fileOutputname = f"{filename}.mp4"
        output_path = 'downloads/' + fileOutputname + str(random.randint(0, 9999999)) + '.mp4'
        print(output_path)
        print(videoName)
        print(audioName)
        # Use ffmpeg-python library instead of subprocess

        try:
            (
                ffmpeg
                .input(f'downloads/{videoName}')
                .input(f'downloads/{audioName}')
                .output(
                    output_path,
                    vcodec='copy',
                    acodec='aac',
                    **{'map': ['0:v:0', '1:a:0']},  # Map video from first input and audio from second input
                    y=None  # Overwrite output file if exists
                )
                .overwrite_output()
                .run(quiet=False)
            )
        except ffmpeg.Error as e:
            raise Exception(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        if os.path.exists(output_path):
            return send_file(output_path, as_attachment=True, download_name=fileOutputname)
    except:
        # message to be printed in the case of error
        return jsonify({"Msg": "Download error!"})
    # combine video

def has_aria2():
    """Check if aria2c is installed."""
    try:
        subprocess.run(["aria2c", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

def Download(link, original, filelocation, ydl_opts=None):
    _, _, ext = filelocation.partition('.')
    newfilelocation = 'downloads/' + slugify(filelocation, True) + str(random.randint(0, 9999999)) + '.' + ext
    try:
        # Calculate thread count dynamically
        aria2_available = has_aria2()
        print(f"✅ aria2c installed: {aria2_available}")
        if(not ydl_opts):
            ydl_opts = {
                'outtmpl': newfilelocation,
                'quiet': True,
                'no_warnings': True,
                'format': 'best',
                'progress_hooks': [lambda d: print(f'Download progress: {d["_percent_str"]}')],
                'progress': False,
                'external_downloader': 'aria2c',
                'external_downloader_args': ['-x16', '-s16', '-k1M'],  # use same dynamic threads for aria2c
                'http_chunk_size': 524288
            }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])

            info = yt_dlp.YoutubeDL(ydl_opts).extract_info(original, download=False)
            if 'Music' in info['categories'] and ext != 'webm':
                # Only attempt metadata for supported formats
                if newfilelocation.endswith('.mp3'):
                    audio = EasyID3(newfilelocation)
                    audio['title'] = info.get('title', '')
                    audio['artist'] = info.get('artists', info.get('artist', ''))
                    audio['album'] = info.get('album', info.get('alt_title', ''))
                    audio.save()
                    
                    if image_data := download_thumbnail(info):
                        audio = mutagen.id3.ID3(newfilelocation)
                        audio.add(mutagen.id3.APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=image_data
                        ))
                        audio.save()
                    else:  # Skip metadata for unsupported formats
                        pass
                elif newfilelocation.endswith(('.mp4', '.m4a')):  # MP4/M4A format
                    from mutagen.mp4 import MP4, MP4Cover
                    audio = MP4(newfilelocation)
                    
                    # Set text metadata
                    audio['\xa9nam'] = info.get('title', '')
                    audio['\xa9ART'] = info.get('artists', info.get('artist', ''))
                    audio['\xa9alb'] = info.get('album', info.get('alt_title', ''))
                    
                    # Add album art
                    if image_data := download_thumbnail(info):
                        audio['covr'] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
                    
                    audio.save()
            threading.Timer(300, os.remove, args=['downloads/' + filelocation]).start()
            return newfilelocation
    except Exception as e:
        print(f"Error downloading file: {e}")


def download_thumbnail(info):
    """Download thumbnail image from YouTube metadata and return image bytes"""
    if not info.get('thumbnail'):
        return None
    
    try:
        response = requests.get(info['thumbnail'])
        response.raise_for_status()
        
        # Create images directory if not exists
        os.makedirs('downloads/', exist_ok=True)
        
        # Sanitize filename
        filename = slugify(info.get('title', 'thumbnail'), True) + '.jpg'
        filepath = os.path.join('downloads/', filename)
        
        # Save the image
        with open(filepath, 'wb') as f:
            f.write(response.content)
            return response.content
            
    except Exception as e:
        print(f"Error downloading thumbnail: {e}")

from slugify import slugify

def empty_folders(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

# Prepare API client

if __name__ == '__main__':
    empty_folders('./downloads')
    print("App has Started")
    serve(app, host="0.0.0.0", port=14032)

