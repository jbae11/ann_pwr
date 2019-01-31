# ANN LWR

This Cyclus Reactor module is created to perform varying
burnup and enrichment calculations for LWRs using a
trained neural network model to predict UNF composition.

The reactor module will behave similarly to the [Cycamore
batch-recipe reactor](https://github.com/cyclus/cycamore),
but it will deplete fuel with user-input burnup.

This reactor can vary burnup for the first n-1 batches,
where n is the total number of batches. The user can
also request varying enrichment fuel for the first n-1 batches.

When decommissioning, the reactor will asses how long the
fuel has been in the reactor and will reduce the burnup
accordingly.

This module requires a pickled file with the trained
ann model.

## Dependencies:
- keras
- numpy
- cyclus
- sklearn
- pickle
