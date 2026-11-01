/**
 * MORM - Frontend controller and precision canvas
 */

class MormApp {
    constructor() {
        this.imageId = null;
        this.image = null;
        this.imageWidth = 0;
        this.imageHeight = 0;

        // Four corner pins in image coordinates [x, y]
        this.corners = [];
        this.activePointIndex = -1;
        this.hoverPointIndex = -1;

        // Two points for ruler mode
        this.rulerPoints = [];
        this.activeRulerIndex = -1;
        this.hoverRulerIndex = -1;

        // Canvas transform (pan and zoom)
        this.scale = 1.0;
        this.panX = 0;
        this.panY = 0;
        this.isPanning = false;
        this.startPanX = 0;
        this.startPanY = 0;

        // Generated Blender script
        this.currentBlenderScript = "";

        // DOM elements
        this.canvas = document.getElementById('mainCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.canvasContainer = document.getElementById('canvasContainer');
        this.canvasWrapper = document.getElementById('canvasWrapper');
        this.emptyState = document.getElementById('emptyState');
        this.fileInput = document.getElementById('fileInput');
        this.uploadDropzone = document.getElementById('uploadDropzone');
        this.processBtn = document.getElementById('processBtn');
        this.toolbarStatus = document.getElementById('toolbarStatus');
        this.outputPanel = document.getElementById('outputPanel');
        this.closeOutputBtn = document.getElementById('closeOutputBtn');
        this.resetZoomBtn = document.getElementById('resetZoomBtn');
        this.autoCornersBtn = document.getElementById('autoCornersBtn');
        this.zoomInBtn = document.getElementById('zoomInBtn');
        this.zoomOutBtn = document.getElementById('zoomOutBtn');
        this.zoomLevel = document.getElementById('zoomLevel');
        this.copyScriptBtn = document.getElementById('copyScriptBtn');
        this.modeHelpBanner = document.getElementById('modeHelpBanner');

        // Precision loupe
        this.loupe = document.getElementById('loupe');
        this.loupeCanvas = document.getElementById('loupeCanvas');
        this.loupeCtx = this.loupeCanvas.getContext('2d');
        this.loupeLabel = document.getElementById('loupeLabel');

        // Mode selection
        this.modeOptions = document.querySelectorAll('input[name="refMode"]');
        this.customDimsRow = document.getElementById('customDimsRow');
        this.rulerRow = document.getElementById('rulerRow');

        this.measureTool = new MeasurementTool();
        document.getElementById('verifyBtn').addEventListener('click', () => {
            if (this.lastResult) this.measureTool.open(this.lastResult);
        });
        this.initEventListeners();
        this.resizeCanvas();
        this.updateModeBanner();
    }

    initEventListeners() {
        window.addEventListener('resize', () => this.resizeCanvas());

        // File upload events
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        this.uploadDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadDropzone.classList.add('drag-over');
        });
        this.uploadDropzone.addEventListener('dragleave', () => {
            this.uploadDropzone.classList.remove('drag-over');
        });
        this.uploadDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadDropzone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                this.uploadFile(e.dataTransfer.files[0]);
            }
        });

        // Clipboard paste (Ctrl+V)
        window.addEventListener('paste', (e) => {
            if (e.clipboardData.files.length > 0) {
                this.uploadFile(e.clipboardData.files[0]);
            }
        });

        // Handle mode changes
        this.modeOptions.forEach(opt => {
            opt.addEventListener('change', () => this.handleModeChange());
        });

        // Canvas pointer events
        this.canvas.addEventListener('pointerdown', (e) => { e.preventDefault(); this.canvas.setPointerCapture(e.pointerId); this.handleMouseDown(e); });
        window.addEventListener('pointermove', (e) => this.handleMouseMove(e));
        window.addEventListener('pointerup', () => this.handleMouseUp());
        window.addEventListener('pointercancel', () => this.handleMouseUp());
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault()); // Prevent the context menu (used for panning)
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });

        // Toolbar buttons
        this.resetZoomBtn.addEventListener('click', () => this.fitImageToView());
        this.zoomInBtn.addEventListener('click', () => this.zoomStep(1.25));
        this.zoomOutBtn.addEventListener('click', () => this.zoomStep(0.8));
        this.autoCornersBtn.addEventListener('click', () => this.detectCorners());
        this.processBtn.addEventListener('click', () => this.processImage());
        this.closeOutputBtn.addEventListener('click', () => {
            this.outputPanel.style.display = 'none';
        });

        // Copy the Blender script
        this.copyScriptBtn.addEventListener('click', () => this.copyBlenderScript());
    }

    resizeCanvas() {
        const rect = this.canvasWrapper.getBoundingClientRect();
        this.canvas.width = Math.max(1, Math.round(rect.width));
        this.canvas.height = Math.max(1, Math.round(rect.height));
        // A viewport resize may radically change the available canvas size
        // (especially when moving between desktop and mobile layouts). Refit the
        // image to avoid carrying an obsolete pan/zoom transform into the new area.
        if (this.image) this.fitImageToView();
        else this.render();
    }

    updateModeBanner() {
        const currentMode = document.querySelector('input[name="refMode"]:checked').value;
        const banners = {
            'a4_portrait': 'ℹ️ <strong>A4 Portrait:</strong> Align P1–P4 with the paper’s four outer corners. Perspective is rectified to 210 × 297 mm; keep the reference and measured surface coplanar.',
            'a4_landscape': 'ℹ️ <strong>A4 Landscape:</strong> Align P1–P4 with the paper’s four outer corners. Perspective is rectified to 297 × 210 mm; keep the reference and measured surface coplanar.',
            'card': 'ℹ️ <strong>Credit/ID Card:</strong> Align P1–P4 with the card’s four corners (standard size: 85.6 × 54.0 mm).',
            'a3_portrait': 'ℹ️ <strong>A3 Paper:</strong> Align P1–P4 with the paper’s four outer corners (297 × 420 mm).',
            'custom': 'ℹ️ <strong>Custom Size:</strong> Align P1–P4 with a known rectangular reference, then enter its measured width and height in millimeters.',
            'ruler': '🎯 <strong>Ruler Mode:</strong> Place R1 and R2 on two known ruler marks (e.g. 0–10 cm = 100 mm). Uniform scaling only; perspective and lens distortion are not corrected.'
        };
        this.modeHelpBanner.innerHTML = banners[currentMode] || '';
    }

    handleModeChange() {
        const currentMode = document.querySelector('input[name="refMode"]:checked').value;
        this.customDimsRow.style.display = (currentMode === 'custom') ? 'grid' : 'none';
        this.rulerRow.style.display = (currentMode === 'ruler') ? 'block' : 'none';
        this.updateModeBanner();

        // The desktop layout keeps the workspace viewport fixed while the
        // sidebar scrolls independently, so mode-specific fields never stretch
        // the preview or reset its zoom.
        this.render();
    }

    handleFileSelect(e) {
        if (e.target.files.length > 0) {
            this.uploadFile(e.target.files[0]);
        }
    }

    async uploadFile(file) {
        this.toolbarStatus.textContent = "Uploading image and detecting corners…";
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            if (!res.ok) throw new Error(await this.apiError(res));
            const data = await res.json();

            this.outputPanel.style.display = 'none';
            this.lastResult = null;
            this.currentBlenderScript = '';
            this.imageId = data.image_id;
            this.imageWidth = data.width;
            this.imageHeight = data.height;

            const img = new Image();
            img.src = data.image_url;
            img.onload = () => {
                this.image = img;
                this.emptyState.style.display = 'none';
                this.corners = data.corners || [
                    [data.width * 0.1, data.height * 0.1],
                    [data.width * 0.9, data.height * 0.1],
                    [data.width * 0.9, data.height * 0.9],
                    [data.width * 0.1, data.height * 0.9]
                ];

                // Initial ruler points near the image center
                this.rulerPoints = [
                    [data.width * 0.3, data.height * 0.5],
                    [data.width * 0.7, data.height * 0.5]
                ];

                this.fitImageToView();
                this.processBtn.disabled = false;
                this.toolbarStatus.textContent = `Uploaded: ${file.name} · ${data.detected ? 'Check the suggested corners.' : 'No reference found; set the corners manually.'}`;
            };
        } catch (err) {
            alert("Upload error: " + err.message);
            this.toolbarStatus.textContent = "Upload failed.";
        }
    }

    async apiError(res) {
        const data = await res.json().catch(() => ({}));
        return typeof data.detail === 'string' ? data.detail : 'Invalid input or processing failed (HTTP ' + res.status + ').';
    }

    async detectCorners() {
        if (!this.imageId) return;
        try {
            const res = await fetch('/api/corners/' + encodeURIComponent(this.imageId));
            if (!res.ok) throw new Error(await this.apiError(res));
            const data = await res.json();
            this.corners = data.corners;
            this.toolbarStatus.textContent = data.detected ? 'Corner suggestions found. Check all four points with the loupe.' : 'No reference found. Position the default points manually.';
            this.render();
        } catch (e) { this.toolbarStatus.textContent = e.message; }
    }

    fitImageToView() {
        if (!this.image) return;
        const pad = 40;
        const availableW = this.canvas.width - pad * 2;
        const availableH = this.canvas.height - pad * 2;

        const scaleW = availableW / this.imageWidth;
        const scaleH = availableH / this.imageHeight;
        this.scale = Math.min(scaleW, scaleH, 1.0);

        this.panX = (this.canvas.width - this.imageWidth * this.scale) / 2;
        this.panY = (this.canvas.height - this.imageHeight * this.scale) / 2;
        this.updateZoomIndicator();
        this.render();
    }

    zoomStep(factor) {
        if (!this.image) return;
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        const newScale = Math.max(0.05, Math.min(30.0, this.scale * factor));

        this.panX = centerX - (centerX - this.panX) * (newScale / this.scale);
        this.panY = centerY - (centerY - this.panY) * (newScale / this.scale);
        this.scale = newScale;

        this.updateZoomIndicator();
        this.render();
    }

    updateZoomIndicator() {
        this.zoomLevel.textContent = `${Math.round(this.scale * 100)}%`;
    }

    // Pointer coordinates are CSS pixels; drawing coordinates use the canvas
    // backing-store dimensions. The canvas can be stretched by responsive CSS,
    // so explicitly map between the two coordinate spaces.
    eventToCanvas(e) {
        const rect = this.canvas.getBoundingClientRect();
        const sx = rect.width ? this.canvas.width / rect.width : 1;
        const sy = rect.height ? this.canvas.height / rect.height : 1;
        return {
            x: (e.clientX - rect.left) * sx,
            y: (e.clientY - rect.top) * sy,
            scaleX: sx,
            scaleY: sy
        };
    }

    // Coordinate transforms
    screenToImg(sx, sy) {
        return {
            x: (sx - this.panX) / this.scale,
            y: (sy - this.panY) / this.scale
        };
    }

    imgToScreen(ix, iy) {
        return {
            x: ix * this.scale + this.panX,
            y: iy * this.scale + this.panY
        };
    }

    handleMouseDown(e) {
        if (!this.image) return;
        const { x: mouseX, y: mouseY } = this.eventToCanvas(e);
        const currentMode = document.querySelector('input[name="refMode"]:checked').value;
        const hitRadius = 24;

        // In ruler mode, only R1 and R2 are draggable
        if (currentMode === 'ruler') {
            for (let i = 0; i < this.rulerPoints.length; i++) {
                const s = this.imgToScreen(this.rulerPoints[i][0], this.rulerPoints[i][1]);
                if (Math.hypot(s.x - mouseX, s.y - mouseY) <= hitRadius) {
                    this.activeRulerIndex = i;
                    this.showLoupe(e.clientX, e.clientY, this.rulerPoints[i], `R${i + 1}`);
                    return;
                }
            }
        } else {
            // In other modes, P1–P4 are draggable
            for (let i = 0; i < this.corners.length; i++) {
                const s = this.imgToScreen(this.corners[i][0], this.corners[i][1]);
                if (Math.hypot(s.x - mouseX, s.y - mouseY) <= hitRadius) {
                    this.activePointIndex = i;
                    this.showLoupe(e.clientX, e.clientY, this.corners[i], `P${i + 1}`);
                    return;
                }
            }
        }

        // If no pin was selected, pan the canvas
        this.isPanning = true;
        this.startPanX = mouseX - this.panX;
        this.startPanY = mouseY - this.panY;
        this.canvas.style.cursor = 'grabbing';
    }

    handleMouseMove(e) {
        if (!this.image) return;
        const { x: mouseX, y: mouseY } = this.eventToCanvas(e);
        const currentMode = document.querySelector('input[name="refMode"]:checked').value;

        // Is a corner pin being dragged?
        if (this.activePointIndex >= 0) {
            const imgCoord = this.screenToImg(mouseX, mouseY);
            this.corners[this.activePointIndex] = [
                Math.max(0, Math.min(this.imageWidth - 1, imgCoord.x)),
                Math.max(0, Math.min(this.imageHeight - 1, imgCoord.y))
            ];
            this.showLoupe(e.clientX, e.clientY, this.corners[this.activePointIndex], `P${this.activePointIndex + 1}`);
            this.render();
            return;
        }

        // Is a ruler pin being dragged?
        if (this.activeRulerIndex >= 0) {
            const imgCoord = this.screenToImg(mouseX, mouseY);
            this.rulerPoints[this.activeRulerIndex] = [
                Math.max(0, Math.min(this.imageWidth - 1, imgCoord.x)),
                Math.max(0, Math.min(this.imageHeight - 1, imgCoord.y))
            ];
            this.showLoupe(e.clientX, e.clientY, this.rulerPoints[this.activeRulerIndex], `R${this.activeRulerIndex + 1}`);
            this.render();
            return;
        }

        // Is the canvas being panned?
        if (this.isPanning) {
            this.panX = mouseX - this.startPanX;
            this.panY = mouseY - this.startPanY;
            this.render();
            return;
        }

        // Hover detection
        const hitRadius = 24;
        let foundHover = false;

        if (currentMode === 'ruler') {
            for (let i = 0; i < this.rulerPoints.length; i++) {
                const s = this.imgToScreen(this.rulerPoints[i][0], this.rulerPoints[i][1]);
                if (Math.hypot(s.x - mouseX, s.y - mouseY) <= hitRadius) {
                    foundHover = true;
                    break;
                }
            }
        } else {
            for (let i = 0; i < this.corners.length; i++) {
                const s = this.imgToScreen(this.corners[i][0], this.corners[i][1]);
                if (Math.hypot(s.x - mouseX, s.y - mouseY) <= hitRadius) {
                    foundHover = true;
                    break;
                }
            }
        }

        this.canvas.style.cursor = foundHover ? 'pointer' : 'crosshair';
    }

    handleMouseUp() {
        this.activePointIndex = -1;
        this.activeRulerIndex = -1;
        this.isPanning = false;
        this.hideLoupe();
        if (this.image) {
            this.canvas.style.cursor = 'crosshair';
        }
    }

    handleWheel(e) {
        if (!this.image) return;
        e.preventDefault();

        const pointer = this.eventToCanvas(e);

        // Shift + wheel pans horizontally
        if (e.shiftKey) {
            this.panX -= e.deltaY * pointer.scaleX * 0.8;
            this.render();
            return;
        }

        // Mouse wheel zoom
        const mouseX = pointer.x;
        const mouseY = pointer.y;

        const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
        const newScale = Math.max(0.05, Math.min(30.0, this.scale * zoomFactor));

        this.panX = mouseX - (mouseX - this.panX) * (newScale / this.scale);
        this.panY = mouseY - (mouseY - this.panY) * (newScale / this.scale);
        this.scale = newScale;

        this.updateZoomIndicator();
        this.render();
    }

    // Smart loupe placement keeps it inside the viewport
    showLoupe(clientX, clientY, imgCoord, label) {
        this.loupe.style.display = 'block';
        const containerRect = this.canvasContainer.getBoundingClientRect();
        const loupeSize = 220;

        // Default: open above and to the right of the cursor
        let targetX = (clientX - containerRect.left) + 30;
        let targetY = (clientY - containerRect.top) - (loupeSize + 20);

        // If it would overflow the right edge, move it to the left of the cursor.
        if (targetX + loupeSize > containerRect.width - 20) {
            targetX = (clientX - containerRect.left) - loupeSize - 30;
        }
        targetX = Math.max(15, targetX);

        // If it would overflow the top edge, move it below the cursor.
        if (targetY < 20) {
            targetY = (clientY - containerRect.top) + 30;
        }
        if (targetY + loupeSize > containerRect.height - 20) {
            targetY = containerRect.height - loupeSize - 20;
        }

        this.loupe.style.left = `${targetX}px`;
        this.loupe.style.top = `${targetY}px`;
        this.loupeLabel.textContent = label;

        // Draw a sharp 5x loupe
        const lw = this.loupeCanvas.width;
        const lh = this.loupeCanvas.height;
        const zoom = 5.0;

        this.loupeCtx.clearRect(0, 0, lw, lh);
        this.loupeCtx.save();
        this.loupeCtx.imageSmoothingEnabled = false; // Preserve sharp pixels

        const cropW = lw / zoom;
        const cropH = lh / zoom;
        const cropX = imgCoord[0] - cropW / 2;
        const cropY = imgCoord[1] - cropH / 2;

        this.loupeCtx.drawImage(
            this.image,
            cropX, cropY, cropW, cropH,
            0, 0, lw, lh
        );
        this.loupeCtx.restore();
    }

    hideLoupe() {
        this.loupe.style.display = 'none';
    }

    render() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        if (!this.image) return;

        // Draw the image
        this.ctx.save();
        this.ctx.drawImage(
            this.image,
            this.panX, this.panY,
            this.imageWidth * this.scale,
            this.imageHeight * this.scale
        );
        this.ctx.restore();

        const currentMode = document.querySelector('input[name="refMode"]:checked').value;

        // In ruler mode, show R1–R2 and hide P1–P4
        if (currentMode === 'ruler') {
            if (this.rulerPoints.length === 2) {
                const r1 = this.imgToScreen(this.rulerPoints[0][0], this.rulerPoints[0][1]);
                const r2 = this.imgToScreen(this.rulerPoints[1][0], this.rulerPoints[1][1]);

                this.ctx.save();
                this.ctx.beginPath();
                this.ctx.moveTo(r1.x, r1.y);
                this.ctx.lineTo(r2.x, r2.y);
                this.ctx.strokeStyle = '#06b6d4';
                this.ctx.lineWidth = 3.5;
                this.ctx.stroke();

                // Distance label
                const midX = (r1.x + r2.x) / 2;
                const midY = (r1.y + r2.y) / 2;
                const rulerLenVal = document.getElementById('rulerLength').value || 100;
                this.ctx.font = '700 13px Outfit, sans-serif';
                this.ctx.fillStyle = '#06b6d4';
                this.ctx.shadowColor = 'rgba(0,0,0,0.9)';
                this.ctx.shadowBlur = 6;
                this.ctx.fillText(`📏 ${rulerLenVal} mm`, midX + 10, midY - 10);
                this.ctx.restore();

                this.drawPin(r1.x, r1.y, 9, '#06b6d4', '#fff', 'R1 (Start)');
                this.drawPin(r2.x, r2.y, 9, '#06b6d4', '#fff', 'R2 (End)');
            }
        } else {
            // In rectangle modes, draw the quadrilateral and P1–P4
            if (this.corners.length === 4) {
                const screenPts = this.corners.map(c => this.imgToScreen(c[0], c[1]));

                this.ctx.save();
                this.ctx.beginPath();
                this.ctx.moveTo(screenPts[0].x, screenPts[0].y);
                this.ctx.lineTo(screenPts[1].x, screenPts[1].y);
                this.ctx.lineTo(screenPts[2].x, screenPts[2].y);
                this.ctx.lineTo(screenPts[3].x, screenPts[3].y);
                this.ctx.closePath();

                this.ctx.fillStyle = 'rgba(99, 102, 241, 0.18)';
                this.ctx.fill();

                this.ctx.strokeStyle = '#6366f1';
                this.ctx.lineWidth = 2.5;
                this.ctx.setLineDash([6, 4]);
                this.ctx.stroke();
                this.ctx.restore();

                const pointLabels = ['P1 (Top left)', 'P2 (Top right)', 'P3 (Bottom right)', 'P4 (Bottom left)'];
                screenPts.forEach((pt, i) => {
                    const isActive = (this.activePointIndex === i);
                    this.drawPin(pt.x, pt.y, isActive ? 10 : 8, '#6366f1', isActive ? '#818cf8' : '#fff', pointLabels[i]);
                });
            }
        }
    }

    drawPin(x, y, radius, strokeColor, fillColor, label) {
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
        this.ctx.fillStyle = fillColor;
        this.ctx.fill();
        this.ctx.lineWidth = 3;
        this.ctx.strokeStyle = strokeColor;
        this.ctx.stroke();

        this.ctx.font = '600 11px Outfit, sans-serif';
        this.ctx.fillStyle = '#f8fafc';
        this.ctx.shadowColor = 'rgba(0,0,0,0.9)';
        this.ctx.shadowBlur = 4;
        this.ctx.fillText(label, x + 12, y - 6);
        this.ctx.restore();
    }

    async processImage() {
        if (!this.imageId) return;

        this.processBtn.disabled = true;
        this.processBtn.innerHTML = `<span>⏳ Processing and rectifying…</span>`;
        this.toolbarStatus.textContent = "Rectifying image to the known reference…";

        const currentMode = document.querySelector('input[name="refMode"]:checked').value;
        const customW = parseFloat(document.getElementById('customWidth').value);
        const customH = parseFloat(document.getElementById('customHeight').value);
        const ppm = parseFloat(document.getElementById('pixelsPerMm').value);
        const margin = parseFloat(document.getElementById('marginMm').value);
        const rulerLen = parseFloat(document.getElementById('rulerLength').value);

        const payload = {
            image_id: this.imageId,
            corners: this.corners,
            mode: currentMode,
            custom_width_mm: customW,
            custom_height_mm: customH,
            pixels_per_mm: ppm,
            margin_mm: margin,
            ruler_pt1: this.rulerPoints[0],
            ruler_pt2: this.rulerPoints[1],
            ruler_length_mm: rulerLen
        };

        try {
            const res = await fetch("/api/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error(await this.apiError(res));
            const data = await res.json();

            this.currentBlenderScript = data.blender_script_code || "";
            this.showResults(data);
            this.toolbarStatus.textContent = "Output ready. Verify it with an independent distance check.";
        } catch (err) {
            alert("Processing error: " + err.message);
            this.toolbarStatus.textContent = "Rectification failed.";
        } finally {
            this.processBtn.disabled = false;
            this.processBtn.innerHTML = `<span class="btn-icon">✨</span><span>Rectify to Reference</span>`;
        }
    }

    showResults(data) {
        this.lastResult = data;
        const meta = data.metadata;
        document.getElementById('accuracyWarning').textContent = (meta.warnings || []).join(' ');
        document.getElementById('downloadMetadataBtn').href = data.download.metadata;
        document.getElementById('rectifiedImg').src = `${data.png_url}?t=${Date.now()}`;

        const metaBox = document.getElementById('metaBox');
        metaBox.innerHTML = `
            <div><strong>Width:</strong> ${meta.width_mm.toFixed(2)} mm (${meta.width_px} px)</div>
            <div><strong>Height:</strong> ${meta.height_mm.toFixed(2)} mm (${meta.height_px} px)</div>
            <div><strong>Sampling:</strong> 1 mm = ${meta.pixels_per_mm} piksel (${(1/meta.pixels_per_mm).toFixed(3)} mm/px)</div>
            <div><strong>Blender Unit:</strong> Metric Millimeters (1 BU = 1 mm)</div>
        `;

        document.getElementById('downloadPngBtn').href = data.download.png;
        document.getElementById('downloadScriptBtn').href = data.download.blender;
        document.getElementById('downloadSvgBtn').href = data.download.svg;

        this.outputPanel.style.display = 'flex';
    }

    copyBlenderScript() {
        if (!this.currentBlenderScript) {
            alert("Please rectify an image first.");
            return;
        }

        navigator.clipboard.writeText(this.currentBlenderScript).then(() => {
            const origHtml = this.copyScriptBtn.innerHTML;
            this.copyScriptBtn.innerHTML = "✅ Copied! (Ctrl + V in Blender)";
            this.copyScriptBtn.style.background = "linear-gradient(135deg, #10b981, #059669)";
            setTimeout(() => {
                this.copyScriptBtn.innerHTML = origHtml;
                this.copyScriptBtn.style.background = "";
            }, 3000);
        }).catch(err => {
            alert("Could not copy script: " + err);
        });
    }
}

// Initialize the application
window.addEventListener('DOMContentLoaded', () => {
    window.app = new MormApp();
});
