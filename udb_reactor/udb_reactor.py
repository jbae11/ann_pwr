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
        with open('log.txt', 'a') as f:
            f.write(string + '\n')

    def tock(self):
        self.write('what')

        # Example dummy code
        composition = {922350000: 5,
                       922380000: 95}
        material = ts.Material.create(self, 100, composition)

        self.inventory.push(material)
        self.write(str(self.inventory.quantity))


    #     time = self.context.time
    #     get rows that match with current time

    #     for information in rows:
    #         Create material given by recipe and quantity
    #         composition = {ZZAAA0000: massfrac,
    #                        ZZAAA0000: massfrac}
    #         recipe = self.context.get_recipe()
    #         material = ts.Material.create(self, quantity, recipe)

    #         Push material to out buffer
    #         self.out.push(material)


    def get_material_bids(self, requests):
        if self.outcommod not in requests:
            return
        reqs = requests[self.outcommod]
        bids = [reqs]
        ports = [{"bids": bids, "constraints": self.inventory.quantity}]
        return ports


    def get_material_trades(self, trades):
        responses = {}
        for trade in trades:
            print(trade)
            mat = self.inventory.pop()
            responses[trade] = mat
        return responses