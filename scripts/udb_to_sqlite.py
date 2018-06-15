import sqlite3
import os

dat_file_name = 'SNF_nuclide_1yr_Cooling(1).dat'
sqlite_name = '1yr.sqlite'

# delete file if exists
try:
    os.remove(sqlite_name)
except OSError:
    pass

with open(dat_file_name) as f:
    rows = f.readlines()

# creates new file if non-existant
conn = sqlite3.connect(sqlite_name)
cur = conn.cursor()
cur.execute(""" CREATE TABLE IF NOT EXISTS discharge (
                    assembly_id integer,
                    reactor_id integer,
                    reactor_type text,
                    initial_uranium_kg real,
                    initial_enrichment real,
                    discharge_burnup real,
                    discharge_date text,
                    evaluation_date text,
                    isotope text,
                    total_mass_g text
            );""")

for row in rows[1:]:
    split_row = row.split('\t')
    values = (split_row[0], split_row[1], split_row[2], split_row[3],
              split_row[4], split_row[5], split_row[6], split_row[9],
              split_row[8], split_row[10])
    #print(values)
    query = """ INSERT INTO discharge(assembly_id,
                reactor_id, reactor_type, initial_uranium_kg,
                initial_enrichment, discharge_burnup, discharge_date,
                evaluation_date, isotope, total_mass_g)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) """
    cur.execute(query, values)


