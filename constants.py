from enum import Enum


class ButtonType(str, Enum):
    """Button appearance variants."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
