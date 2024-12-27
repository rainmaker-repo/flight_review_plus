"""
Tornado handler for hardware ID to serial number mappings
"""
from __future__ import print_function
import json
import sqlite3
import tornado.web

# this is needed for the following imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../plot_app'))
from config import get_db_filename
from .common import TornadoRequestHandlerBase, CustomHTTPError

class HWIDMappingsHandler(TornadoRequestHandlerBase):
    """ Get and update hardware ID to serial number mappings """
    
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        # Remove Allow-Credentials since we're using "*" for Allow-Origin

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def get(self, *args, **kwargs):
        try:
            con = sqlite3.connect(get_db_filename())
            cur = con.cursor()
            cur.execute('SELECT HardwareId, SerialNumber FROM HWIDMappings')
            mappings = cur.fetchall()
            cur.close()
            con.close()

            # Convert to dictionary format
            result = {hw_id: serial for hw_id, serial in mappings}
            
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(result))

        except Exception as e:
            self.set_status(500)
            self.write(json.dumps({'error': str(e)}))

    def post(self, *args, **kwargs):
        try:
            mappings = tornado.escape.json_decode(self.request.body)
            
            con = sqlite3.connect(get_db_filename())
            cur = con.cursor()
            
            cur.execute('DELETE FROM HWIDMappings')
            
            for hardware_id, serial_number in mappings.items():
                cur.execute('''INSERT INTO HWIDMappings 
                              (HardwareId, SerialNumber) VALUES (?, ?)''',
                           (hardware_id, serial_number))
            
            con.commit()
            cur.close()
            con.close()

            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps({'status': 'success'}))

        except Exception as e:
            self.set_status(500)
            self.write(json.dumps({'error': str(e)})) 