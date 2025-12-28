"""
Text widget for displaying content.
"""
from dash import html

from .base import BaseWidget, WidgetConfig


class TextWidget(BaseWidget):
    """Simple text display widget."""

    def __init__(self, config: WidgetConfig, content: str = ""):
        super().__init__(config)
        self.content = content

    def render(self) -> html.Div:
        """Render text widget."""
        return html.Div(
            [
                html.Div(self.config.title, className="tile-header"),
                html.Div(
                    html.Pre(self.content, style={"whiteSpace": "pre-wrap"}),
                    className="tile-body",
                ),
            ],
            className="tile",
            id=self.config.id,
        )

    def get_client_config(self) -> dict:
        """Get configuration for JavaScript."""
        return {
            "widgetType": "text",
            "id": self.config.id,
            "content": self.content,
            "layout": self.config.to_gridstack_dict(),
        }
