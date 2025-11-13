from enum import Enum


class StreamlitMessageStyle(str, Enum):
    """Supported Streamlit message container styles."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    WRITE = "write"


class ButtonType(str, Enum):
    """Button appearance variants."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
