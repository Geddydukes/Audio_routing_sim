(function () {
  // Always connect to the API server on port 8000, regardless of which port serves the dashboard
  const API_HOST = "localhost:8000";
  
  const WS_URL = "ws://" + API_HOST + "/ws/metrics";
  
  console.log("WebSocket URL:", WS_URL);

  const statusEl = document.getElementById("ws-status");
  const nodesContainer = document.getElementById("nodes-container");
  const lastUpdateEl = document.getElementById("last-update");
  const globalTimelineContainer = document.getElementById("global-timeline-container");
  const globalTimelineCanvas = document.getElementById("global-timeline-canvas");
  const timelineTimeLabels = document.getElementById("timeline-time-labels");
  const timelinePanel = document.getElementById("timeline-panel");
  const audioControls = document.getElementById("audio-controls");
  const audioPlayer = document.getElementById("audio-player");
  const muteBtn = document.getElementById("mute-btn");

  /** Map nodeName -> DOM elements */
  const nodeRows = new Map();
  
  // Global audio state
  let currentAudioFile = null;
  let globalWaveformData = { data: null, duration: 0, fileId: null };
  let isMuted = false;

  function setStatus(connected) {
    statusEl.textContent = connected ? "Connected" : "Disconnected";
    statusEl.className =
      "status " + (connected ? "status-connected" : "status-disconnected");
  }

  function formatTime(ts) {
    if (!ts) return "—";
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString();
  }

  // Helper to get filename from path
  const Path = {
    basename: (path) => {
      return path.split('/').pop() || path;
    }
  };

  function formatDuration(seconds) {
    if (!seconds) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function drawWaveform(canvas, waveform, currentTime, duration) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const padding = 10;
    const drawWidth = width - padding * 2;
    const drawHeight = height - padding * 2;
    const centerY = height / 2;

    // Clear canvas
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, width, height);

    if (!waveform || waveform.length === 0 || duration === 0) return;

    // Draw waveform
    ctx.strokeStyle = "#4CAF50";
    ctx.fillStyle = "#4CAF50";
    ctx.lineWidth = 1;

    const pointsPerPixel = waveform.length / drawWidth;
    
    for (let x = 0; x < drawWidth; x++) {
      const startIdx = Math.floor(x * pointsPerPixel);
      const endIdx = Math.min(Math.floor((x + 1) * pointsPerPixel), waveform.length);
      
      if (startIdx >= waveform.length) break;
      
      // Get min/max for this pixel column
      let minVal = 0;
      let maxVal = 0;
      for (let i = startIdx; i < endIdx; i++) {
        if (waveform[i]) {
          minVal = Math.min(minVal, waveform[i].min);
          maxVal = Math.max(maxVal, waveform[i].max);
        }
      }
      
      // Normalize to -1 to 1, then scale to canvas height
      const minY = centerY + (minVal * drawHeight / 2);
      const maxY = centerY + (maxVal * drawHeight / 2);
      
      // Draw vertical line for this pixel
      ctx.beginPath();
      ctx.moveTo(padding + x, minY);
      ctx.lineTo(padding + x, maxY);
      ctx.stroke();
    }

    // Draw current position indicator
    if (duration > 0) {
      const positionX = padding + (currentTime / duration) * drawWidth;
      ctx.strokeStyle = "#FF6B6B";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(positionX, padding);
      ctx.lineTo(positionX, height - padding);
      ctx.stroke();
      
      // Draw position indicator circle
      ctx.fillStyle = "#FF6B6B";
      ctx.beginPath();
      ctx.arc(positionX, centerY, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    // Draw time markers
    ctx.strokeStyle = "#6b7280";
    ctx.lineWidth = 1;
    ctx.font = "10px monospace";
    ctx.fillStyle = "#9ca3af";
    
    const numMarkers = 5;
    for (let i = 0; i <= numMarkers; i++) {
      const time = (i / numMarkers) * duration;
      const x = padding + (time / duration) * drawWidth;
      const timeStr = formatDuration(time);
      
      // Draw tick
      ctx.beginPath();
      ctx.moveTo(x, height - padding);
      ctx.lineTo(x, height - padding + 5);
      ctx.stroke();
      
      // Draw time label
      ctx.fillText(timeStr, x - 15, height - padding + 18);
    }
  }

  function updateNodeRow(metric) {
    let row = nodeRows.get(metric.name);
    if (!row) {
      const card = document.createElement("div");
      card.className = "node-card";

      const meta = document.createElement("div");
      meta.className = "node-meta";

      const nameEl = document.createElement("div");
      nameEl.className = "node-name";
      nameEl.textContent = metric.name;

      const infoEl = document.createElement("div");
      infoEl.className = "node-info";

      const fileInfoEl = document.createElement("div");
      fileInfoEl.className = "file-info";

      const timelineContainer = document.createElement("div");
      timelineContainer.className = "timeline-container";
      const timelineCanvas = document.createElement("canvas");
      timelineCanvas.className = "timeline-canvas";
      // Set canvas size based on container (will be updated on first render)
      timelineCanvas.width = 800;
      timelineCanvas.height = 100;
      timelineContainer.appendChild(timelineCanvas);
      
      // Store waveform data separately to avoid re-sending it every update
      const waveformData = { data: null, duration: 0 };

      meta.appendChild(nameEl);
      meta.appendChild(infoEl);
      meta.appendChild(fileInfoEl);
      meta.appendChild(timelineContainer);

      const bar = document.createElement("div");
      bar.className = "level-bar";

      const barFill = document.createElement("div");
      barFill.className = "level-bar-fill";
      bar.appendChild(barFill);

      card.appendChild(meta);
      card.appendChild(bar);

      nodesContainer.appendChild(card);

      row = { 
        card, meta, nameEl, infoEl, fileInfoEl, 
        timelineContainer, timelineCanvas, barFill,
        waveformData: { data: null, duration: 0 }
      };
      nodeRows.set(metric.name, row);
    }

    const peakDb =
      metric.peak > 0 ? (20 * Math.log10(metric.peak)).toFixed(1) : "-∞";
    const rmsDb =
      metric.rms > 0 ? (20 * Math.log10(metric.rms)).toFixed(1) : "-∞";

    row.infoEl.textContent = `Peak: ${peakDb} dBFS | RMS: ${rmsDb} dBFS | ${metric.num_frames}f / ${metric.num_channels}ch`;

    // Display file info if available
    if (metric.file_info) {
      const fi = metric.file_info;
      const filePeakDb = fi.file_peak > 0 ? (20 * Math.log10(fi.file_peak)).toFixed(1) : "-∞";
      const fileRmsDb = fi.file_rms > 0 ? (20 * Math.log10(fi.file_rms)).toFixed(1) : "-∞";
      const currentTime = formatDuration(fi.current_time);
      const duration = formatDuration(fi.duration);
      const progress = fi.progress_percent.toFixed(1);
      
      row.fileInfoEl.innerHTML = `
        <strong>File:</strong> ${Path.basename(fi.file_path)}<br>
        <strong>Time:</strong> ${currentTime} / ${duration} (${progress}%)<br>
        <strong>File Peak:</strong> ${filePeakDb} dBFS | <strong>File RMS:</strong> ${fileRmsDb} dBFS
        ${fi.loop ? ' | <span style="color: #4CAF50;">LOOPING</span>' : ''}
      `;
      row.fileInfoEl.style.display = "block";
      
      // Don't show per-node timeline anymore (using global timeline)
      row.timelineContainer.style.display = "none";
    } else {
      row.fileInfoEl.style.display = "none";
      row.timelineContainer.style.display = "none";
    }

    // Normalize peak (0..1) into 0..100% width; clamp to [0, 1]
    const level = Math.max(0, Math.min(1, metric.peak));
    row.barFill.style.width = `${(level * 100).toFixed(1)}%`;
  }

  function updateGlobalTimeline(fileInfo) {
    if (!fileInfo || !fileInfo.waveform || fileInfo.waveform.length === 0) {
      timelinePanel.style.display = "none";
      return;
    }
    
    // Update waveform data if it's a new file
    if (globalWaveformData.duration !== fileInfo.duration) {
      globalWaveformData.data = fileInfo.waveform;
      globalWaveformData.duration = fileInfo.duration;
    }
    
    // Make canvas responsive
    const containerWidth = globalTimelineContainer.clientWidth || 1200;
    globalTimelineCanvas.width = containerWidth;
    globalTimelineCanvas.height = 200; // Larger height
    
    // Draw waveform
    drawGlobalWaveform(globalTimelineCanvas, globalWaveformData.data, fileInfo.current_time, fileInfo.duration);
    
    // Update time labels
    updateTimeLabels(fileInfo.duration, containerWidth);
    
    timelinePanel.style.display = "block";
  }

  function drawGlobalWaveform(canvas, waveform, currentTime, duration) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const padding = 20;
    const drawWidth = width - padding * 2;
    const drawHeight = height - padding * 2;
    const centerY = height / 2;

    // Clear canvas
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, width, height);

    if (!waveform || waveform.length === 0 || duration === 0) return;

    // Draw waveform with thicker lines for better visibility
    ctx.strokeStyle = "#4CAF50";
    ctx.fillStyle = "#4CAF50";
    ctx.lineWidth = 2;

    const pointsPerPixel = waveform.length / drawWidth;
    
    for (let x = 0; x < drawWidth; x++) {
      const startIdx = Math.floor(x * pointsPerPixel);
      const endIdx = Math.min(Math.floor((x + 1) * pointsPerPixel), waveform.length);
      
      if (startIdx >= waveform.length) break;
      
      // Get min/max for this pixel column
      let minVal = 0;
      let maxVal = 0;
      for (let i = startIdx; i < endIdx; i++) {
        if (waveform[i]) {
          minVal = Math.min(minVal, waveform[i].min);
          maxVal = Math.max(maxVal, waveform[i].max);
        }
      }
      
      // Normalize to -1 to 1, then scale to canvas height
      const minY = centerY + (minVal * drawHeight / 2);
      const maxY = centerY + (maxVal * drawHeight / 2);
      
      // Draw vertical line for this pixel
      ctx.beginPath();
      ctx.moveTo(padding + x, minY);
      ctx.lineTo(padding + x, maxY);
      ctx.stroke();
    }

    // Draw current position indicator (thicker for visibility)
    if (duration > 0) {
      const positionX = padding + (currentTime / duration) * drawWidth;
      ctx.strokeStyle = "#FF6B6B";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(positionX, padding);
      ctx.lineTo(positionX, height - padding);
      ctx.stroke();
      
      // Draw position indicator circle (larger)
      ctx.fillStyle = "#FF6B6B";
      ctx.beginPath();
      ctx.arc(positionX, centerY, 6, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function updateTimeLabels(duration, width) {
    const padding = 20;
    const drawWidth = width - padding * 2;
    const numMarkers = 10; // More markers for larger timeline
    
    timelineTimeLabels.innerHTML = "";
    timelineTimeLabels.style.width = `${width}px`;
    
    for (let i = 0; i <= numMarkers; i++) {
      const time = (i / numMarkers) * duration;
      const x = padding + (time / duration) * drawWidth;
      const timeStr = formatDuration(time);
      
      const label = document.createElement("div");
      label.className = "time-label";
      label.textContent = timeStr;
      label.style.left = `${x - 20}px`;
      timelineTimeLabels.appendChild(label);
    }
  }

  function handleSnapshot(snapshot) {
    lastUpdateEl.textContent = "Last update: " + formatTime(snapshot.timestamp);

    if (!Array.isArray(snapshot.nodes)) return;
    
    // Find audio file node and update global timeline
    let audioFileInfo = null;
    snapshot.nodes.forEach(node => {
      if (node.file_info) {
        audioFileInfo = node.file_info;
      }
      updateNodeRow(node);
    });
    
    // Update global timeline if we have audio file info
    if (audioFileInfo) {
      updateGlobalTimeline(audioFileInfo);
    }
  }

  function connect() {
    console.log("Connecting to WebSocket:", WS_URL);
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log("WebSocket connected");
      setStatus(true);
      // Optional: send a no-op ping periodically so the loop in server reads
      setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 5000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleSnapshot(data);
      } catch (e) {
        console.error("Failed to parse snapshot:", e);
      }
    };

    ws.onclose = (event) => {
      console.log("WebSocket closed:", event.code, event.reason);
      setStatus(false);
      // Retry with backoff
      setTimeout(connect, 1500);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      setStatus(false);
    };
  }

  setStatus(false);
  connect();

  // File upload handling
  const fileInput = document.getElementById("audio-file-input");
  const uploadBtn = document.getElementById("upload-btn");
  const uploadStatus = document.getElementById("upload-status");

  uploadBtn.addEventListener("click", () => {
    fileInput.click();
  });

  // Mute button handler
  muteBtn.addEventListener("click", () => {
    isMuted = !isMuted;
    audioPlayer.muted = isMuted;
    muteBtn.textContent = isMuted ? "🔇 Unmute" : "🔊 Mute";
  });

  fileInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    uploadStatus.textContent = `Uploading ${file.name}...`;
    uploadStatus.className = "upload-status uploading";
    uploadBtn.disabled = true;

    try {
      const formData = new FormData();
      formData.append("file", file);

      const API_URL = "http://localhost:8000/api/upload-audio";
      const response = await fetch(API_URL, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }

      const result = await response.json();
      uploadStatus.textContent = `✅ ${result.message}`;
      uploadStatus.className = "upload-status success";

      // Set up audio playback
      if (result.file_url) {
        currentAudioFile = result.file_id;
        const audioUrl = `http://${API_HOST}${result.file_url}`;
        audioPlayer.src = audioUrl;
        audioPlayer.loop = true;
        audioPlayer.muted = isMuted;
        
        // Force play - user has already interacted by clicking upload button
        const playPromise = audioPlayer.play();
        if (playPromise !== undefined) {
          playPromise
            .then(() => {
              console.log("Audio playing");
              audioControls.style.display = "flex";
            })
            .catch(err => {
              console.log("Auto-play prevented, trying again:", err);
              // Try again after a short delay
              setTimeout(() => {
                audioPlayer.play().catch(e => {
                  console.error("Failed to play audio:", e);
                  // Show play button as fallback
                  muteBtn.textContent = "▶️ Play";
                  muteBtn.onclick = () => {
                    audioPlayer.play().then(() => {
                      muteBtn.textContent = isMuted ? "🔇 Unmute" : "🔊 Mute";
                      muteBtn.onclick = () => {
                        isMuted = !isMuted;
                        audioPlayer.muted = isMuted;
                        muteBtn.textContent = isMuted ? "🔇 Unmute" : "🔊 Mute";
                      };
                    });
                  };
                });
              }, 100);
            });
        }
        audioControls.style.display = "flex";
      }

      // Reset file input
      fileInput.value = "";

      // Wait a moment, then clear status
      setTimeout(() => {
        uploadStatus.textContent = "";
        uploadStatus.className = "upload-status";
      }, 3000);
    } catch (error) {
      uploadStatus.textContent = `❌ Error: ${error.message}`;
      uploadStatus.className = "upload-status error";
      console.error("Upload error:", error);
    } finally {
      uploadBtn.disabled = false;
    }
  });
})();

