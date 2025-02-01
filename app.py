from flask import Flask, request, jsonify, send_file
import yt_dlp
import requests
import concurrent.futures

app = Flask(__name__, static_folder='./Webpage', static_url_path='')
sPort = 3000


@app.route('/')
def index():
    return app.send_static_file('index.html')

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
    
    return jsonify(formats)

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
            return send_file("downloads/" + f"{info['title']}.{info['ext']}", as_attachment=True)
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
        with concurrent.futures.ThreadPoolExecutor() as executor:
            print('downloading video')
            executor.submit(Download, videoURL, 'downloads/v_' + filename)
            print('downloading audio')
            executor.submit(Download, audioURL, 'downloads/a_' + filename)

        # Combine with ffmpeg
        output_path = f"downloads/{filename}_combined.mp4"
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
    bytes = requests.get(link).content
    with open(filelocation, 'wb') as file:
        file.write(bytes)
        print(f'{filelocation} was downloaded...')


if __name__ == '__main__':
    app.run(port=sPort, debug=True)
