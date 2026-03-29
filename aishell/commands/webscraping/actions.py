"""
Action handlers for web scraping navigation.

This module defines the action types that can be used to interact with web pages
using Playwright. Actions are the building blocks of navigation sequences.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class ActionType(Enum):
    """Supported action types for web navigation."""
    CLICK = "click"
    HOVER = "hover"
    WAIT = "wait"
    EXTRACT = "extract"
    SCROLL = "scroll"
    TYPE = "type"
    SELECT = "select"
    SCREENSHOT = "screenshot"
    JAVASCRIPT = "js"
    NAVIGATE = "navigate"


@dataclass
class Action:
    """Base class for navigation actions."""
    description: Optional[str] = field(default=None, kw_only=True)
    type: ActionType = field(default=None, init=False)  # Set by child classes

    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary representation."""
        return {
            "type": self.type.value,
            "description": self.description
        }


@dataclass
class ClickAction(Action):
    """Click on an element."""
    selector: str
    button: str = "left"  # left, right, middle
    click_count: int = 1
    timeout: int = 30000  # milliseconds

    def __post_init__(self):
        self.type = ActionType.CLICK

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "selector": self.selector,
            "button": self.button,
            "click_count": self.click_count,
            "timeout": self.timeout
        })
        return result


@dataclass
class HoverAction(Action):
    """Hover over an element."""
    selector: str
    timeout: int = 30000

    def __post_init__(self):
        self.type = ActionType.HOVER

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "selector": self.selector,
            "timeout": self.timeout
        })
        return result


@dataclass
class WaitAction(Action):
    """Wait for a condition."""
    selector: Optional[str] = None  # Wait for element
    duration: Optional[int] = None  # Wait for duration (milliseconds)
    state: str = "visible"  # visible, hidden, attached, detached
    timeout: int = 30000

    def __post_init__(self):
        self.type = ActionType.WAIT
        if self.selector is None and self.duration is None:
            raise ValueError("Either selector or duration must be specified")

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "selector": self.selector,
            "duration": self.duration,
            "state": self.state,
            "timeout": self.timeout
        })
        return result


@dataclass
class ExtractAction(Action):
    """Extract data from the page."""
    selectors: Dict[str, str] = field(default_factory=dict)  # field_name: css_selector
    extract_type: str = "text"  # text, html, attribute
    attribute: Optional[str] = None  # For extract_type="attribute"
    multiple: bool = False  # Extract all matching elements

    def __post_init__(self):
        self.type = ActionType.EXTRACT

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "selectors": self.selectors,
            "extract_type": self.extract_type,
            "attribute": self.attribute,
            "multiple": self.multiple
        })
        return result


@dataclass
class ScrollAction(Action):
    """Scroll the page."""
    direction: str = "down"  # down, up, left, right
    amount: Optional[int] = None  # Pixels (None = full page)
    selector: Optional[str] = None  # Scroll specific element

    def __post_init__(self):
        self.type = ActionType.SCROLL

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "direction": self.direction,
            "amount": self.amount,
            "selector": self.selector
        })
        return result


@dataclass
class TypeAction(Action):
    """Type text into an input field."""
    selector: str = ""
    text: str = ""
    delay: int = 0  # Milliseconds between keystrokes
    clear_first: bool = True

    def __post_init__(self):
        self.type = ActionType.TYPE
        if not self.selector or not self.text:
            raise ValueError("Both selector and text must be specified")

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "selector": self.selector,
            "text": self.text,
            "delay": self.delay,
            "clear_first": self.clear_first
        })
        return result


@dataclass
class SelectAction(Action):
    """Select option from dropdown."""
    selector: str = ""
    value: Optional[str] = None
    label: Optional[str] = None
    index: Optional[int] = None

    def __post_init__(self):
        self.type = ActionType.SELECT
        if not self.selector:
            raise ValueError("Selector must be specified")
        if not any([self.value, self.label, self.index is not None]):
            raise ValueError("Either value, label, or index must be specified")

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "selector": self.selector,
            "value": self.value,
            "label": self.label,
            "index": self.index
        })
        return result


@dataclass
class ScreenshotAction(Action):
    """Take a screenshot."""
    path: str = ""
    full_page: bool = False
    selector: Optional[str] = None  # Screenshot specific element

    def __post_init__(self):
        self.type = ActionType.SCREENSHOT
        if not self.path:
            raise ValueError("Path must be specified")

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "path": self.path,
            "full_page": self.full_page,
            "selector": self.selector
        })
        return result


@dataclass
class JavaScriptAction(Action):
    """Execute JavaScript code."""
    code: str = ""

    def __post_init__(self):
        self.type = ActionType.JAVASCRIPT
        if not self.code:
            raise ValueError("Code must be specified")

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "code": self.code
        })
        return result


@dataclass
class NavigateAction(Action):
    """Navigate to a URL."""
    url: str = ""
    wait_until: str = "networkidle"  # load, domcontentloaded, networkidle

    def __post_init__(self):
        self.type = ActionType.NAVIGATE
        if not self.url:
            raise ValueError("URL must be specified")

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "url": self.url,
            "wait_until": self.wait_until
        })
        return result


# Action factory function
def create_action(action_dict: Dict[str, Any]) -> Action:
    """
    Create an Action instance from a dictionary.

    Args:
        action_dict: Dictionary with action type and parameters

    Returns:
        Action instance

    Raises:
        ValueError: If action type is unknown
    """
    action_type = action_dict.get("type", "").lower()

    action_map = {
        "click": ClickAction,
        "hover": HoverAction,
        "wait": WaitAction,
        "extract": ExtractAction,
        "scroll": ScrollAction,
        "type": TypeAction,
        "select": SelectAction,
        "screenshot": ScreenshotAction,
        "js": JavaScriptAction,
        "javascript": JavaScriptAction,
        "navigate": NavigateAction,
    }

    action_class = action_map.get(action_type)
    if not action_class:
        raise ValueError(f"Unknown action type: {action_type}")

    # Remove 'type' from dict as it's set in __post_init__
    params = {k: v for k, v in action_dict.items() if k != "type"}

    return action_class(**params)
