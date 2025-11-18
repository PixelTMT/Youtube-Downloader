
import subprocess
import time
import requests
import os
import signal
import threading
import hashlib

def file_hash(filename):
    h = hashlib.sha256()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def _download_and_compare_stream(format_info, base_url, stream_type, results, thumbnail_url=None):
    """
    Tests the /stream_download endpoint for a given stream type (video or audio).
    Downloads the file from the API and verifies its properties.
    The result and the path to the downloaded file are stored in the results dictionary.
    """
    testPass = "Failed"
    api_filename = f"test_{stream_type}_api.{format_info['extension']}"
    is_video_only = stream_type == "video" and not format_info.get("sampleRate")

    payload = {
        "url": format_info["url"],
        "filename": api_filename,
        "thumbnailURL": thumbnail_url if stream_type == "audio" else None,
        "videoOnly": is_video_only
    }

    print(f"Downloading {stream_type} from API with payload: {payload}")
    api_response = requests.post(f"{base_url}/stream_download", json=payload, stream=True)
    with open(api_filename, "wb") as f:
        for chunk in api_response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print(f"API {stream_type} download complete.")

    verification_passed = False
    if api_response.status_code == 200:
        if stream_type == "audio" and thumbnail_url:
            verification_passed = _verify_thumbnail_embedded(api_filename)
            print(f"Thumbnail verification for {api_filename}: {'Pass' if verification_passed else 'Fail'}")
        elif is_video_only:
            verification_passed = _verify_silent_audio(api_filename)
            print(f"Silent audio verification for {api_filename}: {'Pass' if verification_passed else 'Fail'}")
        else:
            # For audio without thumbnail or video with audio, we can just check if the file is valid
            verification_passed = os.path.getsize(api_filename) > 0

    if verification_passed:
        testPass = "Pass"

    print(f"/stream_download {stream_type} test {testPass}")
    
    results[stream_type] = {
        "passed": testPass == "Pass",
        "api_file": api_filename
    }

def _verify_thumbnail_embedded(filepath):
    """Verify that a thumbnail is embedded in the media file."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', filepath],
            check=True, capture_output=True, text=True
        )
        return 'video' in result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def _verify_silent_audio(filepath):
    """Verify that the media file has an audio track."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', filepath],
            check=True, capture_output=True, text=True
        )
        return 'audio' in result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def test_app_flow(quality='lowest'):
    """
    Tests the Flask application by starting the server, making API calls, and then shutting it down.
    :param quality: The quality of the streams to test ('lowest' or 'highest').
    """
    server_process = None
    try:
        # Start the server
        server_process = subprocess.Popen(['python3', 'app.py'])
        print("Server started, waiting for it to be ready...")
        time.sleep(5)

        base_url = "http://127.0.0.1:14032"
        youtube_url = "https://www.youtube.com/watch?v=g0JEUPfmu9c"

        # Test /api/video_details
        print("Testing /api/video_details...")
        response = requests.post(f"{base_url}/api/video_details", json={"url": youtube_url})
        print(f"response.status_code: {response.status_code}")
        data = response.json()
        print(f"Title: {data['title']}")
        print("/api/video_details test PASSED")

        print(f"Selecting {quality} quality formats...")
        if quality == 'highest':
            video_formats = [f for f in data["formats"] if f.get("extension") == "mp4" and not f.get("sampleRate") and f.get('filesize')]
            if video_formats:
                video_formats.sort(key=lambda f: f['filesize'])
                video_format = video_formats[-1]
            else:
                video_format = None

            audio_formats = [f for f in data["formats"] if f.get("codec") and "mp4a" in f["codec"] and f.get('filesize')]
            if audio_formats:
                audio_formats.sort(key=lambda f: f['filesize'])
                audio_format = audio_formats[-1]
            else:
                audio_format = None
        else: # 'lowest'
            video_format = next((f for f in data["formats"] if f.get("extension") == "mp4" and not f.get("sampleRate")), None)
            audio_format = next((f for f in data["formats"] if f.get("codec") and "mp4a" in f["codec"] ), None)

        print(f"video_format is not None: {video_format is not None}")
        if video_format:
            print(f"Selected video format: {video_format.get('format')}")
        print(f"audio_format is not None: {audio_format is not None}")
        if audio_format:
            print(f"Selected audio format: {audio_format.get('format')}")


        thumbnail_url = data.get("thumbnail")
        results = {}
        threads = []
        if video_format:
            video_thread = threading.Thread(target=_download_and_compare_stream, args=(video_format, base_url, "video", results))
            threads.append(video_thread)
            video_thread.start()
        
        if audio_format:
            audio_thread = threading.Thread(target=_download_and_compare_stream, args=(audio_format, base_url, "audio", results, thumbnail_url))
            threads.append(audio_thread)
            audio_thread.start()

        for thread in threads:
            thread.join()

        # Test /stream_combine
        if video_format and audio_format and results.get("video", {}).get("passed") and results.get("audio", {}).get("passed"):
            print("Testing /stream_combine...")
            video_raw_filename = results["video"]["raw_file"]
            audio_raw_filename = results["audio"]["raw_file"]

            locally_combined_filename = "locally_combined.mp4"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-i", video_raw_filename,
                        "-i", audio_raw_filename,
                        "-c", "copy",
                        "-movflags", "frag_keyframe+empty_moov+faststart",
                        "-y",
                        locally_combined_filename,
                    ],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"Error combining files locally with ffmpeg: {e}")
                raise e

            combined_from_api_filename = "combined_from_api.mp4"
            combine_response = requests.post(f"{base_url}/stream_combine", json={"videoURL": video_format["url"], "audioURL": audio_format["url"], "filename": combined_from_api_filename}, stream=True)
            with open(combined_from_api_filename, "wb") as f:
                for chunk in combine_response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            local_size = os.path.getsize(locally_combined_filename)
            api_size = os.path.getsize(combined_from_api_filename)
            print(f"Locally combined size: {local_size}, API combined size: {api_size}")

            size_test_passed = abs(local_size - api_size) < 1024
            hash_test_passed = False
            if size_test_passed:
                local_hash = file_hash(locally_combined_filename)
                api_hash = file_hash(combined_from_api_filename)
                print(f"Locally combined hash: {local_hash}")
                print(f"API combined hash: {api_hash}")
                hash_test_passed = local_hash == api_hash

            if combine_response.status_code == 200 and size_test_passed and hash_test_passed:
                print(f"/stream_combine test Pass (Size match: {size_test_passed}, Hash match: {hash_test_passed})")
            else:
                print(f"/stream_combine test Failed (Size match: {size_test_passed}, Hash match: {hash_test_passed})")

            os.remove(locally_combined_filename)
            os.remove(combined_from_api_filename)

        print("All tests Finish!")

    except Exception as e:
        print(f"A test failed: {e}")
    finally:
        # Cleanup all downloaded files
        for stream_type in ["video", "audio"]:
                if stream_type in results and "api_file" in results[stream_type] and os.path.exists(results[stream_type]["api_file"]):
                    os.remove(results[stream_type]["api_file"])
        
        if server_process:
            print("Shutting down server...")
            server_process.terminate()
            server_process.wait()
            print("Server shut down.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the application test suite.")
    parser.add_argument('--quality', type=str, default='lowest', choices=['lowest', 'highest'],
                        help='The quality of the video/audio to test (default: lowest).')
    args = parser.parse_args()
    
    test_app_flow(quality=args.quality)
