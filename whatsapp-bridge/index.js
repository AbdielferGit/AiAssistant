// Puente HTTP <-> WhatsApp Web (Baileys). Ver docs/ARCHITECTURE.md sobre el
// riesgo de usar un protocolo no oficial antes de activarlo en producción.
//
// Lista blanca de contactos: este archivo es una SEGUNDA capa de defensa
// además de la que ya aplica orchestrator/contacts.py. Lee el mismo
// config/contacts.yaml y:
//   - rechaza /send hacia números que no estén en la lista (activo: true)
//   - descarta mensajes entrantes de números fuera de la lista ANTES de
//     reenviarlos al orchestrator (nunca se procesan, ni se registran)
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import express from "express";
import qrcode from "qrcode-terminal";
import yaml from "js-yaml";
import baileysPkg from "@whiskeysockets/baileys";

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = baileysPkg;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 4001;
const TOKEN = process.env.WHATSAPP_BRIDGE_TOKEN || "";
const PHONE_BRIDGE_TOKEN = process.env.PHONE_BRIDGE_TOKEN || "";
const ORCHESTRATOR_INBOUND_URL =
  process.env.ORCHESTRATOR_INBOUND_URL || "http://orchestrator:8090/inbound/whatsapp";
const AUTH_DIR = "./auth_session"; // en .gitignore — nunca lo subas a git
const CONTACTS_PATH = path.join(__dirname, "..", "config", "contacts.yaml");

let sock;
let conectado = false;

function normalizarNumero(numero) {
  return (numero || "").replace(/[^\d+]/g, "");
}

function cargarNumerosAutorizados() {
  if (!fs.existsSync(CONTACTS_PATH)) {
    console.warn(
      `No existe ${CONTACTS_PATH} — copia config/contacts.yaml.example y ` +
        `agrega tus contactos. Mientras tanto, NINGÚN número está autorizado.`
    );
    return new Set();
  }
  const datos = yaml.load(fs.readFileSync(CONTACTS_PATH, "utf8")) || {};
  const numeros = new Set();
  for (const c of datos.contactos || []) {
    if (c.activo && c.canales && c.canales.whatsapp) {
      numeros.add(normalizarNumero(c.canales.whatsapp));
    }
  }
  return numeros;
}

function requireAuth(req, res, next) {
  if (!TOKEN || req.headers.authorization !== `Bearer ${TOKEN}`) {
    return res.status(401).json({ error: "token inválido" });
  }
  next();
}

async function iniciarWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  sock = makeWASocket({ auth: state, printQRInTerminal: false });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      console.log("Escanea este QR desde WhatsApp > Dispositivos vinculados:");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "open") {
      conectado = true;
      console.log("WhatsApp conectado.");
    }
    if (connection === "close") {
      conectado = false;
      const debeReconectar =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      console.log("Conexión cerrada.", debeReconectar ? "Reintentando..." : "Sesión cerrada, re-escanea el QR.");
      if (debeReconectar) iniciarWhatsApp();
    }
  });

  // Mensajes entrantes: filtra por lista blanca ANTES de reenviar nada.
  sock.ev.on("messages.upsert", async ({ messages }) => {
    const autorizados = cargarNumerosAutorizados();
    for (const msg of messages) {
      if (msg.key.fromMe || !msg.message) continue;
      const remitenteJid = msg.key.remoteJid || "";
      const remitenteNumero = normalizarNumero(remitenteJid.split("@")[0]);
      const texto =
        msg.message.conversation || msg.message.extendedTextMessage?.text || "";

      if (!autorizados.has(remitenteNumero)) {
        console.log(`Mensaje entrante ignorado (fuera de lista blanca): ${remitenteNumero}`);
        continue; // nunca se reenvía, nunca se procesa, nunca se guarda
      }

      try {
        await fetch(ORCHESTRATOR_INBOUND_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${PHONE_BRIDGE_TOKEN}`,
          },
          body: JSON.stringify({ remitente: remitenteNumero, texto }),
        });
      } catch (err) {
        console.error("No se pudo reenviar mensaje entrante al orchestrator:", err);
      }
    }
  });
}

const app = express();
app.use(express.json());

app.get("/status", requireAuth, (_req, res) => {
  res.json({ conectado });
});

app.post("/send", requireAuth, async (req, res) => {
  const { numero, texto } = req.body || {};
  if (!numero || !texto) {
    return res.status(400).json({ error: "faltan 'numero' o 'texto'" });
  }
  const autorizados = cargarNumerosAutorizados();
  if (!autorizados.has(normalizarNumero(numero))) {
    return res.status(403).json({ error: "número fuera de la lista blanca de contactos" });
  }
  if (!conectado) {
    return res.status(503).json({ error: "WhatsApp no está conectado todavía" });
  }
  try {
    const jid = normalizarNumero(numero).replace("+", "") + "@s.whatsapp.net";
    await sock.sendMessage(jid, { text: texto });
    res.json({ status: "enviado", numero });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.listen(PORT, () => console.log(`whatsapp-bridge escuchando en :${PORT}`));
iniciarWhatsApp();
