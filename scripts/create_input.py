import sqlite3 as lite
import os

db_path = '/home/teddy/github/udb_reactor/db/1yr.sqlite'
output_path = 'output.xml'
archetype_path = 'archetype.xml'
entry_path = "entry.xml"

conn = lite.connect(db_path)
conn.row_factory = lite.Row
cur = conn.cursor()

reactor_ids = cur.execute('SELECT distinct(reactor_id) FROM discharge').fetchall()


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
    <duration>612</duration>
    <startmonth>1</startmonth>
    <startyear>1969</startyear>
    <decay>manual</decay>
  </control>


"""

archetype_file = "<root>"
for reactor_id in reactor_ids:
    archetype_file += """
    <facility>
        <config>
          <udb_reactor>
            <outcommod>fuel</outcommod>
            <reactor_id>%i</reactor_id>
            <db_path>%s</db_path>
          </udb_reactor>
        </config>
        <name>%i</name>
    </facility>
    """ %(reactor_id['reactor_id'], db_path, reactor_id['reactor_id'])
archetype_file += "</root>"
with open(archetype_path, 'w') as f:
    f.write(archetype_file)

xml_file += """

  <xi:include href="%s" xpointer="xpointer(/root/facility)"/>

  <facility>
    <name>sink</name>
    <config>
      <Sink>
        <in_commods><val>fuel</val></in_commods>
        <capacity>1e100</capacity>
      </Sink>
    </config>
  </facility>
""" %archetype_path

xml_file += """

<region>
    <name>SingleRegion</name>
    <config><NullRegion/></config>
    <institution>
      <name>udb_reactor_inst</name>
      <initialfacilitylist>
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
with open(entry_path, 'w') as f:
    f.write(entry_file)

xml_file += """
      <xi:include href="%s" xpointer="xpointer(/root/entry)"/>
      </initialfacilitylist>
      <config>
      <NullInst/>
      </config>
    </institution>
  </region>
</simulation>
""" %entry_path

with open(output_path, 'w') as f:
    f.write(xml_file)