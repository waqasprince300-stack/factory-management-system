"""
Threadworks WhatsApp Webhook Server.
Zero-dependency HTTP server that handles Meta WhatsApp Cloud API, Twilio,
and Local QR-bridge webhooks.
"""

import json
import base64
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import requests

from bot.config import (
    META_WHATSAPP_TOKEN,
    META_PHONE_NUMBER_ID,
    META_VERIFY_TOKEN,
    BOT_SERVER_HOST,
    BOT_SERVER_PORT
)
from bot.engine import process_whatsapp_pdf, process_whatsapp_text_command

# In-memory session store per phone number (e.g. { "+923001234567": {"heads": 28, "rate": 1.20} })
USER_SESSIONS = {}


def get_user_session(phone_number: str) -> dict:
    if phone_number not in USER_SESSIONS:
        USER_SESSIONS[phone_number] = {}
    return USER_SESSIONS[phone_number]


def send_meta_whatsapp_message(to_phone: str, text: str):
    """Sends a text message using Meta WhatsApp Cloud API."""
    if not META_WHATSAPP_TOKEN or not META_PHONE_NUMBER_ID:
        print(f"[Bot] Simulated WhatsApp to {to_phone}:\n{text}")
        return

    url = f"https://graph.facebook.com/v21.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[Bot] Meta text response: {r.status_code}")
    except Exception as e:
        print(f"[Bot] Error sending Meta WhatsApp message: {e}")


def send_meta_whatsapp_document(to_phone: str, pdf_bytes: bytes, filename: str, caption: str = ""):
    """Uploads and sends a PDF document via Meta WhatsApp Cloud API."""
    if not META_WHATSAPP_TOKEN or not META_PHONE_NUMBER_ID:
        print(f"[Bot] Simulated PDF Document send to {to_phone}: {filename} ({len(pdf_bytes)} bytes)")
        return

    # 1. Upload Media
    upload_url = f"https://graph.facebook.com/v21.0/{META_PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {META_WHATSAPP_TOKEN}"}
    files = {
        "file": (filename, pdf_bytes, "application/pdf"),
        "messaging_product": (None, "whatsapp")
    }
    try:
        up_resp = requests.post(upload_url, headers=headers, files=files, timeout=20)
        media_id = up_resp.json().get("id")
        if not media_id:
            print(f"[Bot] Failed to upload media: {up_resp.text}")
            return

        # 2. Send Document Message
        send_url = f"https://graph.facebook.com/v21.0/{META_PHONE_NUMBER_ID}/messages"
        doc_payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": filename,
                "caption": caption
            }
        }
        r = requests.post(send_url, json=doc_payload, headers={"Authorization": f"Bearer {META_WHATSAPP_TOKEN}", "Content-Type": "application/json"}, timeout=10)
        print(f"[Bot] Meta doc response: {r.status_code}")
    except Exception as e:
        print(f"[Bot] Error sending Meta WhatsApp document: {e}")


class WhatsAppWebhookHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        # Meta WhatsApp Webhook Verification
        if parsed.path == "/webhook":
            mode = qs.get("hub.mode", [""])[0]
            token = qs.get("hub.verify_token", [""])[0]
            challenge = qs.get("hub.challenge", [""])[0]

            if mode == "subscribe" and token == META_VERIFY_TOKEN:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(challenge.encode("utf-8"))
                print("[Bot] Webhook successfully verified with Meta!")
                return
            else:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Verification failed")
                return

        # Health check
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {
            "status": "online",
            "service": "Threadworks WhatsApp Bot Server",
            "version": "1.0.0"
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)

        parsed = urllib.parse.urlparse(self.path)

        # 1. Direct JSON Processing API (for Local QR Bridges / Baileys)
        if parsed.path == "/process":
            try:
                data = json.loads(post_body.decode("utf-8"))
                pdf_b64 = data.get("pdf_base64")
                fname = data.get("filename", "design.pdf")
                overrides = {
                    "heads": data.get("heads"),
                    "shades": data.get("shades"),
                    "lots": data.get("lots"),
                    "rate": data.get("rate")
                }
                pdf_bytes = base64.b64decode(pdf_b64)
                result = process_whatsapp_pdf(pdf_bytes, fname, overrides)

                resp_payload = {
                    "design_name": result["design_name"],
                    "text_reply": result["text_reply"],
                    "pdf_filename": result["pdf_filename"],
                    "pdf_base64": base64.b64encode(result["pdf_bytes"]).decode("utf-8"),
                    "metrics": result["metrics"]
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp_payload).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        # 2. Meta WhatsApp Cloud API Webhook
        if parsed.path == "/webhook":
            try:
                data = json.loads(post_body.decode("utf-8"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"EVENT_RECEIVED")

                # Parse Meta payload
                entries = data.get("entry", [])
                for entry in entries:
                    changes = entry.get("changes", [])
                    for change in changes:
                        val = change.get("value", {})
                        messages = val.get("messages", [])
                        for msg in messages:
                            from_phone = msg.get("from")
                            msg_type = msg.get("type")
                            session = get_user_session(from_phone)

                            # Handle Document (Wilcom PDF)
                            if msg_type == "document":
                                doc_info = msg.get("document", {})
                                doc_id = doc_info.get("id")
                                fname = doc_info.get("filename", "wilcom.pdf")

                                if doc_id and META_WHATSAPP_TOKEN:
                                    # Fetch download URL
                                    media_info_url = f"https://graph.facebook.com/v21.0/{doc_id}"
                                    hdrs = {"Authorization": f"Bearer {META_WHATSAPP_TOKEN}"}
                                    m_resp = requests.get(media_info_url, headers=hdrs).json()
                                    direct_url = m_resp.get("url")

                                    if direct_url:
                                        # Download PDF bytes
                                        pdf_data = requests.get(direct_url, headers=hdrs).content
                                        # Process through Threadworks engine
                                        bot_result = process_whatsapp_pdf(pdf_data, fname, session)

                                        # Reply 1: Text Summary
                                        send_meta_whatsapp_message(from_phone, bot_result["text_reply"])
                                        # Reply 2: PDF Job Card
                                        send_meta_whatsapp_document(
                                            to_phone=from_phone,
                                            pdf_bytes=bot_result["pdf_bytes"],
                                            filename=bot_result["pdf_filename"],
                                            caption=f"Job Card: {bot_result['design_name']}"
                                        )

                            # Handle Text Command
                            elif msg_type == "text":
                                body_text = msg.get("text", {}).get("body", "")
                                reply_text = process_whatsapp_text_command(body_text, session)
                                send_meta_whatsapp_message(from_phone, reply_text)
                return
            except Exception as e:
                print(f"[Bot] Webhook error: {e}")
                self.send_response(500)
                self.end_headers()
                return

        # Default 404
        self.send_response(404)
        self.end_headers()


def run_bot_server(host: str = BOT_SERVER_HOST, port: int = BOT_SERVER_PORT):
    server = ThreadingHTTPServer((host, port), WhatsAppWebhookHandler)
    print(f"🚀 Threadworks WhatsApp Bot Server running on http://{host}:{port}")
    print(f"   Webhook URL: http://{host}:{port}/webhook")
    print(f"   Process API: http://{host}:{port}/process")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping bot server...")
        server.server_close()


if __name__ == "__main__":
    run_bot_server()

