"""
TrustGuard ML Package

Provides the clean integration boundary for the Backend Policy Engine.
"""

from .predict import predict_risk

__all__ = ["predict_risk"]
