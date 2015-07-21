import argparse
import unittest

import stun
from stun import cli


class TestCLI(unittest.TestCase):
    """Test the CLI API."""

    @classmethod
    def setUpClass(cls):
        cls.source_ip = '123.45.67.89'
        cls.source_port = 24816
        cls.stun_port = 13579
        cls.stun_host = 'stun.stub.org'

    def test_cli_parser_default(self):
        parser = cli.make_argument_parser()
        options = parser.parse_args([])

        self.assertEqual(options.source_ip, stun.DEFAULTS['source_ip'])
        self.assertEqual(options.source_port, stun.DEFAULTS['source_port'])
        self.assertEqual(options.stun_port, stun.DEFAULTS['stun_port'])
        self.assertIsNone(options.stun_host)

    def test_cli_parser_user_long_form(self):
        parser = cli.make_argument_parser()
        options = parser.parse_args([
            '--source-port', str(self.source_port),
            '--source-ip', self.source_ip,
            '--stun-port', str(self.stun_port),
            '--stun-host', self.stun_host,
            '--debug'
        ])


        self.assertTrue(options.debug)
        self.assertEqual(options.source_ip, self.source_ip)
        self.assertEqual(options.source_port, self.source_port)
        self.assertEqual(options.stun_host, self.stun_host)
        self.assertEqual(options.stun_port, self.stun_port)

    def test_cli_parser_user_short_form(self):
        parser = cli.make_argument_parser()
        options = parser.parse_args([
            '-p', str(self.source_port),
            '-i', self.source_ip,
            '-P', str(self.stun_port),
            '-H', self.stun_host,
            '-d'
        ])

        self.assertTrue(options.debug)
        self.assertEqual(options.source_ip, self.source_ip)
        self.assertEqual(options.source_port, self.source_port)
        self.assertEqual(options.stun_host, self.stun_host)
        self.assertEqual(options.stun_port, self.stun_port)

if __name__ == '__main__':
    unittest.main()
