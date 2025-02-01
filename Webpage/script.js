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

        formats.forEach(format => {
            const card = document.createElement('div');
            card.className = 'format-card';
            
            card.innerHTML = `
                <p>Format: ${format.format}</p>
                <p>Codec: ${format.codec}</p>
                <p>Bitrate: ${format.bitrate || 'N/A'} kbps</p>
                <p>Extension: .${format.extension}</p>
                <p>Filesize: ${(format.filesize / 1024 / 1024).toFixed(2)} MB</p>
                <button class="download-btn" onclick="downloadFormat('${format.url}')">
                    Download
                </button>
            `;
            
            container.appendChild(card);
        });
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
