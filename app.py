from flask import Flask, request, jsonify, send_file
import yt_dlp

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
        print('downloading video')
        Download(videoURL, 'downloads/v_' + filename)
        print('downloading audio')
        Download(audioURL, 'downloads/a_' + filename)

        print('combining video and audio')
        return jsonify({"Msg": "Download successfully completed"})
    except:
        # message to be printed in the case of error
        return jsonify({"Msg": "Download error!"})
    # combine video


def Download(link, filelocation):
    print(link)


if __name__ == '__main__':
    app.run(port=sPort, debug=True)
