"""Exercise the real form schema with HA's serializer dependency, without HA."""
import ast
import json
from pathlib import Path
import unittest

from voluptuous_serialize import convert

PATH = Path(__file__).resolve().parents[1] / "custom_components/crestron_gwexer/config_flow.py"
tree = ast.parse(PATH.read_text())
# Load the actual helper definitions without importing the HA application.
tree.body = [node for node in tree.body if not isinstance(node, ast.ClassDef)
             and not (isinstance(node, ast.ImportFrom) and node.module == "homeassistant")]
helpers = {}
exec(compile(tree, str(PATH), "exec"), helpers)


class FormSchemaTests(unittest.TestCase):
    def test_setup_and_options_forms_serialize(self):
        for settings in ({}, {"host": "192.0.2.1", "listen_port": 50000}):
            fields = convert(helpers["schema"](settings))
            json.dumps(fields)
            self.assertEqual(len(fields), 5)
            host = next(f for f in fields if f["name"] == "host")
            self.assertEqual(host["type"], "string")
            self.assertEqual(host["default"], settings.get("host", "172.26.219.35"))

    def test_invalid_ip_returns_field_error(self):
        data = {"host": "bad", "gateway_host": "999.2.3.4", "listen_host": "0.0.0.0"}
        self.assertEqual(helpers["validate_addresses"](data),
                         {"host": "invalid_ip", "gateway_host": "invalid_ip"})

    def test_valid_addresses_normalized(self):
        data = {"host": " 192.0.2.1 ", "gateway_host": "192.0.2.2", "listen_host": "0.0.0.0"}
        self.assertEqual(helpers["validate_addresses"](data), {})
        self.assertEqual(data["host"], "192.0.2.1")
