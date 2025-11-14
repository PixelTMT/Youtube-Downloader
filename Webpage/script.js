window.selectedFormats = {currentFormat: null, original: null , video: null, audio: null };
window.isDownloading = false;
window.combineDownloadBtnState = false;
window.abortController = new AbortController();

async function fetchVideoInfo() {
    const url = document.getElementById('urlInput').value;
    const button = document.getElementById('searchBtn');
    
    window.selectedFormats = {currentFormat: null, original: document.getElementById('urlInput').value , video: null, audio: null };
    updateCombineButton();

    try {
        button.disabled = true;
        setLoading(true);
        
        const response = await fetch('/api/video_details', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });

        if (!response.ok) throw new Error('Failed to fetch formats');
        
        const {title, thumbnail, formats} = await response.json();
        
        // Update video title and thumbnail
        document.getElementById('videoTitle').textContent = title;
        document.getElementById('videoThumbnail').src = thumbnail;
        document.getElementById('videoInfo').style.display = 'block';
        window.selectedFormats['currentFormat'] = title;
        console.log(window.selectedFormats['currentFormat']);
        // Sort formats by filesize descending
        const sortedFormats = formats.sort((a, b) => b.filesize - a.filesize);
        window.sortedFormats = sortedFormats;
        renderFormats(sortedFormats);
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to fetch formats. Please check the URL and try again.');
    } finally {
        button.disabled = false;
        setLoading(false);
    }
}

// streaming CombineDownload — replace the existing function
async function startCombinedDownload(){
    if (!window.selectedFormats.video || !window.selectedFormats.audio) {
        alert('Please select both video and audio formats');
        return;
    }
    window.isDownloading = true;
    updateCombineButton();
    setDownloadButtonsState(true);
    setLoading(true);

    // UI elements for progress (created in index.html)
    const progressWrap = document.getElementById('downloadProgressWrap');
    const progressBar = document.getElementById('downloadProgress');
    const progressText = document.getElementById('downloadText');
    const progressPercent = document.getElementById('downloadPercent');
    const cancelBtn = document.getElementById('cancelBtn');

    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = 'Starting...';
    progressPercent.textContent = '0%';
    cancelBtn.style.display = 'inline-block';

    // Prepare payload
    const payload = {
        videoURL: window.selectedFormats.video.url,
        audioURL: window.selectedFormats.audio.url,
        original: window.selectedFormats.original,
        filename: window.selectedFormats['currentFormat']
    };

    // Abort controller so we can cancel if needed
    window.abortController = new AbortController();
    const signal = window.abortController.signal;

    try {
        const resp = await fetch('/stream_combine', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
            signal
        });

        if (!resp.ok) {
            throw new Error('Combine request failed: ' + resp.status);
        }

        // Try to read estimated size header (backend should set this if possible)
        const estimated = resp.headers.get('X-Estimated-Content-Length');
        const totalBytes = estimated ? parseInt(estimated, 10) : null;

        // stream the body
        const reader = resp.body.getReader();
        const chunks = [];
        let received = 0;
        const startTime = Date.now();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
            received += value.length;
            const elapsed = Math.max(1, (Date.now() - startTime) / 1000);
            const mbps = (received / (1024*1024)) / elapsed;
            // update progress UI
            if (totalBytes) {
                const pct = Math.min(100, (received / totalBytes) * 100);
                progressBar.style.width = pct.toFixed(2) + '%';
                progressPercent.textContent = pct.toFixed(1) + '%';
                progressText.textContent = `Downloaded ${(received / (1024*1024)).toFixed(2)} MB of ${(totalBytes / (1024*1024)).toFixed(2)} MB — ${mbps.toFixed(2)} MB/s`;
            } else {
                // unknown total: show bytes and speed
                progressBar.style.width = '100%'; // keep bar full when unknown
                progressPercent.textContent = `${(received / (1024*1024)).toFixed(2)} MB`;
                progressText.textContent = `Downloaded ${(received / (1024*1024)).toFixed(2)} MB — ${mbps.toFixed(2)} MB/s`;
            }
        }

        // assemble Blob and trigger download
        const blob = new Blob(chunks, { type: 'video/mp4' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // sanitize filename a bit: remove slashes
        const safeName = (window.selectedFormats['currentFormat'] || 'video').replace(/[\/\\:?<>|"]/g, '_');
        a.download = `${safeName}.mp4`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        progressText.textContent = 'Done!';
        progressPercent.textContent = '100%';
    } catch (err) {
        if (err.name === 'AbortError') {
            progressText.textContent = 'Cancelled';
        } else {
            console.error(err);
            alert('Failed to combine formats. See console for details.');
            progressText.textContent = 'Error';
        }
    } finally {
        window.isDownloading = false;
        updateCombineButton();
        setDownloadButtonsState(false);
        setLoading(false);
        document.getElementById('cancelBtn').style.display = 'none';
        // hide after a short delay so user sees completion
        setTimeout(() => {
            const progressWrap = document.getElementById('downloadProgressWrap');
            if (progressWrap) progressWrap.style.display = 'none';
        }, 2500);
    }
}


function renderFormats(sortedFormats) {
    const container = document.getElementById('formatsContainer');
    container.innerHTML = '';

    // Create new containers each render
    const videoContainer = document.createElement('div');
    videoContainer.className = 'formats-section';
    videoContainer.innerHTML = '<h3><i class="fas fa-video"></i> Video Formats</h3>';
    
    const audioContainer = document.createElement('div');
    audioContainer.className = 'formats-section';
    audioContainer.innerHTML = '<h3><i class="fas fa-music"></i> Audio Formats</h3>';

    sortedFormats.forEach(format => {
        
        const targetContainer = format.format.includes('audio') ? audioContainer : videoContainer;
        const card = document.createElement('div');
        card.className = 'format-card';
        
        const isAudio = format.format.includes('audio');
        const formatType = isAudio ? 'audio' : 'video';
        const isSelected = window.selectedFormats?.[formatType]?.url === format.url;

        let cardContent = `
            <label class="select-format">
                <input type="radio" name="${formatType}Format" 
                    value="${format.url}" 
                    data-format='${JSON.stringify(format).replace(/'/g, "\\'")}'
                    ${isSelected ? 'checked' : ''}>
                Select for combined download
            </label>
            <p><strong>Format:</strong> ${format.format}</p>
            ${format.codec ? `<p><strong>Codec:</strong> ${format.codec}</p>` : ''}
        `;

        if(isAudio){
            cardContent += `
                <p><strong>Bitrate:</strong> ${format.bitrate || 'N/A'} kbps</p>
                <p><strong>Sample Rate:</strong> ${format.sampleRate ? (format.sampleRate / 1000) + ' kHz' : 'N/A'}</p>
            `;
        } else {
            cardContent += `
                <p><strong>Resolution:</strong> ${format.resolution || 'N/A'}</p>
            `;
        }

        cardContent += `
            <p><strong>Extension:</strong> .${format.extension}</p>
            <p><strong>Filesize:</strong> ${(format.filesize / 1024 / 1024).toFixed(2)} MB</p>
            <div class="actions">
                <button class="download-btn" onclick="downloadFormat('${format.url}', '${window.selectedFormats['currentFormat']}.${format.extension}')">
                    <i class="fas fa-download"></i> Download
                </button>
                <button class="direct-download-btn" onclick="window.open('${format.url}')">
                    <i class="fas fa-link"></i> Raw File
                </button>
            </div>
        `;
        
        card.innerHTML = cardContent;
        targetContainer.appendChild(card);
    });

    container.appendChild(videoContainer);
    container.appendChild(audioContainer);
    updateCombineButton();
}

// Handle format selection changes
document.addEventListener('change', (e) => {
    if (e.target.matches('input[type="radio"][name="videoFormat"], input[type="radio"][name="audioFormat"]')) {
        const formatType = e.target.name === 'videoFormat' ? 'video' : 'audio';
        const formatData = JSON.parse(e.target.dataset.format.replace(/\\'/g, "'"));
        window.selectedFormats[formatType] = formatData;
        updateCombineButton();
    }
});

function updateCombineButton(){
    // Update combine button state
    const combineBtn = document.getElementById('combineBtn');
    combineBtn.disabled = (!(window.selectedFormats.video && window.selectedFormats.audio) && !window.isDownloading);
}

async function downloadFormat(url, filename) {
    setDownloadButtonsState(true);
    setLoading(true);
    window.isDownloading = true;
    updateCombineButton();
    // UI elements for progress
    const progressWrap = document.getElementById('downloadProgressWrap');
    const progressBar = document.getElementById('downloadProgress');
    const progressText = document.getElementById('downloadText');
    const progressPercent = document.getElementById('downloadPercent');
    const cancelBtn = document.getElementById('cancelBtn');

    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = 'Starting...';
    progressPercent.textContent = '0%';
    cancelBtn.style.display = 'inline-block';

    // Prepare payload
    const payload = {
        url: url,
        filename: filename
    };

    // Abort controller
    window.abortController = new AbortController();
    const signal = window.abortController.signal;

    try {
        const resp = await fetch('/stream_download', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
            signal
        });

        if (!resp.ok) {
            throw new Error('Download request failed: ' + resp.status);
        }

        // Get total size from format data if possible
        const formatData = window.sortedFormats.find(f => f.url === url);
        const totalBytes = formatData ? formatData.filesize : null;

        // stream the body
        const reader = resp.body.getReader();
        const chunks = [];
        let received = 0;
        const startTime = Date.now();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
            received += value.length;
            const elapsed = Math.max(1, (Date.now() - startTime) / 1000);
            const mbps = (received / (1024*1024)) / elapsed;
            // update progress UI
            if (totalBytes) {
                const pct = Math.min(100, (received / totalBytes) * 100);
                progressBar.style.width = pct.toFixed(2) + '%';
                progressPercent.textContent = pct.toFixed(1) + '%';
                progressText.textContent = `Downloaded ${(received / (1024*1024)).toFixed(2)} MB of ${(totalBytes / (1024*1024)).toFixed(2)} MB — ${mbps.toFixed(2)} MB/s`;
            } else {
                // unknown total: show bytes and speed
                progressBar.style.width = '100%'; // keep bar full when unknown
                progressPercent.textContent = `${(received / (1024*1024)).toFixed(2)} MB`;
                progressText.textContent = `Downloaded ${(received / (1024*1024)).toFixed(2)} MB — ${mbps.toFixed(2)} MB/s`;
            }
        }

        // Get mimetype from filename extension
        const extension = filename.split('.').pop();
        const mimetypes = {
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'mkv': 'video/x-matroska',
            'mp3': 'audio/mpeg',
            'm4a': 'audio/mp4',
            'opus': 'audio/opus',
        };
        const mimetype = mimetypes[extension] || 'application/octet-stream';

        // assemble Blob and trigger download
        const blob = new Blob(chunks, { type: mimetype });
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);

        progressText.textContent = 'Done!';
        progressPercent.textContent = '100%';
    } catch (err) {
        if (err.name === 'AbortError') {
            progressText.textContent = 'Cancelled';
        } else {
            console.error(err);
            alert('Failed to download format. See console for details.');
            progressText.textContent = 'Error';
        }
    } finally {
        window.isDownloading = false;
        updateCombineButton();
        setDownloadButtonsState(false);
        setLoading(false);
        document.getElementById('cancelBtn').style.display = 'none';
        // hide after a short delay
        setTimeout(() => {
            const progressWrap = document.getElementById('downloadProgressWrap');
            if (progressWrap) progressWrap.style.display = 'none';
        }, 2500);
    }
}

function setDownloadButtonsState(disabled) {
    document.querySelectorAll('.download-btn').forEach(btn => btn.disabled = disabled);
}

function setLoading(state){
    const loadingBar = document.getElementById('loadingBar');
    if(state){
        loadingBar.style.display = 'block';
    }
    else{
        loadingBar.style.display = 'none';
    }
}

function cancelDownload() {
    if (window.abortController) {
        window.abortController.abort();
    }
}

// Auto-trigger when page loads with URL parameter and add event listeners
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('searchBtn').addEventListener('click', fetchVideoInfo);
    document.getElementById('combineBtn').addEventListener('click', startCombinedDownload);
    document.getElementById('cancelBtn').addEventListener('click', cancelDownload);

    const urlParams = new URLSearchParams(window.location.search);
    const vID = urlParams.get('v');
    if (vID) {
        document.getElementById('urlInput').value = 'https://www.youtube.com/watch?v=' + vID;
        fetchVideoInfo();
    }

    window.addEventListener('beforeunload', (event) => {
        if (window.isDownloading) {
            event.preventDefault();
            event.returnValue = ''; // Required for Chrome
        }
    });
});
