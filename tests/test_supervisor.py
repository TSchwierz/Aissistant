"""Supervisor launches one process per service."""

import unittest

from server.supervisor import child_commands


class SupervisorTests(unittest.TestCase):
    def test_child_commands_cover_each_service(self):
        commands = child_commands("python")
        self.assertEqual([name for name, _cmd in commands], ["api", "climate", "scale", "news"])
        by_name = dict(commands)
        self.assertEqual(by_name["api"], ["python", "-m", "server"])
        self.assertEqual(by_name["climate"][-1], "climate")
        self.assertEqual(by_name["scale"][-1], "scale")
        self.assertEqual(by_name["news"][-1], "news")
