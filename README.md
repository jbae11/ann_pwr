# UDB Reactor

This Cyclus Reactor module is created towards the project
to benchmark Cyclus with ORION UNF-ST&DARDS benchmark.

The reactor module will read the UNF-ST&DARDS dataset
and will output UNF defined by the database. The parameters
for the output commodity are:

1. Output date (finest time step is one month.)
2. Composition
3. Quantity

Each reactor agent will have a `ReactorID` parameter
that will connect the individual prototype with an
actual reactor in the database. This way, we can model
the historical UNF discharge by tracking
individual reactors in the U.S as an agent.

**less bro-y**
I'm guessing this will be different from ORION, and allow
interesting analyses like the GIS mapping and burn-up
characterization by reactor.
