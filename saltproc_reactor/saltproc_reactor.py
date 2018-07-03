import random
import copy
import math
from collections import defaultdict
import numpy as np
import scipy as sp
import h5py

from cyclus.agents import Institution, Agent, Facility
from cyclus import lib
import cyclus.typesystem as ts


class saltproc_reactor(Facility):
    init_fuel_commod = ts.String(
        doc="The commodity name for initial loading fuel",
        tooltip="Init Fuel",
        uilabel="Init Fuel"
    )

    core_size = ts.Float(
        doc="Mass of core in reactor",
        tooltip="Core Size",
        uilabel="Core Size"
    )

    fill_commod = ts.String(
        doc="The commodity this facility will take in for fertile materials ",
        tooltip="Fill Commodity",
        uilabel="Fill Commodity"
    )

    fissile_out_commod = ts.String(
        doc="The fissile commodity this facility will output",
        tooltip="Fissile commodity",
        uilabel="Fissile Commodity"
    )

    waste_commod = ts.String(
        doc="The waste commodity this facility will output",
        tooltip="Waste commodity",
        uilabel="Waste Commodity"
    )

    db_path = ts.String(
        doc="Path to the hdf5 file",
        tooltip="Absolute path to the hdf5 file"
    )


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, string):
        # for debugging purposes.
        with open('log.txt', 'a+') as f:
            f.write(string + '\n')

    def enter_notify(self):
        super().enter_notify()
        self.f = h5py.File(self.db_path, 'r')
        dt = self.context.dt
        # default in saltproc is 3 days
        # probably should have this in the database as well
        saltproc_timestep = 3 * 24 * 3600
        

    def tick(self):
        z = 2

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
            mat_list = self.inventory.pop_n(self.inventory.count)
            # absorb all materials
            # best way is to do it separately, but idk how to do it :(
            for mat in mat_list[1:]:
                mat_list[0].absorb(mat)
            responses[trade] = mat_list[0]
        return responses