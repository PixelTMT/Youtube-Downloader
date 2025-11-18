
import subprocess
import requests
import os
import threading
import hashlib
import json
from app import app

def file_hash(filename):
    h = hashlib.sha256()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def test_and_download_stream(client, format_info, stream_type, results):
    """
    Tests the /stream_download endpoint for a given stream type (video or audio).
    It downloads the file from the raw URL and the API endpoint in parallel and compares them.
    The result and the path to the raw downloaded file are stored in the results dictionary.
    """
    testPass = "Failed"
    raw_filename = f"test_{stream_type}_raw.{format_info['extension']}"
    api_filename = f"test_{stream_type}_api.{format_info['extension']}"

    def download_raw():
        print(f"Downloading {stream_type} from raw URL...")
        raw_response = requests.get(format_info["url"], stream=True)
        with open(raw_filename, "wb") as f:
            for chunk in raw_response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Raw {stream_type} download complete.")

    def download_api():
        print(f"Downloading {stream_type} from API...")
        api_response = client.post("/stream_download", json={"url": format_info["url"], "filename": api_filename})
        with open(api_filename, "wb") as f:
            f.write(api_response.data)
        print(f"API {stream_type} download complete.")
        return api_response

    raw_thread = threading.Thread(target=download_raw)
    api_thread_result = {}
    api_thread = threading.Thread(target=lambda: api_thread_result.update(api_response=download_api()))

    raw_thread.start()
    api_thread.start()
    raw_thread.join()
    api_thread.join()

    api_response = api_thread_result.get("api_response")

    raw_size = os.path.getsize(raw_filename)
    api_size = os.path.getsize(api_filename)
    print(f"Raw {stream_type} size: {raw_size}, API {stream_type} size: {api_size}")

    size_test_passed = raw_size == api_size
    hash_test_passed = False
    if size_test_passed:
        raw_hash = file_hash(raw_filename)
        api_hash = file_hash(api_filename)
        print(f"Raw {stream_type} hash: {raw_hash}")
        print(f"API {stream_type} hash: {api_hash}")
        hash_test_passed = raw_hash == api_hash

    if api_response and api_response.status_code == 200 and size_test_passed and hash_test_passed:
        testPass = "Pass"

    print(f"/stream_download {stream_type} test {testPass} (Size match: {size_test_passed}, Hash match: {hash_test_passed})")
    
    results[stream_type] = {
        "passed": testPass == "Pass",
        "raw_file": raw_filename,
        "api_file": api_filename
    }

def run_test(quality='lowest'):
    """
    Tests the Flask application by making API calls with a test client.
    :param quality: The quality of the streams to test ('lowest' or 'highest').
    """
    client = app.test_client()
    try:
        youtube_url = "https://www.youtube.com/watch?v=g0JEUPfmu9c"

        # Test /api/video_details
        print("Testing /api/video_details...")
        response = client.post("/api/video_details", json={"url": youtube_url})
        print(f"response.status_code: {response.status_code}")
        data = json.loads(response.data)
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


        results = {}
        threads = []
        if video_format:
            video_thread = threading.Thread(target=test_and_download_stream, args=(client, video_format, "video", results))
            threads.append(video_thread)
            video_thread.start()
        
        if audio_format:
            audio_thread = threading.Thread(target=test_and_download_stream, args=(client, audio_format, "audio", results))
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
            combine_response = client.post("/stream_combine", json={"videoURL": video_format["url"], "audioURL": audio_format["url"], "filename": combined_from_api_filename})
            with open(combined_from_api_filename, "wb") as f:
                f.write(combine_response.data)

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
            if stream_type in results:
                if "raw_file" in results[stream_type] and os.path.exists(results[stream_type]["raw_file"]):
                    os.remove(results[stream_type]["raw_file"])
                if "api_file" in results[stream_type] and os.path.exists(results[stream_type]["api_file"]):
                    os.remove(results[stream_type]["api_file"])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the application test suite.")
    parser.add_argument('--quality', type=str, default='lowest', choices=['lowest', 'highest'],
                        help='The quality of the video/audio to test (default: lowest).')
    args = parser.parse_args()
    
    run_test(quality=args.quality)
