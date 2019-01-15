import random
import copy
import math
from collections import defaultdict
import numpy as np
import scipy as sp
import pandas as pd
from cyclus.agents import Institution, Agent, Facility
from cyclus import lib
import cyclus.typesystem as ts
import pickle


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

    db_path = ts.String(
        doc="Path to the sqlite file of udb data",
        tooltip="Absolute path to the udb sqlite data"
    )

    recipe_name = ts.String(
        doc="if using recipe, this parameter holds the recipe name",
        tooltip="recipe to be used for recipe composition",
        default=''
    )

    startyear = ts.Int(
        doc="Startyear of simulation",
        tooltip="Simulation Startyear"
    )

    startmonth = ts.Int(
        doc="Startmonth of simulation",
        tooltip="Simulation Startmonth"
    )

    use_rom = ts.Bool(
        doc="Boolean to use reduced-order-model for depletion"
        tooltip="ROM bool"
        default=0
    )

    inventory = ts.ResBufMaterialInv()

    ## Import pickle file into `depletion_model_dict'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, string):
        # for debugging purposes.
        with open('log.txt', 'a+') as f:
            f.write(string + '\n')

    def enter_notify(self):
        super().enter_notify()
        df = pd.read_table(self.db_path)
        self.reactor_assems = df.loc[df['reactor_id'] == self.reactor_id]
        self.reactor_assems['discharge_date'] = self.reactor_assems['discharge_date'].str[:7]
        self.assembly_dates = self.reactor_assems['discharge_date'].unique()
        # for memory
        del df

    def tick(self):
        year_month = self.find_year_month()
        if year_month in self.assembly_dates:
            assembly_id_list = self.reactor_assems.loc[self.reactor_assems['discharge_date'] == year_month]['assembly_id'].unique()

            for assembly in assembly_id_list:
                assem_mass = np.array(
                    self.reactor_assems.loc[self.reactor_assems['assembly_id'] == assembly_id]['initial_uranium_kg'])[0]
                if self.recipe_name != '':
                    composition = self.context.get_recipe(self.recipe_name)
                elif use_rom:
                    composition = self.rom_depletion(assembly)
                else:
                    composition = self.data_depletion(assembly)

                material = ts.Material.create(self, assem_mass, composition)
                self.inventory.push(material)


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

    def find_year_month(self):
        time = self.context.time
        year = self.startyear + time // 12
        month = self.startmonth + time % 12
        if month < 10:
            return (str(year) + '-0' + str(month))
        else:
            return (str(year) + '-' + str(month))

    def rom_depletion(self, assembly_id):
        enr_bu = self.reactor_assems.loc[self.reactor_assems['assembly_id'] == assembly_id][[
            'initial_enrichment', 'discharge_burnup']]
        enr_bu = np.array(enr_bu)[0]
        
        composition = {}
        for iso, model in self.depletion_model_dict.items():
            composition[iso] = model.predict(enr_bu)[0]

    def data_depletion(self, assembly_id):
        assem_data = self.reactor_assems.loc[self.reactor_assems['assembly_id'] == assembly_id][['name', 'total_mass_g']]
        assem_data['comp'] = assem_data['total_mass_g'] / sum(assem_data['total_mass_g'])
        composition = {}
        for indx, row in assem_data.iterrows():
            composition[row['name']] = row['comp']
        return composition