import random
import copy
import math
from collections import defaultdict
import numpy as np
import scipy as sp
import sqlite3 as lite

from cyclus.agents import Institution, Agent, Facility
from cyclus import lib
import cyclus.typesystem as ts


class udb_reactor(Facility):

    reactor_id = ts.Int(
        doc="This variable lists the reactor id of the reactors in the database ",
        tooltip="Reactor Id in database",
        uilabel="Reactor ID"
    )

    outcommod = ts.String(
        doc="The commodity this institution will output",
        tooltip="Output commodity",
        uilabel="Output Commodity"
    )

    inventory = ts.ResBufMaterialInv()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, string):
        # for debugging purposes.
        with open('log.txt', 'a') as f:
            f.write(string + '\n')


    def tock(self):
        self.write('Tock')
        # Example dummy material
        # this should be replaced with material
        # from the UDB database
        composition = {922350000: 5,
                       922380000: 95}
        material = ts.Material.create(self, 100, composition)

        # stores the planned spent fuel into inventory buffer
        # for it to be offered to the market
        self.inventory.push(material)
        self.write(str(self.inventory.quantity))


    def get_material_bids(self, requests):
        """ Gets material bids that want its `outcommod' an
            returns bid portfolio
        """
        if self.outcommod not in requests:
            return
        reqs = requests[self.outcommod]
        bids = []
        for req in reqs:
            qty = min(req.target.quantity, self.inventory.quantity)
            # returns if the inventory is empty
            if self.inventory.empty():
                return
            # get the composition of the material next in line
            next_in_line = self.inventory.peek()
            mat = ts.Material.create_untracked(qty, next_in_line.comp())
            bids.append({'request': req, 'offer': mat})
        port = {"bids": bids}
        return port


    def get_material_trades(self, trades):
        responses = {}
        for trade in trades:
            print(trade)
            mat = self.inventory.pop()
            responses[trade] = mat
        return responses