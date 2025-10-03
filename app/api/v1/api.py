#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Router modülü
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, services, bot, messages, analytics

api_router = APIRouter()

# Auth endpoint'leri
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

# Services endpoint'leri 
api_router.include_router(
    services.router,
    prefix="/services",
    tags=["services"]
)

# Bot endpoint'leri
api_router.include_router(
    bot.router,
    prefix="/bot",
    tags=["bot"]
)

# Messages endpoint'leri
api_router.include_router(
    messages.router,
    prefix="/messages",
    tags=["messages"]
)

# Analytics endpoint'leri
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)