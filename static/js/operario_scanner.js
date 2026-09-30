// static/js/operario_scanner.js - Mobile Barcode/QR Scanner controller
class OperarioScanner {
  constructor(videoElementId, onDetectedCallback) {
    this.video = document.getElementById(videoElementId);
    this.onDetected = onDetectedCallback;
    this.stream = null;
    this.detector = null;
    this.active = false;
    this.scanInterval = null;
  }

  async start() {
    if (!this.video) return false;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } }
      });
      this.video.srcObject = this.stream;
      await this.video.play();
      this.active = true;

      // Check BarcodeDetector API support
      if ('BarcodeDetector' in window) {
        try {
          const supported = await BarcodeDetector.getSupportedFormats();
          this.detector = new BarcodeDetector({
            formats: supported.length > 0 ? supported : ['code_128', 'ean_13', 'ean_8', 'qr_code']
          });
        } catch (e) {
          console.warn("BarcodeDetector error:", e);
        }
      }

      this.loop();
      return true;
    } catch (err) {
      console.warn("Cámara no disponible o denegada:", err);
      return false;
    }
  }

  loop() {
    if (!this.active) return;
    if (this.detector) {
      this.detector.detect(this.video)
        .then(barcodes => {
          if (barcodes.length > 0) {
            const raw = barcodes[0].rawValue;
            if (raw && this.active) {
              this.stop();
              this.onDetected(raw);
              return;
            }
          }
        })
        .catch(err => console.debug(err));
    }
    this.scanInterval = setTimeout(() => this.loop(), 300);
  }

  stop() {
    this.active = false;
    if (this.scanInterval) clearTimeout(this.scanInterval);
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  }
}
