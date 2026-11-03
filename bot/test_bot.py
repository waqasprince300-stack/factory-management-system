"""
Test and Verification Script for Threadworks WhatsApp Bot.
Simulates receiving a WhatsApp PDF and executing text commands.
"""

import os
import sys

# Ensure project root is in path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.engine import process_whatsapp_pdf, process_whatsapp_text_command


def run_tests():
    print("=" * 60)
    print("🧪 TESTING THREADWORKS WHATSAPP BOT ENGINE")
    print("=" * 60)

    # 1. Test Text Commands
    print("\n[1] Testing Text Commands:")
    session = {}
    r_help = process_whatsapp_text_command("help", session)
    print("  'help' response length:", len(r_help))

    r_heads = process_whatsapp_text_command("heads 28", session)
    print("  'heads 28' response:", r_heads)
    assert session.get("heads") == 28, "Heads setting failed!"

    r_rate = process_whatsapp_text_command("rate 1.25", session)
    print("  'rate 1.25' response:", r_rate)
    assert session.get("rate") == 1.25, "Rate setting failed!"

    r_status = process_whatsapp_text_command("status", session)
    print("  'status' response:\n" + r_status)

    # 2. Test Processing Actual PDF from Downloads
    test_pdf_path = r"c:\Users\Muhammad Waqas\Downloads\G1491 Lawan (2R).pdf"
    if not os.path.exists(test_pdf_path):
        print(f"⚠️ Test PDF not found at {test_pdf_path}")
        return

    print(f"\n[2] Testing PDF Processing with: {os.path.basename(test_pdf_path)}")
    with open(test_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = process_whatsapp_pdf(
        pdf_bytes=pdf_bytes,
        filename="G1491 Lawan (2R).pdf",
        overrides={"heads": 30, "shades": 6, "rate": 1.00, "lots": 1.0}
    )

    print("\n" + "=" * 60)
    print("📱 WHATSAPP MESSAGE OUTPUT FROM BOT:")
    print("=" * 60)
    print(result["text_reply"])
    print("=" * 60)

    print(f"\n[3] Job Card PDF generated: {result['pdf_filename']} ({len(result['pdf_bytes']):,} bytes)")
    assert len(result["pdf_bytes"]) > 1000, "PDF bytes too small!"
    assert "THREADWORKS" in result["text_reply"], "Header missing in reply!"
    assert "STORE REQUISITION" in result["text_reply"], "Store section missing!"

    print("\n✅ ALL BOT TESTS PASSED 100% SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
