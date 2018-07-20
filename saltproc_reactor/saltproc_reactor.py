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

    waste_tank = ts.ResBufMaterialInv()
    fill_tank = ts.ResBufMaterialInv()
    fissile_tank = ts.ResBufMaterialInv()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def enter_notify(self):
        super().enter_notify()
        self.f = h5py.File(self.db_path, 'r')
        # subject to change
        self.waste_db = self.f['waste tank composition']
        self.fissile_db = self.f['fissile tank composition']
        self.isos = self.f['iso names']
        self.num_isotopes = len(self.isos)
        self.prev_indx = 0
        # default in saltproc is 3 days
        # probably should have this in the database as well
        ################################ SET AS 60 days
        self.saltproc_timestep = 3 * 24 * 3600 * 20

    def tick(self):
        print('TIME IS %i \n' %self.context.time)
        self.indx = self.context.dt * (self.context.time - self.enter_time)
        self.indx = int(self.indx / self.saltproc_timestep)
        waste_dump = np.zeros(self.num_isotopes)
        waste_dict = {}
        for t in np.arange(self.prev_indx, self.indx):
            print(t)
            waste_dump += self.waste_db[t, :]
        for i, val in enumerate(waste_dump):
            iso = self.isos[i].decode('utf8')
            waste_dict[iso] = val
        print(waste_dict)
        self.prev_indx = self.indx
        total_mass = 1
        material = ts.Material.create(self, total_mass, waste_dict)
        self.waste_tank.push(material)
        print('tick end')
