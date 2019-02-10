import random
import copy
import math
from collections import defaultdict
import numpy as np
import scipy as sp
import h5py
import cyclus
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

    # one row would be 2.1_30000 3.1_40000 4.1_50000 etc
    enr_bu_matrix = ts.VectorString(
        doc="enrichment and burnup matrix",
        tooltip="enrichment_burnup column separated by space"
    )

    n_assem_core = ts.Int(
        doc="Number of assemblies",
        tooltip="Number of assemblies in core"
    )

    n_assem_batch = ts.Int(
        doc="Number of assemblies per batch",
        tooltip="Number of assemblies per batch"
    )

    assem_size = ts.Double(
        doc="Assembly mass",
        tooltip="Assembly mass"
    )

    power_cap = ts.Double(
        doc="Power capacity of reactor",
        tooltip="Power capacity of reactor",
    )

    cycle_time_eq = ts.String(
        doc="cycle time of reactor equation",
        tooltip="Cycle time of reactor equation"
    )

    refuel_time_eq = ts.String(
        doc="Refuel time of reactor equation",
        tooltip="Refuel time of reactor equation"
    )

    core = ts.ResBufMaterialInv()
    waste = ts.ResBufMaterialInv()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def enter_notify(self):
        super().enter_notify()
        self.model_dict = pickle.load(open(self.pickle_path, 'rb'))
        # change other to h-1
        other_index = self.model_dict['iso_list'].index('other')
        self.model_dict['iso_list'][other_index] = 'h-1'
        self.iso_list = self.model_dict['iso_list']

        # check if it's integer batches
        if (self.n_assem_core / self.n_assem_batch)%1 != 0:
            raise ValueError('Sorry can only do integer batches')

        # input consistency checking
        self.enr_matrix, self.bu_matrix = self.check_enr_bu_matrix()

        # !!
        self.f = open('f.txt', 'w')
        # set initial cycle and refuel time
        t = self.context.time
        self.cycle_time = int(eval(self.cycle_time_eq))
        self.refuel_time = int(eval(self.refuel_time_eq))

        # set core capacity
        self.core.capacity = self.n_assem_core * self.assem_size

        self.cycle_step = 0
        self.batch_gen = 0
        self.n_batch = int(self.n_assem_core / self.n_assem_batch)
        # if no exit time, exit time is 1e5
        if self.exit_time == -1:
            self.decom_time = 1e5
        else:
            self.decom_time = self.exit_time

    def tick(self):
        # If time to decommission, where if decommissioning
        # mid cycle, deplete using weighted average
        # and discharge
        if self.context.time == self.decom_time:
            # burnup is prorated by the ratio
            cycle_step_ratio = self.cycle_step / self.cycle_time
            for index, bu_list in enumerate(self.bu_matrix):
                prorated_bu_list = bu_list * cycle_step_ratio
                self.transmute_and_discharge(prorated_bu_list,
                                             self.enr_matrix[index])
            return

        if self.cycle_step == self.cycle_time:
            if self.batch_gen < self.n_batch:
                i = self.batch_gen
            else:
                i = -1
            bu_list = self.bu_matrix[i]
            self.transmute_and_discharge(bu_list,
                                         self.enr_matrix[i])
            self.batch_gen += 1


    def tock(self):
        if (self.cycle_step >= self.cycle_time + self.refuel_time) and (self.is_core_full()):
            t = self.context.time
            self.cycle_time = int(eval(self.cycle_time_eq))
            self.refuel_time = int(eval(self.refuel_time_eq))
            self.cycle_step = 1

        # produce power if core is full
        if (self.cycle_step >= 0) and (self.cycle_step < self.cycle_time) and (self.is_core_full()):
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
        if self.fuel_outcommod in requests.keys():
            reqs = requests[self.fuel_outcommod]
            for req in reqs:
                if self.waste.empty():
                    break
                qty = min(req.target.quantity, self.waste.quantity
                        )
                next_in_line = self.waste.peek()
                mat = ts.Material.create_untracked(qty, next_in_line.comp())
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
            if len(mat_list) > 1:
                for mat in mat_list[1:]:
                    mat_list[0].absorb(mat)
            responses[trade] = mat_list[0]
        return responses

    def get_material_requests(self):
        """ Ask for fuel_incommod"""
        ports = []
        if self.context.time == self.decom_time:
            return []
        if self.is_core_full():
            return []

        recipes = {}
        qty = {}
        mat = {}
        # initial core loading
        if self.batch_gen == 0:
            enr_to_request = self.enr_matrix
            for i in range(np.shape(enr_to_request)[0]):
                for j in range(np.shape(enr_to_request)[1]):
                    comp = {'u-238': 100-enr_to_request[i,j],
                            'u-235': enr_to_request[i,j]}
                    qty = self.assem_size
                    mat = ts.Material.create_untracked(qty, comp)

                    ports.append({'commodities': {self.fuel_incommod: mat},
                                  'constraints': qty})
        # subsequent equilibrium batch loading
        else:
            enr_to_request = self.enr_matrix[-1]
            for enrichment in enr_to_request:
                comp = {'u-238': 100-enrichment,
                        'u-235': enrichment}
                qty = self.assem_size
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
        if self.core.count == self.n_assem_core:
            return True
        else:
            return False


    def predict(self, enr_bu):
        model = self.model_dict['model']
        x = self.model_dict['xscaler'].transform(enr_bu)
        y = self.model_dict['yscaler'].inverse_transform(
                model.predict(x))[0]
        comp_dict = {}
        for indx, iso in enumerate(self.iso_list):
            # zero if model predicts negative
            if y[indx] < 0:
                y[indx] = 0
            comp_dict[iso] = y[indx]
        return comp_dict


    def transmute_and_discharge(self, bu_list, enr_list):
        # this should ideally be one batch,
        if self.batch_gen < self.n_batch:
           enr = enr_list[self.batch_gen]
        else:
            enr = enr_list[-1]
        for indx, bu in enumerate(bu_list):
            enr_bu = [[enr_list[indx],bu]]
            discharge_fuel = self.core.pop()
            comp = self.predict(enr_bu)
            discharge_fuel.transmute(comp)
            self.waste.push(discharge_fuel)


    def produce_power(self, produce=True):
        if produce:
            lib.record_time_series(lib.POWER, self, float(self.power_cap))
        else:
            lib.record_time_series(lib.POWER, self, 0)


    def check_enr_bu_matrix(self):
        # parse bu enr matrix
        empty = np.zeros(len(self.enr_bu_matrix[0].split(' ')))

        for i in self.enr_bu_matrix:
            entry = np.array(i.split(' '))
            if len(entry) != self.n_assem_batch:
                raise ValueError('The length of entry has to match n_assem_batch')
            try:
                empty = np.vstack((empty, entry))
            except ValueError:
                print('Your length of entries per batch are inconsistent!')
        matrix = empty[1:]

        # separate bu and enrichment
        sep = np.char.split(matrix, '_')
        bu_matrix = np.zeros(np.shape(matrix))
        enr_matrix = np.zeros(np.shape(matrix))
        for i in range(np.shape(sep)[0]):
            for j in range(np.shape(sep)[1]):
                enr_matrix[i,j] = float(sep[i,j][0])
                bu_matrix[i,j] = float(sep[i,j][1])

        return enr_matrix, bu_matrix

