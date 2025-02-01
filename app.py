from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__, static_folder='.', static_url_path='')
sPort = 3000


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
            if(f.get('format_note') == 'storyboard'):
                continue
            formats.append({
                    'codec': f.get('acodec', f.get('vcodec', f.get('acodec'))),
                    'format': f['format'],
                    'samplesRate': f.get('asr'),
                    'bitrate': f.get('abr'),
                    'extension': f['ext'],
                    'filesize': f.get('filesize', 0),
                    'url': f.get('url')
                })
    
    return jsonify(formats)


if __name__ == '__main__':
    app.run(port=sPort, debug=True)
