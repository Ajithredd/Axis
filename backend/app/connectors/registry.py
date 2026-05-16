"""
Connector Registry — auto-discovers and manages connector plugins.

Scans the app/connectors/ directory for any module that contains a
subclass of BaseConnector and registers it automatically.
"""

import importlib
import pkgutil
from pathlib import Path

from app.connectors.base import BaseConnector, ConnectorInfo


class ConnectorRegistry:
    """
    Registry that holds all available connectors.

    Usage:
        registry = ConnectorRegistry()
        registry.discover()  # auto-finds all connectors

        gitlab = registry.get("gitlab")
        events = await gitlab.sync_all(config, token)
    """

    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        """Manually register a connector instance."""
        info = connector.info()
        self._connectors[info.type] = connector
        print(f"  ✓ Registered connector: {info.display_name} ({info.type})")

    def get(self, connector_type: str) -> BaseConnector | None:
        """Get a connector by its type identifier."""
        return self._connectors.get(connector_type)

    def list_connectors(self) -> dict[str, ConnectorInfo]:
        """Return info about all registered connectors."""
        return {
            ctype: connector.info()
            for ctype, connector in self._connectors.items()
        }

    def discover(self) -> None:
        """
        Auto-discover connectors by scanning subdirectories.

        Looks for any package under app/connectors/ that has a
        connector.py file with a class that subclasses BaseConnector.

        Directory structure expected:
            app/connectors/
            ├── gitlab/
            │   ├── __init__.py
            │   └── connector.py  ← must contain a BaseConnector subclass
            ├── slack/             ← future
            │   ├── __init__.py
            │   └── connector.py
            └── confluence/        ← future
                ├── __init__.py
                └── connector.py
        """
        connectors_dir = Path(__file__).parent

        for item in connectors_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("_"):
                continue

            connector_module_path = item / "connector.py"
            if not connector_module_path.exists():
                continue

            try:
                module = importlib.import_module(
                    f"app.connectors.{item.name}.connector"
                )

                # Find the BaseConnector subclass in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseConnector)
                        and attr is not BaseConnector
                    ):
                        instance = attr()
                        self.register(instance)
                        break  # One connector per module

            except Exception as e:
                print(f"  ✗ Failed to load connector from {item.name}: {e}")


# Global singleton
connector_registry = ConnectorRegistry()
