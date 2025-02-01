import yt_dlp


def download(link):
    # set the correct options before download
    ydl_opts = {
        'format': 'best[ext=mp4]',  # Download best MP4 format without merging
        'outtmpl':
        '%(title)s.%(ext)s',  # formatting the file name to be VideoName.mp4
    }
    try:
        # attempt to download without errors
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
        print("Download complete!")
    except:
        # message to be printed in the case of error
        print("Download error!")

def Format(link):
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            
            for f in info['formats']:
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    print({
                        'format_id': f['format_id'],
                        'resolution': f.get('format_note', f['ext']),
                        'extension': f['ext'],
                        'filesize': f.get('filesize', 0)
                    })
                elif f.get('acodec') != 'none':
                    print({
                        'format_id': f['format_id'],
                        'bitrate': f.get('abr', 0),
                        'extension': f['ext'],
                        'filesize': f.get('filesize', 0)
                    })
                # Print: 
                # {'format_id': '249', 'bitrate': 51.713, 'extension': 'webm', 'filesize': 1497255}
                # {'format_id': '250', 'bitrate': 68.022, 'extension': 'webm', 'filesize': 1969434}
                # {'format_id': '140', 'bitrate': 129.5, 'extension': 'm4a', 'filesize': 3750094}
                # {'format_id': '251', 'bitrate': 133.496, 'extension': 'webm', 'filesize': 3865087}
                # {'format_id': '18', 'resolution': '360p', 'extension': 'mp4', 'filesize': 6502773}


run = True
while run:
    link = input("Enter YouTube link to download (or type 'EXIT' to quit): ")
    if "youtube.com" in link or "youtu.be" in link:
        print("Downloading...")
        Format(link)
    elif link.upper() == "EXIT":
        print("Exiting program. Thank you!")
        run = False
    else:
        print("Invalid YouTube link. Try again!")
