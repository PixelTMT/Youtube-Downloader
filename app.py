from flask import Flask, request, Response, jsonify, send_file
import yt_dlp
import os, shutil
import requests

app = Flask(__name__, static_folder='./Webpage', static_url_path='')
sPort = 3000


@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/proxy', methods=['POST'])
def proxy():
    data = request.json
    url = data['url']
    filename = data['filename']
    location = 'downloads/' + data['filename']
    Download(url, location)
    return send_file(location, as_attachment=True, download_name=filename)

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
        "downloads/" + '%(title)s.%(ext)s',  # formatting the file name to be VideoName.mp4
    }
    try:
        # attempt to download without errors
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            ydl.download([link])
            return send_file("downloads/" + f"{info['title']}{info['ext']}", as_attachment=True)
    except:
        # message to be printed in the case of error
        print("Download error!")

@app.route('/combine', methods=['POST'])
def Download_Combine():
    # download and save both video and audio in downloads folder
    data = request.json
    videoURL = data['videoURL']
    audioURL = data['audioURL']
    filename = data['filename']

    try:
        # attempt to download without errors
        #urls = [videoURL, audioURL]
        #with concurrent.futures.ThreadPoolExecutor() as executor:
        #    for url in urls:
        #        executor.submit(Download, url)
        # Download both formats concurrently
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            video_future = executor.submit(Download, videoURL, 'downloads/v_' + filename)
            audio_future = executor.submit(Download, audioURL, 'downloads/a_' + filename)
            concurrent.futures.wait([video_future, audio_future])

        # Combine with ffmpeg
        output_path = f"downloads/{filename}.mp4"
        ffmpeg_path = 'ffmpeg/ffmpeg.exe'  # Path to ffmpeg executable
        
        # Build ffmpeg command
        command = [
            ffmpeg_path,
            '-i', f'downloads/v_{filename}',
            '-i', f'downloads/a_{filename}',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-y',  # Overwrite output file if exists
            output_path
        ]
        
        # Run ffmpeg command
        import subprocess
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg error: {result.stderr}")
            
        return send_file(output_path, as_attachment=True)
    except:
        # message to be printed in the case of error
        return jsonify({"Msg": "Download error!"})
    # combine video


def Download(link, filelocation):
    ydl_opts = {
        'outtmpl': filelocation,
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'progress_hooks': [lambda d: print(f'Download progress: {d["_percent_str"]}')],
        'noprogress': False,
        'external_downloader': 'aria2c',
        'concurrent_fragment_downloads': 4*2,
        'http_chunk_size': 1048576/2  # 1 MB chunks
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([link])

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

if __name__ == '__main__':
    empty_folders('./downloads')
    app.run(port=sPort, debug=True)
