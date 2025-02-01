async function fetchFormats() {
    const url = document.getElementById('urlInput').value;
    const container = document.getElementById('formatsContainer');
    
    try {
        const response = await fetch('/formats', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });

        if (!response.ok) throw new Error('Failed to fetch formats');
        
        const formats = await response.json();
        container.innerHTML = ''; // Clear previous results

        // Create separate containers for video and audio
        const videoContainer = document.createElement('div');
        videoContainer.className = 'formats-section';
        videoContainer.innerHTML = '<h3>Video Formats</h3>';
        
        const audioContainer = document.createElement('div');
        audioContainer.className = 'formats-section';
        audioContainer.innerHTML = '<h3>Audio Formats</h3>';

        // Sort formats by filesize descending
        const sortedFormats = formats.sort((a, b) => b.filesize - a.filesize);
        
        // Get checkbox state
        const hideNoCodec = document.getElementById('hideNoCodecCheckbox').checked;

        sortedFormats.forEach(format => {
            if (hideNoCodec && (!format.codec || format.codec === 'none')) return;
            
            const container = format.format.includes('audio') ? audioContainer : videoContainer;
            const card = document.createElement('div');
            card.className = 'format-card';
            
            card.innerHTML = `
                <p>Format: ${format.format}</p>
                ${format.codec ? `<p>Codec: ${format.codec}</p>` : ''}`;
            if(format.format.includes('audio')){
                card.innerHTML += `
                    <p>Bitrate: ${format.bitrate || 'N/A'} kbps</p>
                    <p>Sample Rate: .${format.sampleRate}</p>
                    `;
            }
            card.innerHTML += `
                <p>Extension: .${format.extension}</p>
                <p>Filesize: ${(format.filesize / 1024 / 1024).toFixed(2)} MB</p>
                <button class="download-btn" onclick="downloadFormat('${format.url}')">
                    Download
                </button>
            `;
            
            container.appendChild(card);
        });

        container.innerHTML = '';
        container.appendChild(videoContainer);
        container.appendChild(audioContainer);
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to fetch formats. Please check the URL and try again.');
    }
}

function downloadFormat(url) {
    const link = document.createElement('a');
    link.href = url;
    link.download = true;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
