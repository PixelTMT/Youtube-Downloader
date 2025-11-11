window.selectedFormats = {currentFormat: null, original: null , video: null, audio: null };

async function fetchFormats() {
    const url = document.getElementById('urlInput').value;
    const button = document.querySelector('button');
    
    window.selectedFormats = {currentFormat: null, original: document.getElementById('urlInput').value , video: null, audio: null };
    UpdateCombineButton();

    try {
        button.disabled = true;
        SetLoading(true);
        
        const response = await fetch('/formats', {
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
        ListingAllFormats(sortedFormats);
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to fetch formats. Please check the URL and try again.');
    } finally {
        button.disabled = false;
        SetLoading(false);
    }
}

// streaming CombineDownload — replace the existing function
async function CombineDownload(){
    if (!window.selectedFormats.video || !window.selectedFormats.audio) {
        alert('Please select both video and audio formats');
        return;
    }

    const combineBtn = document.getElementById('combineBtn');
    combineBtn.disabled = true;
    SetLoading(true);

    // UI elements for progress (created in index.html)
    const progressWrap = document.getElementById('downloadProgressWrap');
    const progressBar = document.getElementById('downloadProgress');
    const progressText = document.getElementById('downloadText');
    const progressPercent = document.getElementById('downloadPercent');

    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = 'Starting...';
    progressPercent.textContent = '0%';

    // Prepare payload
    const payload = {
        videoURL: window.selectedFormats.video.url,
        audioURL: window.selectedFormats.audio.url,
        original: window.selectedFormats.original,
        filename: window.selectedFormats['currentFormat']
    };

    // Abort controller so we can cancel if needed
    const controller = new AbortController();
    const signal = controller.signal;

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

            // update progress UI
            if (totalBytes) {
                const pct = Math.min(100, (received / totalBytes) * 100);
                progressBar.style.width = pct.toFixed(2) + '%';
                progressPercent.textContent = pct.toFixed(1) + '%';
                progressText.textContent = `Downloaded ${(received / (1024*1024)).toFixed(2)} MB of ${(totalBytes / (1024*1024)).toFixed(2)} MB`;
            } else {
                // unknown total: show bytes and speed
                const elapsed = Math.max(1, (Date.now() - startTime) / 1000);
                const mbps = (received / (1024*1024)) / elapsed;
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
        combineBtn.disabled = false;
        SetLoading(false);
        // hide after a short delay so user sees completion
        setTimeout(() => {
            const progressWrap = document.getElementById('downloadProgressWrap');
            if (progressWrap) progressWrap.style.display = 'none';
        }, 2500);
    }
}


function ListingAllFormats(sortedFormats) {
    const container = document.getElementById('formatsContainer');
    container.innerHTML = '';

    // Create new containers each render
    const videoContainer = document.createElement('div');
    videoContainer.className = 'formats-section';
    videoContainer.innerHTML = '<h3>Video Formats</h3>';
    
    const audioContainer = document.createElement('div');
    audioContainer.className = 'formats-section';
    audioContainer.innerHTML = '<h3>Audio Formats</h3>';

    sortedFormats.forEach(format => {
        
        const targetContainer = format.format.includes('audio') ? audioContainer : videoContainer;
        const card = document.createElement('div');
        card.className = 'format-card';
        
        card.innerHTML = `
            <label class="select-format">
                <input type="radio" name="${format.format.includes('audio') ? 'audioFormat' : 'videoFormat'}" 
                    value="${format.url}" 
                    data-format='${JSON.stringify(format).replace(/'/g, "\\'")}'
                    ${window.selectedFormats?.[format.format.includes('audio') ? 'audio' : 'video']?.url === format.url ? 'checked' : ''}>
                Select for combined download
            </label>
            <p>Format: ${format.format}</p>
            ${format.codec ? `<p>Codec: ${format.codec}</p>` : ''}
            `;
        if(format.format.includes('audio')){
            card.innerHTML += `
                <p>Bitrate: ${format.bitrate || 'N/A'} kbps</p>
                <p>Sample Rate: .${format.sampleRate}</p>
                `;
        }
        card.innerHTML += `
            <p>Extension: .${format.extension}</p>
            <p>Filesize: ${(format.filesize / 1024 / 1024).toFixed(2)} MB</p>
            <button class="download-btn" onclick="downloadFormat('${format.url}', '${window.selectedFormats['currentFormat']}.${format.extension}')">
                Download via Proxy
            </button>
            <button class="direct-download-btn" onclick="window.open('${format.url}')" style="margin-left: 8px; background-color: #2196F3;">
                Direct Download
            </button>
        `;
        
            targetContainer.appendChild(card);
    });

    container.appendChild(videoContainer);
    container.appendChild(audioContainer);
}

// Handle format selection changes
document.addEventListener('change', (e) => {
    if (e.target.matches('input[type="radio"][name="videoFormat"], input[type="radio"][name="audioFormat"]')) {
        const formatType = e.target.name === 'videoFormat' ? 'video' : 'audio';
        const formatData = JSON.parse(e.target.dataset.format.replace(/\\'/g, "'"));
        window.selectedFormats[formatType] = formatData;
        UpdateCombineButton();
    }
});

function UpdateCombineButton(){
    // Update combine button state
    const combineBtn = document.getElementById('combineBtn');
    if (window.selectedFormats.video && window.selectedFormats.audio) {
        combineBtn.disabled = false;
        combineBtn.style.backgroundColor = '#4CAF50';
    } else {
        combineBtn.disabled = true;
        combineBtn.style.backgroundColor = '#9E9E9E';
    }
}

function downloadFormat(url, filename) {
    document.querySelectorAll('.download-btn').forEach(btn => btn.disabled = true);
    SetLoading(true);
    fetch('/proxy', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: url, original: window.selectedFormats['original'], filename: filename})
    })
    .then(response => {
        if (!response.ok) throw new Error('Combination failed');
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    })
    .then(()=>{
        SetLoading(false);
        document.querySelectorAll('.download-btn').forEach(btn => btn.disabled = false);
    });
}

function SetLoading(state){
    const loadingBar = document.getElementById('loadingBar');
    if(state){
        loadingBar.style.display = 'block';
    }
    else{
        loadingBar.style.display = 'none';
    }
}

// Auto-trigger when page loads with URL parameter
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const vID = urlParams.get('v');
    if (vID) {
        document.getElementById('urlInput').value = vID;
        fetchFormats();
    }
});
