async function fetchFormats() {
    const url = document.getElementById('urlInput').value;
    const formatList = document.getElementById('formatList');
    formatList.innerHTML = 'Loading...';

    try {
        const response = await fetch('http://localhost:8000/formats', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        const formats = await response.json();
        displayFormats(formats);
    } catch (error) {
        formatList.innerHTML = 'Error fetching formats';
        console.error('Error:', error);
    }
}

function displayFormats(formats) {
    const formatList = document.getElementById('formatList');
    formatList.innerHTML = '';

    formats.forEach(format => {
        const formatDiv = document.createElement('div');
        formatDiv.className = 'format-item';
        
        formatDiv.innerHTML = `
            <input type="radio" name="format" value="${format.format_id}">
            <div>${format.resolution || `${format.bitrate}kbps`}</div>
            <div>${format.extension.toUpperCase()}</div>
            <div>${format.filesize ? (format.filesize/1024/1024).toFixed(2) + 'MB' : 'N/A'}</div>
            <button onclick="downloadFormat('${format.format_id}')">Download</button>
        `;
        
        formatList.appendChild(formatDiv);
    });
}

async function downloadFormat(formatId) {
    const combine = document.getElementById('combineCheckbox').checked;
    const url = document.getElementById('urlInput').value;

    try {
        const response = await fetch('http://localhost:8000/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                format_id: formatId,
                combine: combine
            })
        });

        if (response.ok) {
            // Start polling for download completion
            const pollInterval = setInterval(async () => {
                try {
                    const downloadResponse = await fetch(response.download_url);
                    if (downloadResponse.ok) {
                        clearInterval(pollInterval);
                        window.location.href = response.download_url;
                    }
                } catch (error) {
                    console.error('Polling error:', error);
                }
            }, 2000);
        } else {
            alert('Download failed!');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Download error!');
    }
}
