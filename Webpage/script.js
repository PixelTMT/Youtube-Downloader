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

function CombineDownload(){
    if (!window.selectedFormats.video || !window.selectedFormats.audio) {
        alert('Please select both video and audio formats');
        return;
    }
    
    const combineBtn = document.getElementById('combineBtn');
    combineBtn.disabled = true;
    SetLoading(true);
    
    fetch('/combine', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            videoURL: window.selectedFormats.video.url,
            audioURL: window.selectedFormats.audio.url,
            filename: window.selectedFormats['currentFormat'] // Sanitize filename
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Combination failed');
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${window.selectedFormats['currentFormat']}.mp4`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to combine formats. Please try again.');
    })
    .finally(() => {
        const combineBtn = document.getElementById('combineBtn');
        combineBtn.disabled = false;
        SetLoading(false);
    });
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
                Download
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
