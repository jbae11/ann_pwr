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

    final_fuel_commod = ts.String(
        doc="The commodity name for final discharge fuel",
        tooltip="Final Fuel",
        uilabel="Final Fuel"
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
    fissile_tank = ts.ResBufMaterialInv()

    driver_buf = ts.ResBufMaterialInv()
    blanket_buf = ts.ResBufMaterialInv()

    fill_tank = ts.ResBufMaterialInv()

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
        self.end_driver = self.f['driver composition after reproc'][-1, :]
        self.end_blanket = self.f['blanket composition after reproc'][-1, :]
        self.isos = self.f['iso names']
        self.num_isotopes = len(self.isos)
        self.prev_indx = 0
        # default in saltproc is 3 days
        # probably should have this in the database as well
        ################################ SET AS 30 days
        self.saltproc_timestep = 3 * 24 * 3600 * 10
        self.driver_mass = 1
        self.blanket_mass = 1
        self.driver_buf.capacity = self.driver_mass
        self.blanket_buf.capacity = self.blanket_mass
        self.fresh = True
        self.loaded = False

    def tick(self):
        print('TIME IS %i' %self.context.time)
        if not self.fresh:
            self.indx = self.context.dt * (self.context.time - self.start_time)
            self.indx = int(self.indx / self.saltproc_timestep)
            self.indx = min(self.indx, len(self.waste_db[:, 0])) + 1
            print('INDX IS: %i' %self.indx)
        else:
            self.indx = -1
        # if reactor is `on'
        if self.indx > 0:
            # push waste from db to waste_tank
            self.get_waste()
            # push fissile from db to fissile_tank
            self.get_fissile()

            self.get_fill_demand()
            self.prev_indx = self.indx

        print('DRIVER QTY')
        print(self.driver_buf.quantity)
        
        print('BLANKET QTY')
        print(self.blanket_buf.quantity)


    def tock(self):

        # check if core is full;
        if (self.driver_buf.quantity == self.driver_buf.capacity and
            self.blanket_buf.quantity == self.blanket_buf.capacity):
            self.loaded = True
            print('REACTOR IS LOADED')
            if self.fresh:
                self.start_time = self.context.time
                self.fresh = False
        else:
            print('DRIVER OR BLANKET IS NOT FULL IN TIME %s \n\n' %self.context.time)
            self.loaded = False

        print('TOCK\n')

    def get_waste(self):
        waste_dump = np.zeros(self.num_isotopes)
        waste_dict = {}
        # lump all the waste generated in this timestep
        # into one waste dump
        for t in np.arange(self.prev_indx, self.indx):
            waste_dump += self.waste_db[t, :]
        # convert this into a dictionary

        waste_dict = self.array_to_comp_dict(waste_dump)
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

        fissile_dict = self.array_to_comp_dict(fissile_dump)

        if bool(fissile_dict):
            fissile_mass = self.blanket_mass * sum(fissile_dict.values())
            material = ts.Material.create(self, fissile_mass, fissile_dict)
            self.fissile_tank.push(material)
            print('PUSHED %f kg of FISSILE MATERIAL INTO FISSILE TANK' %fissile_mass)


    def get_fill_demand(self):
        self.get_fill = False
        blanket_demand_dump = np.zeros(self.num_isotopes)
        driver_demand_dump = np.zeros(self.num_isotopes)
        fill_comp_dict = {}
        # since the data is in negative:
        for t in np.arange(self.prev_indx, self.indx):
            driver_demand_dump += -1.0 * self.driver_refill[t, :]
            blanket_demand_dump += -1.0 * self.blanket_refill[t, :]
        driver_fill_mass = self.driver_mass * sum(driver_demand_dump)
        blanket_fill_mass = self.blanket_mass * sum(blanket_demand_dump)

        # pop mass to make room
        self.driver_buf.pop(driver_fill_mass)
        self.blanket_buf.pop(blanket_fill_mass)

        self.qty = driver_fill_mass + blanket_fill_mass
        if (self.qty) == 0:
            return 0 
        self.fill_comp = driver_demand_dump + blanket_demand_dump 
        
        fill_comp_dict = self.array_to_comp_dict(self.fill_comp)

        if bool(fill_comp_dict):
            print('I WANT %f kg DEP U' %(self.qty))
            self.demand_mat = ts.Material.create_untracked(self.qty, fill_comp_dict)
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

        if self.context.time == self.exit_time:
            reqs = requests[self.final_fuel_commod]
            for req in reqs:
                total_qty = self.driver_buf.quantity + self.blanket_buf.quantity
                qty = min(req.target.quantity, total_qty)
                if self.driver_buf.empty():
                    return
                driver = self.driver_buf.peek()
                blanket = self.blanket_buf.peek()
                driver.absorb(blanket)
                bids.append({'request': req, 'offer': driver})                                
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
            if commodity == self.final_fuel_commod:
                blank_comp = self.array_to_comp_dict(self.end_blanket)
                driver_comp = self.array_to_comp_dict(self.end_driver)
                blank = ts.Material.create(self, self.blanket_mass, blank_comp)
                driv = ts.Material.create(self, self.driver_mass, driver_comp)
                driv.absorb(blank)
                mat_list = [driv]
            # absorb all materials
            # best way is to do it separately, but idk how to do it :(
            for mat in mat_list[1:]:
                mat_list[0].absorb(mat)
            responses[trade] = mat_list[0]
        return responses


    def get_material_requests(self):
        """ Ask for material fill_commod """
        if not self.loaded:
            driver_recipe = {'92235': 1}
            d_qty = self.driver_buf.capacity - self.driver_buf.quantity
            driver_mat = ts.Material.create_untracked(d_qty, driver_recipe)

            blanket_recipe = {'92238': 1}
            b_qty = self.blanket_buf.capacity - self.blanket_buf.quantity
            blanket_mat = ts.Material.create_untracked(b_qty, blanket_recipe)

            ports = [{'commodities': {self.init_fuel_commod: driver_mat}, 'constraints': d_qty},
                     {'commodities': {self.fill_commod: blanket_mat}, 'constraints': b_qty}]
            return ports
        elif self.get_fill:
            commods = {self.fill_commod: self.demand_mat}
            port = {'commodities': commods, 'constraints': self.qty}
            return port
        else:
            return {}

    def accept_material_trades(self, responses):
        """ Get fill_commod and store it into fill_tank """
        for key, mat in responses.items():
            if key.request.commodity == self.init_fuel_commod and not self.loaded:
                self.driver_buf.push(mat)
            elif key.request.commodity == self.fill_commod:
                to_blanket = mat.extract_qty(self.blanket_buf.space)
                self.blanket_buf.push(to_blanket)
                self.driver_buf.push(mat)


    def array_to_comp_dict(self, array):
        dictionary = {}
        for i, val in enumerate(array):
            if val != 0:
                iso = self.isos[i].decode('utf8')
                dictionary[iso] = val
        return dictionary