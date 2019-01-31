import random
import copy
import math
from collections import defaultdict
import numpy as np
import scipy as sp
import h5py
import pickle
from cyclus.agents import Institution, Agent, Facility
from cyclus import lib
import cyclus.typesystem as ts


class ann_lwr(Facility):
    fuel_incommod = ts.String(
        doc="The commodity name for incoming fuel",
        tooltip="Incoming fuel",
        uilabel="Incoming fuel"
    )

    fuel_outcommod = ts.String(
        doc="The commodity name for discharge fuel",
        tooltip="Discharge Fuel",
        uilabel="Discharge Fuel"
    )

    pickle_path = ts.String(
        doc="Path to the pickle file",
        tooltip="Absolute path to the pickle file"
    )

    burnup_list = ts.VectorDouble(
        doc="Burnup list for n batches",
        tooltip="Bunrup list for n batches"
    )

    enrichment_list = ts.VectorDouble(
        doc="Enrichment list for n batches",
        tooltip="Enrichment list for n batches"
    )

    n_batch = ts.Int(
        doc="Number of batches",
        tooltip="Number of batches for reactor"
    )

    batch_mass = ts.Double(
        doc="Mass per batch",
        tooltip="Mass per batch"
    )

    power_cap = ts.Double(
        doc="Power capacity of reactor",
        tooltip="Power capacity of reactor",
    )

    cycle_time = ts.Int(
        doc="cycle time of reactor",
        tooltip="Cycle time of reactor"
    )

    refuel_time = ts.Int(
        doc="Refuel time of reactor",
        tooltip="Refuel time of reactor"
    )

    core = ts.ResBufMaterialInv()
    waste = ts.ResBufMaterialInv()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def enter_notify(self):
        super().enter_notify()
        self.model_dict = pickle.load(open(pickle_path, 'rb'))
        # change other to h-1
        other_index = self.model_dict['iso_list'].index('other')
        self.model_dict['iso_list'][other_index] = 'h-1'

        # input consistency checking:
        if len(self.burnup_list) != n_batch or len(self.enrichmnet_list) != n_batch:
            raise ValueError('Burnup and Enrichment list length has to match n_batch')

        # set core capacity
        self.core.capacity = self.n_batch * self.batch_mass

        self.cycle_step = 0
        self.batch_gen = 0

    def tick(self):
        # If time to decommission, where if decommissioning
        # mid cycle, deplete using weighted average
        # and discharge
        if self.context.time == self.exit_time + 1:
            # burnup is prorated by the ratio
            cycle_step_ratio = cycle_step / cycle_time
            for bu in self.burnup_list:
                prorate_bu = bu * cycle_step_ratio
                self.transmute_and_discharge(self.batch_mass,
                                             prorated_bu)
            return

        if self.cycle_step == self.cycle_time:
            if self.batch_gen < len(self.n_batch):
                bu = self.burnup_list[self.batch_gen]
            else:
                bu = self.burnup_list[-1]
            self.transmute_and_discharge(self.batch_mass,
                                         bu)
            self.batch_gen += 1

    def tock(self):
        if (self.cycle_step >= self.cycle_time + self.refuel_time) and (self.is_core_full()):
            self.cycle_step = 0

        # produce power if core is full
        if self.cycle_step >= 0 and self.cycle_step < self.cycle_time and self.is_core_full():
            self.produce_power(True)
        else:
            self.produce_power(False)

        if self.cycle_step > 0 or self.is_core_full():
            self.cycle_step += 1



    def get_material_bids(self, requests):
        """ Gets material bids that want its 'outcommod' and
            returns bid portfolio
        """
        bids = []
        try:
            reqs = requests[self.fuel_outcommod]
            for req in reqs:
                qty = min(req.target.quantity, self.waste.quantity)
                if self.waste.empty():
                    break
                mat = ts.Material.create_untracked(qty, self.waste.peek().comp())
                bids.append({'request': req, 'offer': mat})

        if len(bids) == 0:
            return
        port = {'bids': bids}
        return port

    def get_material_trades(self, trades):
        """ Give out fuel_outcommod from waste buffer"""
        responses = {}
        for trade in trades:
            commodity = trade.request.commodity
            if commodity == self.fuel_outcommod:
                mat_list = self.waste.pop_n(self.waste.count)

            if len(mat) > 1:
                for mat in mat_list[1:]:
                    mat_list[0].absorb(mat)
            responses[trade] = mat_list[0]
        return responses

    def get_material_requests(self):
        """ Ask for fuel_incommod"""
        ports = []
        if self.is_core_full():
            return {}

        if self.batch_gen == 0:
            enr_to_request = self.enrichment_list
        else:
            enr_to_request = [self.enrichment_list[-1]]

        recipes = {}
        qty = {}
        mat = {}
        for enrichment in enr_to_request:
            comp = {'u-238': 100-enrichment
                    'u-235': enrichment}
            qty = batch_mass
            mat = ts.Material.create_untracked(qty, comp)
            ports.append({'commodities' : {self.fuel_incommod: mat},
                          'constraints': qty})
        return ports


    def accept_material_trades(self, responses):
        """ Get fuel_incommod and store it into core"""
        for key, mat in responses.items():
            if key.request.commodity == self.fuel_incommod:
                self.core.push(mat)


    def is_core_full(self):
        if self.core.quantity == self.core.capacity:
            return True
        else:
            return False

    def get_enrichment(self):
        """ Returns the average enrichment of fuel in core """
        in_core_fuel = self.core.peek(self.core.quantity)
        composition = in_core_fuel.comp()
        print(composition)
        return composition['U-235']


    def predict(self, enr_bu):
        model = self.model_dict['model']
        x = self.model_dict['xscaler'].transform(enr_bu)
        y = self.model_dict['yscaler'].inverse_transform(
                model.predict(x))[0]
        comp_dict = {}
        for indx, iso in enumerate(iso_list):
            comp_dict[iso] = y[indx]
        return comp_dict


    def transmute_and_discharge(self, quantity, bu):
        # this should ideally be one batch,
        # so not pop_qty but just pop
        discharge_fuel = self.core.pop_qty(quantity)
        enr_bu = [[self.get_enrichment(), bu]]
        comp = self.predict(enr_bu)
        discharge_fuel.comp() = comp
        self.waste.push(discharge_fuel)

    def produce_power(self, produce=True):
        if produce:
            lib.record_time_series(lib.POWER, self, float(self.power_cap))
        else:
            lib.record_time_series(lib.POWER, self, 0)

