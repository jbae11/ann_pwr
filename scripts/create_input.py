import sqlite3 as lite
import os

""" This script generates two cyclus input files:
  one where the recipe is used, and the other using the udb database

  Separate xml files are created for simplicity, and XInclude is used."""

db_path = '/home/teddy/github/udb_reactor/db/1yr.sqlite'
output_path = 'input.xml'
recipe_output_path = 'recipe_input.xml'

conn = lite.connect(db_path)
conn.row_factory = lite.Row
cur = conn.cursor()

reactor_ids = cur.execute('SELECT distinct(reactor_id) FROM discharge').fetchall()
id_list = []
for row in reactor_ids:
  id_list.append(row['reactor_id'])


# start year is 1969-01
xml_file = """
<simulation xmlns:xi="http://www.w3.org/2001/XInclude">

  <archetypes>
    <spec>
      <lib>agents</lib>
      <name>NullRegion</name>
    </spec>
    <spec>
      <lib>agents</lib>
      <name>NullInst</name>
    </spec>
    <spec>
      <lib>cycamore</lib>
      <name>Sink</name>
    </spec>
    <spec>
      <lib>udb_reactor.udb_reactor</lib>
      <name>udb_reactor</name>
    </spec>
  </archetypes>

  <control>
    <!-- 2020/07 - 1969/01 -->
    <duration>619</duration>
    <startmonth>1</startmonth>
    <startyear>1969</startyear>
    <decay>manual</decay>
  </control>


"""

archetype_file = "<root>"
for reactor_id in id_list:
    archetype_file += """
    <facility>
        <config>
          <udb_reactor>
            <outcommod>fuel</outcommod>
            <reactor_id>%i</reactor_id>
            <db_path>%s</db_path>
            <recipe_name>used_fuel_recipe</recipe_name>
          </udb_reactor>
        </config>
        <name>%i</name>
    </facility>
    """ %(reactor_id, db_path, reactor_id)

archetype_file += "</root>"
with open('./archetype_recipe.xml', 'w') as f:
    f.write(archetype_file)

archetype_without_recipe = archetype_file.replace('<recipe_name>used_fuel_recipe</recipe_name>\n', '')
with open('./archetype.xml', 'w') as f:
    f.write(archetype_without_recipe)


xml_file += """

  <xi:include href="./archetype_recipe.xml" xpointer="xpointer(/root/facility)"/>

  <facility>
    <name>sink</name>
    <config>
      <Sink>
        <in_commods><val>fuel</val></in_commods>
        <capacity>1e100</capacity>
      </Sink>
    </config>
  </facility>
"""

xml_file += """

<region>
    <name>SingleRegion</name>
    <config><NullRegion/></config>
    <institution>
      <name>udb_reactor_inst</name>
      <initialfacilitylist>
      <entry>
        <prototype>sink</prototype>
        <number>1</number>
      </entry>
"""

entry_file = "<root>"
for reactor_id in reactor_ids:
    entry_file += """
        <entry>
          <prototype>%i</prototype>
          <number>1</number>
        </entry>
    """ %reactor_id['reactor_id']
entry_file += "</root>"
with open('prototype.xml', 'w') as f:
    f.write(entry_file)

xml_file += """
      <xi:include href="./prototype.xml" xpointer="xpointer(/root/entry)"/>
      </initialfacilitylist>
      <config>
      <NullInst/>
      </config>
    </institution>
  </region>
"""

xml_file += """<xi:include href="avg_recipe.xml" xpointer="xpointer(/root/recipe)"/>
            </simulation>"""


with open(recipe_output_path, 'w') as f:
    f.write(xml_file)

xml_file_without_recipe = xml_file.replace('<xi:include href="./archetype_recipe.xml" xpointer="xpointer(/root/facility)"/>',
                                           '<xi:include href="./archetype.xml" xpointer="xpointer(/root/facility)"/>')
xml_file_without_recipe = xml_file_without_recipe.replace('<xi:include href="avg_recipe.xml" xpointer="xpointer(/root/recipe)"/>',
                                                          '')

with open(output_path, 'w') as f:
    f.write(xml_file_without_recipe)


# generate recipe block
# by taking the average and finding the assembly closest
# to the average burnup and enrichment to the average
avg_burnup = cur.execute('SELECT avg(discharge_burnup) FROM discharge').fetchone()[0]
avg_enrichment = cur.execute('SELECT avg(initial_enrichment) FROM discharge').fetchone()[0]
min_diff = cur.execute('SELECT assembly_id, min(abs(discharge_burnup - %f) + abs(initial_enrichment - %f)) '
                       'FROM discharge' %(avg_burnup, avg_enrichment)).fetchone()[0]
chosen_assem = cur.execute('SELECT * FROM discharge WHERE assembly_id = %i' %min_diff).fetchall()
total_mass = chosen_assem[0]['initial_uranium_kg']
with open('avg_recipe.xml', 'w') as f:
    head = "<root>\n<recipe>\n\t<name>used_fuel_recipe</name>\n\t<basis>mass</basis>\n"
    for row in chosen_assem:
        head += '\t\t<nuclide> <id>%s</id> <comp>%f</comp> </nuclide>\n' %(row['isotope'].capitalize(), float(row['total_mass_g']) * 0.1 / total_mass)
    head += '</recipe></root>'
    f.write(head)

print('DONE!')