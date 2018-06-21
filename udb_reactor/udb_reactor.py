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

    db_path = ts.String(
        doc="Path to the sqlite file of udb data",
        tooltip="Absolute path to the udb sqlite data"
    )

    recipe_name = ts.String(
        doc="if using recipe, this parameter holds the recipe name",
        tooltip="recipe to be used for recipe composition",
        default=''
    )

    inventory = ts.ResBufMaterialInv()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, string):
        # for debugging purposes.
        with open('log.txt', 'a+') as f:
            f.write(string + '\n')

    def enter_notify(self):
        super().enter_notify()
        conn = lite.connect(self.db_path)
        conn.row_factory = lite.Row
        self.cur = conn.cursor()
        assembly_ids = self.cur.execute('SELECT evaluation_date, isotope, '
                                        'sum(total_mass_g) FROM discharge '
                                        'WHERE reactor_id = %i GROUP BY evaluation_date, isotope' %self.reactor_id).fetchall()
        self.assembly_discharge_dict = {}
        print('WEEEEEEEEEEEEEEEEEE')
        for assembly in assembly_ids:
            # lump everything to evaluation date
            self.assembly_discharge_dict[assembly['evaluation_date']] = {assembly['isotope']: float(assembly['sum(total_mass_g)']) * 1e-3}
        # can't find a way to get it from framework
        self.startyear = 1969
        self.startmonth = 1

    def tick(self):
        year_month = self.find_year_month()
        for key, val in self.assembly_discharge_dict.items():
            # [:-3] gets rid of the day
            if key[:-3] == year_month:
                total_mass = sum(val.values())
                if self.recipe_name != '':
                    composition = self.context.get_recipe(self.recipe_name)
                else:
                    composition = {}
                    for iso, mass in val.items():
                        composition[iso.capitalze()] = mass
                material = ts.Material.create(self, total_mass, composition)
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