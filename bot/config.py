"""
WhatsApp Bot Configuration & Defaults.
"""

import os
from core.config import (
    DEFAULT_MACHINE_HEADS,
    DEFAULT_BASE_COLORS,
    DEFAULT_LOTS_COUNT,
    DEFAULT_STITCH_RATE,
    DEFAULT_CONE_PRICE,
    DEFAULT_CONE_CAPACITY_METERS,
    DEFAULT_WASTAGE_PCT
)

# Default Machine Floor Settings for Bot
BOT_DEFAULT_HEADS = int(os.getenv("BOT_HEADS", DEFAULT_MACHINE_HEADS))
BOT_DEFAULT_SHADES = int(os.getenv("BOT_SHADES", DEFAULT_BASE_COLORS))
BOT_DEFAULT_LOTS = float(os.getenv("BOT_LOTS", DEFAULT_LOTS_COUNT))
BOT_DEFAULT_RATE = float(os.getenv("BOT_RATE", DEFAULT_STITCH_RATE))
BOT_DEFAULT_WASTE = float(os.getenv("BOT_WASTE", DEFAULT_WASTAGE_PCT))
BOT_DEFAULT_CONE_CAPACITY = float(os.getenv("BOT_CONE_CAPACITY", DEFAULT_CONE_CAPACITY_METERS))

# Meta WhatsApp Cloud API Credentials
META_WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "threadworks_verify_token")

# Webhook Server Settings
BOT_SERVER_HOST = os.getenv("BOT_HOST", "0.0.0.0")
BOT_SERVER_PORT = int(os.getenv("BOT_PORT", "8000"))

