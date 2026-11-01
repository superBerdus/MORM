/* Independent output measurement. Never recalibrates or silently warps the image. */
function metricDistance(a, b, ppm) {
    if (!(Number.isFinite(ppm) && ppm > 0)) throw new Error('Invalid pixel density.');
    return Math.hypot(b[0] - a[0], b[1] - a[1]) / ppm;
}

class MeasurementTool {
    constructor() {
        this.dialog = document.getElementById('measureDialog');
        this.canvas = document.getElementById('measureCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.wrap = document.getElementById('measureCanvasWrap');
        this.known = document.getElementById('measureKnown');
        this.readout = document.getElementById('measureReadout');
        this.points = []; this.records = []; this.image = null; this.drag = null;
        this.scale = 1; this.panX = 0; this.panY = 0;
        document.getElementById('measureClose').onclick = () => this.close();
        document.getElementById('measureReset').onclick = () => { this.points = []; this.render(); };
        document.getElementById('measureFit').onclick = () => this.fit();
        document.getElementById('measureSave').onclick = () => this.save();
        this.known.oninput = () => this.updateReadout();
        this.canvas.addEventListener('pointerdown', e => this.down(e));
        this.canvas.addEventListener('pointermove', e => this.move(e));
        this.canvas.addEventListener('pointerup', e => this.up(e));
        this.canvas.addEventListener('pointercancel', () => { this.drag = null; });
        this.canvas.addEventListener('wheel', e => {
            if (!this.image) return;
            e.preventDefault();
            const [x,y] = this.screenPoint(e);
            const next = Math.max(.02, Math.min(25, this.scale * (e.deltaY < 0 ? 1.2 : 1/1.2)));
            this.panX = x-(x-this.panX)*next/this.scale;
            this.panY = y-(y-this.panY)*next/this.scale;
            this.scale = next; this.render();
        }, {passive:false});
        window.addEventListener('resize', () => { if (!this.dialog.hidden) this.resize(); });
        this.dialog.addEventListener('keydown', e => {
            if (e.key === 'Escape') this.close();
            // Keep keyboard focus inside the open dialog.
            if (e.key === 'Tab') {
                const nodes = [...this.dialog.querySelectorAll('button,input')].filter(n => !n.disabled);
                const first = nodes[0], last = nodes[nodes.length-1];
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
                else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
            }
        });
    }
    open(result) {
        this.lastFocus = document.activeElement;
        this.dialog.hidden = false;
        document.getElementById('measureClose').focus();
        if (this.result?.png_url === result.png_url && this.image) { this.resize(); return; }
        this.result = result; this.points = []; this.records = []; this.image = null;
        this.readout.textContent = 'Loading output image…';
        const image = new Image();
        const url = result.png_url;
        image.onload = () => {
            if (this.result.png_url !== url) return;
            this.image = image; this.resize(); this.fit();
        };
        image.onerror = () => { this.readout.textContent = 'Could not load the image.'; };
        image.src = url;
    }
    close() { this.dialog.hidden = true; this.drag = null; this.lastFocus?.focus(); }
    resize() {
        const r = this.wrap.getBoundingClientRect();
        this.canvas.width = Math.max(1,Math.floor(r.width));
        this.canvas.height = Math.max(1,Math.floor(r.height));
        this.render();
    }
    fit() {
        if (!this.image) return;
        this.scale = Math.min((this.canvas.width-32)/this.image.width, (this.canvas.height-32)/this.image.height);
        this.panX = (this.canvas.width-this.image.width*this.scale)/2;
        this.panY = (this.canvas.height-this.image.height*this.scale)/2;
        this.render();
    }
    screenPoint(e) {
        const r = this.canvas.getBoundingClientRect();
        return [(e.clientX-r.left)*this.canvas.width/r.width, (e.clientY-r.top)*this.canvas.height/r.height];
    }
    imagePoint(x,y) {
        return [Math.max(0,Math.min(this.image.width-1,(x-this.panX)/this.scale)),
                Math.max(0,Math.min(this.image.height-1,(y-this.panY)/this.scale))];
    }
    down(e) {
        if (!this.image || e.button !== 0) return;
        const [x,y] = this.screenPoint(e);
        const index = this.points.findIndex(p => Math.hypot(p[0]*this.scale+this.panX-x,p[1]*this.scale+this.panY-y)<15);
        this.drag = {index, x,y, panX:this.panX,panY:this.panY,moved:false};
        this.canvas.setPointerCapture(e.pointerId);
    }
    move(e) {
        if (!this.drag) return;
        const [x,y] = this.screenPoint(e), d = this.drag;
        if (Math.hypot(x-d.x,y-d.y)>3) d.moved = true;
        if (d.index>=0) this.points[d.index] = this.imagePoint(x,y);
        else if (d.moved) { this.panX = d.panX+x-d.x; this.panY = d.panY+y-d.y; }
        this.render();
    }
    up(e) {
        if (!this.drag) return;
        const [x,y] = this.screenPoint(e);
        if (!this.drag.moved && this.drag.index<0 && this.points.length<2) {
            const ix = (x-this.panX)/this.scale, iy=(y-this.panY)/this.scale;
            if (ix>=0 && iy>=0 && ix<this.image.width && iy<this.image.height) this.points.push(this.imagePoint(x,y));
        }
        this.drag = null;
        if (this.canvas.hasPointerCapture(e.pointerId)) this.canvas.releasePointerCapture(e.pointerId);
        this.render();
    }
    measurement() {
        if (this.points.length !== 2) return null;
        const expected = Number(this.known.value);
        if (!(Number.isFinite(expected) && expected>0)) return null;
        const measured = metricDistance(this.points[0],this.points[1],this.result.metadata.pixels_per_mm);
        return {points_px: this.points.map(p=>[...p]), expected_mm:expected, measured_mm:measured,
                error_mm:measured-expected, error_percent:100*(measured/expected-1)};
    }
    updateReadout() {
        const m = this.measurement();
        document.getElementById('measureSave').disabled = !m;
        if (this.points.length<2) this.readout.textContent = this.points.length ? 'Select point B.' : 'Select points A and B.';
        else if (!m) this.readout.textContent = 'Enter a positive known distance to compare.';
        else this.readout.textContent = `Measured: ${m.measured_mm.toFixed(2)} mm · Known: ${m.expected_mm.toFixed(2)} mm · Error: ${m.error_mm>=0?'+':''}${m.error_mm.toFixed(2)} mm (${m.error_percent.toFixed(2)}%) · Zoom: ${Math.round(this.scale*100)}%`;
    }
    render() {
        const c = this.ctx;
        c.clearRect(0,0,this.canvas.width,this.canvas.height);
        if (!this.image) return;
        c.drawImage(this.image,this.panX,this.panY,this.image.width*this.scale,this.image.height*this.scale);
        const pts = this.points.map(p=>[p[0]*this.scale+this.panX,p[1]*this.scale+this.panY]);
        if (pts.length===2) {
            c.beginPath(); c.moveTo(...pts[0]); c.lineTo(...pts[1]);
            c.strokeStyle = '#06b6d4'; c.lineWidth = 2; c.stroke();
        }
        pts.forEach(([x,y],i)=>{
            c.strokeStyle='#06b6d4'; c.lineWidth=2;
            c.beginPath();c.arc(x,y,8,0,Math.PI*2);c.stroke();
            c.beginPath();c.moveTo(x-13,y);c.lineTo(x+13,y);c.moveTo(x,y-13);c.lineTo(x,y+13);c.stroke();
            c.fillStyle='#020617';c.fillRect(x+15,y-23,24,24);
            c.fillStyle='#fff';c.font='bold 15px sans-serif';c.fillText(i?'B':'A',x+21,y-5);
        });
        this.updateReadout();
    }
    save() {
        const m = this.measurement();
        if (!m) return;
        this.records.push({...m,timestamp:new Date().toISOString()});
        const data = {output:this.result.png_url, metadata:this.result.metadata,
                      note:'User-selected independent distances only; not a whole-image accuracy certificate.',
                      checks:this.records};
        const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
        const link = document.createElement('a');link.href=url;link.download='morm-distance-checks.json';link.click();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
}

if (typeof module !== 'undefined') module.exports = {metricDistance};
