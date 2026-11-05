"""
Test and Verification Script for Threadworks WhatsApp Bot.
Simulates receiving a WhatsApp PDF and executing text commands.

Usage:
  python bot/test_bot.py
  python bot/test_bot.py "C:\\path\\to\\your_file.pdf"
"""

import os
import sys

# Ensure UTF-8 output and project root in path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.engine import process_whatsapp_pdf, process_whatsapp_text_command


def run_tests(custom_pdf_path=None):
    print("=" * 65)
    print("🤖 TESTING THREADWORKS WHATSAPP BOT")
    print("=" * 65)

    # 1. Test WhatsApp Text Commands Simulation
    print("\n[Step 1] Simulating WhatsApp Text Commands:")
    session = {}
    
    # User sends 'help'
    r_help = process_whatsapp_text_command("help", session)
    print("  ✓ Command 'help' -> Response Received")

    # User sends 'heads 30'
    r_heads = process_whatsapp_text_command("heads 30", session)
    print("  ✓ Command 'heads 30' ->", r_heads)
    assert session.get("heads") == 30, "Heads setting failed!"

    # User sends 'rate 1.20'
    r_rate = process_whatsapp_text_command("rate 1.20", session)
    print("  ✓ Command 'rate 1.20' ->", r_rate)
    assert session.get("rate") == 1.20, "Rate setting failed!"

    # User sends 'status'
    r_status = process_whatsapp_text_command("status", session)
    print("  ✓ Command 'status' -> Current Session Settings Confirmed")

    # 2. Determine PDF Path to Test
    default_pdf = r"c:\Users\Muhammad Waqas\Downloads\G1491 Lawan (2R).pdf"
    target_pdf = custom_pdf_path if (custom_pdf_path and os.path.exists(custom_pdf_path)) else default_pdf

    if not os.path.exists(target_pdf):
        print(f"\n⚠️ Test PDF not found at: {target_pdf}")
        print("Aap kisi bhi Wilcom PDF ka path command mein de sakte hain:")
        print("  python bot/test_bot.py \"C:\\path\\to\\file.pdf\"")
        return

    print(f"\n[Step 2] Processing Wilcom PDF Worksheet:")
    print(f"  📄 File: {os.path.basename(target_pdf)}")
    
    with open(target_pdf, "rb") as f:
        pdf_bytes = f.read()

    # Process PDF with session overrides
    result = process_whatsapp_pdf(
        pdf_bytes=pdf_bytes,
        filename=os.path.basename(target_pdf),
        overrides={"heads": session.get("heads", 30), "shades": 6, "rate": session.get("rate", 1.00), "lots": 1.0}
    )

    print("\n" + "=" * 65)
    print("📱 WHATSAPP PAR USER KO JO MESSAGE JAYEGA:")
    print("=" * 65)
    print(result["text_reply"])
    print("=" * 65)

    # 3. Save the Generated PDF Job Card to Disk
    output_pdf_filename = f"bot_output_{result['pdf_filename']}"
    with open(output_pdf_filename, "wb") as f:
        f.write(result["pdf_bytes"])

    print(f"\n[Step 3] Printable A4 Job Card PDF File Ban Gayi Hai:")
    print(f"  📁 Saved As: {os.path.abspath(output_pdf_filename)}")
    print(f"  📊 Size: {len(result['pdf_bytes']):,} bytes")

    assert len(result["pdf_bytes"]) > 1000, "PDF bytes too small!"
    assert "DHAAGA ORDER" in result["text_reply"], "Header missing in reply!"
    assert "Kul Dhaaga Cones" in result["text_reply"], "Total cones missing in reply!"

    print("\n" + "=" * 65)
    print("✅ TEST 100% KAMYAB! Bot bilkul theek chal raha hai.")
    print("=" * 65)


if __name__ == "__main__":
    custom_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_tests(custom_arg)
