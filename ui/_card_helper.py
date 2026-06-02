"""Shared _card() factory used across tabs and components."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from .tokens import CARD_MARGIN, ROW_SPACING


def _card(title: str):
    """Create a card widget with a header label. Returns (card, body_layout)."""
    card = QWidget()
    card.setProperty("card", True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(*CARD_MARGIN)
    layout.setSpacing(ROW_SPACING)
    header = QLabel(title)
    header.setProperty("header", True)
    layout.addWidget(header)
    return card, layout
