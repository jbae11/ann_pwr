import numpy as np
import sqlite3 as lite

from cyclus.agents import Institution, Agent
from cyclus import lib
import cyclus.typstream as ts

class udb_reactor_manager(Institution):

    db_path = ts.String(
        doc="Path to the sqlite file of udb data",
        tooltip="Absolute path to the udb sqlite data"
    )

    def __init__(self):
        super().__init__()

    def enter_notify(self):
        super().enter_notify()
        conn = lite.connect(db_path)
        cur = conn.cursor()
        reactor_ids = cur.execute('SELECT distinct(reactor_id) FROM '
                                  'discharge').fetchall()
        for reactor in reactor_ids:
            self.context.schedule_build(self, reactor)