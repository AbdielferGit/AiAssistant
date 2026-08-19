# Roadmap: de asistente personal a producto

## Dónde alojar el servidor (para no depender de tu Mac)

Recomendación por fases — no saltes directo a lo más complejo, cada fase te
sirve de validación antes de gastar en la siguiente:

### Fase 1 — MVP personal (tú como único usuario)
**VPS pequeño, barato, en una región cercana a los servidores de Anthropic (US):**
- [Hetzner Cloud](https://www.hetzner.com/cloud/) CX22 (~€4-5/mes) — mejor precio/rendimiento.
- [DigitalOcean](https://www.digitalocean.com/) Droplet básico ($6/mes) — documentación más amigable si es tu primer VPS.

En ese VPS corres `docker-compose.yml` (orchestrator + whatsapp-bridge) las
24h. Ventaja clave: el puente de WhatsApp (Baileys) necesita mantener una
sesión activa constantemente — si vive en tu Mac y la cierras/duerme, se cae
la sesión. Un VPS soluciona justo eso.

Para conectar el VPS con tu celular y tu Mac de forma privada y segura, sin
abrir puertos públicos: instala **[Tailscale](https://tailscale.com/)** (gratis
hasta 100 dispositivos) en el VPS, tu Mac y tu Android. Crea una red privada
tipo VPN entre los tres — el `bridge/server.py` solo escucha dentro de esa
red, nunca expuesto a internet abierto.

### Fase 2 — Beta cerrada (tú + un puñado de clientes de prueba)
- Mismo VPS, pero cada cliente = su propia sesión de WhatsApp/Messenger y su
  propio contenedor aislado (un número de WhatsApp = una sesión de Baileys;
  no se pueden compartir).
- Migra la "base de datos en Drive" a **Postgres gestionado** (Neon, Supabase,
  o RDS de AWS) con la extensión `pgvector` para la memoria de estilo.
  Drive deja de ser la base de datos; pasa a ser solo **respaldo/export** por
  cliente, que es para lo que sirve bien.
- Aísla credenciales por cliente con un vault (Doppler o AWS Secrets Manager),
  nunca en archivos `.env` sueltos por servidor.

### Fase 3 — Producto SaaS multi-cliente
- Contenerización orquestada: **Fly.io** o **Railway** si quieres seguir con
  poca operación (recomendado para empezar a cobrar rápido); **AWS ECS/Fargate**
  o **GCP Cloud Run** cuando el volumen justifique más control.
- Un contenedor "orchestrator" + un contenedor "whatsapp-bridge" **por
  cliente**, no compartidos — así un baneo o caída afecta a un solo cliente.
- Facturación: Stripe Billing (suscripción mensual).
- **Decisión de fondo antes de vender**: evalúa migrar WhatsApp/Messenger a
  las APIs oficiales (WhatsApp Business API vía Twilio/360dialog, Messenger
  Platform). Usar librerías no oficiales para *muchas cuentas de clientes*
  multiplica el riesgo de baneos y te expone legalmente de una forma que no
  aplica cuando es solo tu cuenta personal. No es bloqueante para probar el
  producto con pocos clientes que acepten el riesgo, pero sí lo es para
  escalar en serio.

## Resumen de la respuesta a tu pregunta

> "¿Dónde puedo crear un servidor para no depender de mi Mac?"

Empieza con un **VPS de Hetzner o DigitalOcean** (unos $5-6/mes), conectado a
tu Mac y tu Android vía **Tailscale**. Es suficiente para el MVP personal y
para las primeras pruebas con clientes. Cuando el número de clientes crezca,
migras la orquestación a Fly.io/Railway (fácil) o AWS/GCP (más control) y la
base de datos de Drive a Postgres gestionado.

## Métricas a validar antes de invertir en escalar
- ¿El estilo de escritura generado realmente pasa por "escrito por ti" para
  quien lo lee? (pídele feedback a 2-3 personas que te conozcan bien).
- ¿Cuántas confirmaciones manuales por día tolera un usuario antes de sentir
  que "no ahorra tiempo"?
- ¿Qué tan seguido se cae la sesión de WhatsApp no oficial? (esto define si
  el modelo de negocio aguanta con la vía no oficial o si hay que saltar a
  la oficial antes de lo planeado).
