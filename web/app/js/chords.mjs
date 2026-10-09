// Formato REALE del firmware (letto da ~/Documents/Arduino/provaBCI/provaBCI.ino, Upside Down Labs "Chords"):
// pacchetti BINARI a 250 Hz, 115200 baud, solo dopo il comando di testo "START\n".
//   byte 0: 0xC7   byte 1: 0x7C   byte 2: contatore (0..255, poi riparte)
//   poi N canali x 2 byte (alto, basso) = valore ADC a 10 bit (UNO: N = 6, A0..A5)
//   ultimo byte: 0x01
// Lunghezza = 2*N + 4.  Comandi (righe di testo): WHORU -> nome scheda, START, STOP, STATUS.
// Vedi anche web/05-talpa-w0.md, sez. 2c. Questo e' un "formato verificato sul codice del firmware", non su dati.

export const SYNC1 = 0xC7, SYNC2 = 0x7C, END_BYTE = 0x01;
export const BOARDS = { 'UNO-R3': 6, 'GENUINO-UNO': 6, 'UNO-CLONE': 6, 'NANO-CLASSIC': 8, 'NANO-CLONE': 8, 'MEGA-2560-R3': 16, 'MEGA-2560-CLONE': 16 };
export const packetLength = (channels) => channels * 2 + 4;

export class ChordsParser {
  constructor(channels = 6) {
    this.channels = channels; this.rest = new Uint8Array(0);
    this.packets = 0; this.lost = 0; this.skipped = 0; this.prev = null; this.text = '';
  }
  // Consegna byte; restituisce i pacchetti completi: [{counter, values: Uint16Array(canali)}]
  push(bytes) {
    const n = packetLength(this.channels);
    const buf = new Uint8Array(this.rest.length + bytes.length); buf.set(this.rest); buf.set(bytes, this.rest.length);
    const out = []; let i = 0;
    while (i < buf.length) {
      if (buf[i] === SYNC1 && (i + 1 >= buf.length || buf[i + 1] === SYNC2)) {
        if (i + n > buf.length) break;                           // pacchetto non ancora completo
        if (buf[i + n - 1] === END_BYTE) {
          const counter = buf[i + 2], values = new Uint16Array(this.channels);
          for (let c = 0; c < this.channels; c++) values[c] = (buf[i + 3 + 2 * c] << 8) | buf[i + 4 + 2 * c];
          if (this.prev !== null) this.lost += (counter - this.prev - 1) & 255;
          this.prev = counter; this.packets++; out.push({ counter, values }); i += n; continue;
        }
      }
      const b = buf[i];                                          // non e' l'inizio di un pacchetto: scarto (testo?)
      if (b >= 32 && b < 127) { if (this.text.length < 400) this.text += String.fromCharCode(b); }
      else if (b === 10 && this.text.length < 400) this.text += '\n';
      this.skipped++; i++;
    }
    this.rest = buf.slice(i);
    return out;
  }
}
