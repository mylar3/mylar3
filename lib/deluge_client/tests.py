import os

from unittest import TestCase

from .client import DelugeRPCClient

class TestDelugeClient(TestCase):
    def setUp(self):
        auth_path = os.path.expanduser("~/.config/deluge/auth")
        
        with open(auth_path, 'rb') as f:
            filedata = f.read().decode("utf-8").split('\n')[0].split(':')
        
        self.username, self.password = filedata[:2]
        self.ip = '127.0.0.1'
        self.port = 58846
        self.client = DelugeRPCClient(self.ip, self.port, self.username, self.password)
    
    def tearDown(self):
        try:
            self.client.disconnect()
        except:
            pass
    
    def test_connect(self):
        self.client.connect()
    
    def test_call_method(self):
        self.client.connect()
        self.assertIsInstance(self.client.call('core.get_free_space'), int)
    
    def test_call_method_arguments(self):
        self.client.connect()
        self.assertIsInstance(self.client.call('core.get_free_space', '/'), int)
    
    def test_call_method_exception(self):
        self.client.connect()
        try:
            self.client.call('core.get_free_space', '1', '2')
        except Exception as e:
            self.assertEqual('deluge_client.client', e.__module__)
