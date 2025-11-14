
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

def test_and_download_stream(format_info, base_url, stream_type, results):
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
        api_response = requests.post(f"{base_url}/stream_download", json={"url": format_info["url"], "filename": api_filename}, stream=True)
        with open(api_filename, "wb") as f:
            for chunk in api_response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
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

def run_test():
    """
    Tests the Flask application by starting the server, making API calls, and then shutting it down.
    """
    server_process = None
    try:
        # Start the server
        server_process = subprocess.Popen(['.\\.venv\\Scripts\\python.exe', 'app.py'])
        print("Server started, waiting for it to be ready...")
        time.sleep(5)

        base_url = "http://192.168.0.102:14032"
        youtube_url = "https://www.youtube.com/watch?v=g0JEUPfmu9c"

        # Test /api/video_details
        print("Testing /api/video_details...")
        response = requests.post(f"{base_url}/api/video_details", json={"url": youtube_url})
        print(f"response.status_code: {response.status_code}")
        data = response.json()
        print(f"Title: {data['title']}")
        print("/api/video_details test PASSED")

        video_format = next((f for f in data["formats"] if f.get("extension") == "mp4" and not f.get("sampleRate")), None)
        audio_format = next((f for f in data["formats"] if f.get("codec") and "mp4a" in f["codec"] ), None)

        print(f"video_format is not None: {video_format is not None}")
        print(f"audio_format is not None: {audio_format is not None}")

        results = {}
        threads = []
        if video_format:
            video_thread = threading.Thread(target=test_and_download_stream, args=(video_format, base_url, "video", results))
            threads.append(video_thread)
            video_thread.start()
        
        if audio_format:
            audio_thread = threading.Thread(target=test_and_download_stream, args=(audio_format, base_url, "audio", results))
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
                print("/stream_combine test Pass")
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
                if os.path.exists(results[stream_type]["raw_file"]):
                    os.remove(results[stream_type]["raw_file"])
                if os.path.exists(results[stream_type]["api_file"]):
                    os.remove(results[stream_type]["api_file"])
        
        if server_process:
            print("Shutting down server...")
            server_process.terminate()
            server_process.wait()
            print("Server shut down.")

if __name__ == "__main__":
    run_test()
