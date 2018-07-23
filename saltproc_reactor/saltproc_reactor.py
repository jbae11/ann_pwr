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

    fill_recipe = ts.String(
        doc="The recipe this facility will take in for fertile materials ",
        tooltip="Fill Recipe",
        uilabel="Fill Recipe"
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
        self.driver_refill = self.f['driver refill tank composition']
        self.blanket_refill = self.f['blanket refill tank composition']
        self.isos = self.f['iso names']
        self.num_isotopes = len(self.isos)
        self.prev_indx = 0
        # default in saltproc is 3 days
        # probably should have this in the database as well
        ################################ SET AS 30 days
        self.saltproc_timestep = 3 * 24 * 3600 * 10
        self.driver_mass = 1
        self.blanket_mass = 1

    def tick(self):
        print('TIME IS %i' %self.context.time)
        self.indx = self.context.dt * (self.context.time - self.enter_time)
        self.indx = int(self.indx / self.saltproc_timestep)
        self.indx = min(self.indx, len(self.waste_db[:, 0])) + 1
        print('INDX IS: %i' %self.indx)
        # push waste from db to waste_tank
        self.get_waste()
        # push fissile from db to fissile_tank
        self.get_fissile()

        self.get_fill_demand()
        self.prev_indx = self.indx
        
    def tock(self):
        print('TOCK\n')

    def get_waste(self):
        waste_dump = np.zeros(self.num_isotopes)
        waste_dict = {}
        # lump all the waste generated in this timestep
        # into one waste dump
        for t in np.arange(self.prev_indx, self.indx):
            waste_dump += self.waste_db[t, :]
        # convert this into a dictionary
        for i, val in enumerate(waste_dump):
            if val != 0:
                iso = self.isos[i].decode('utf8')
                waste_dict[iso] = val
        if bool(waste_dict):
            waste_mass = self.driver_mass * sum(waste_dict.values())
            material = ts.Material.create(self, waste_mass, waste_dict)
            self.waste_tank.push(material)
            print('PUSHED %f kg of WASTE INTO WASTE TANK' %waste_mass)

    def get_fissile(self):
        fissile_dump = np.zeros(self.num_isotopes)
        fissile_dict = {}

        for t in np.arange(self.prev_indx, self.indx):
            fissile_dump += self.fissile_db[t, :]
        for i, val in enumerate(fissile_dump):
            if val != 0:
                iso = self.isos[i].decode('utf8')
                fissile_dict[iso] = val
        if bool(fissile_dict):
            fissile_mass = self.blanket_mass * sum(fissile_dict.values())
            material = ts.Material.create(self, fissile_mass, fissile_dict)
            self.fissile_tank.push(material)
            print('PUSHED %f kg of FISSILE MATERIAL INTO FISSILE TANK' %fissile_mass)

    def get_fill_demand(self):
        self.get_fill = False
        blanket_demand_dump = np.zeros(self.num_isotopes)
        driver_demand_dump = np.zeros(self.num_isotopes)
        fill_dict = {}
        for t in np.arange(self.prev_indx, self.indx):
            driver_demand_dump += self.driver_refill[t, :]
            blanket_demand_dump += self.blanket_refill[t, :]
        # since the data is in negative:      
        driver_fill_mass = -1.0 * self.driver_mass * sum(driver_demand_dump)
        blanket_fill_mass = -1.0 * self.blanket_mass * sum(blanket_demand_dump)
        self.qty = driver_fill_mass + blanket_fill_mass
        if (self.qty) == 0:
            return 0 
        self.total_fill_demand = -1.0 * (driver_demand_dump + blanket_demand_dump) 
        for i, val in enumerate(self.total_fill_demand):
            if val != 0:
                iso = self.isos[i].decode('utf8')
                fill_dict[iso] = val
        if bool(fill_dict):
            print('I WANT %f kg DEP U' %(driver_fill_mass+blanket_fill_mass))
            self.demand_mat = ts.Material.create(self, driver_fill_mass + blanket_fill_mass,
                                            fill_dict)
        if self.qty != 0.0:
            self.get_fill = True

    
    def get_material_bids(self, requests):
        """ Gets material bids that want its `outcommod' an
            returns bid portfolio
        """
        bids = []
        # waste commods
        if self.waste_commod not in requests:
            return
        reqs = requests[self.waste_commod]
        for req in reqs:
            qty = min(req.target.quantity, self.waste_tank.quantity)
            # returns if the inventory is empty
            if self.waste_tank.empty():
                return
            # get the composition of the material next in line
            next_in_line = self.waste_tank.peek()
            mat = ts.Material.create_untracked(qty, next_in_line.comp())
            bids.append({'request': req, 'offer': mat})
        
        # fissile commods
        if self.fissile_out_commod not in requests:
            return
        reqs = requests[self.fissile_out_commod]
        for req in reqs:
            qty = min(req.target.quantity, self.fissile_tank.quantity)
            if self.fissile_tank.empty():
                return
            next_in_line =self.fissile_tank.peek()
            mat = ts.Material.create_untracked(qty, next_in_line.comp())
            bids.append({'request': req, 'offer':mat})

        port = {"bids": bids}
        return port


    def get_material_trades(self, trades):
        """ Give out waste_commod and fissile_out_commod from
            waste_tank and fissile_tank, respectively.
        """
        responses = {}
        for trade in trades:
            commodity = trade.request.commodity
            if commodity == self.waste_commod:            
                mat_list = self.waste_tank.pop_n(self.waste_tank.count)
            if commodity == self.fissile_out_commod:
                mat_list = self.fissile_tank.pop_n(self.fissile_tank.count)
            # absorb all materials
            # best way is to do it separately, but idk how to do it :(
            for mat in mat_list[1:]:
                mat_list[0].absorb(mat)
            responses[trade] = mat_list[0]
        return responses


    def get_material_requests(self):
        """ Ask for material fill_commod """
        print(self.get_fill)
        if self.get_fill:
            fill_qty = self.qty
            recipe = self.context.get_recipe(self.fill_recipe)
            target = ts.Material.create_untracked(fill_qty, recipe)
            commods = {self.fill_commod: target}
            port = {'commodities': commods, 'constraints': fill_qty}
            return port
        else:
            return {}

    def accept_material_trades(self, responses):
        """ Get fill_commod and store it into fill_tank """
        for mat in responses.values():
            self.fill_tank.push(mat)
