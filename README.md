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
ann model. The pickled file, when imported, is a dictionary
with keys:
- model: Keras trained model object
- xscaler: sklearn.preprocessing.MinMaxScaler object to transform [enrichment, burnup] to standard values for model
- yscaler: sklearn.preprocessing.MinMaxScaler object to transform model prediction results to standard value [% of fuel]
- iso_list: list of isotope names for model prediction (index matches y indexes)


## Inputs:
- fuel_incommod: commodity name for incoming fuel
- fuel_outcommod: commodity name for outgoing fuel
- pickle_path: absolute path of the pickle file- n_batch: number of batches for reactor
- burnup_list: list of burnup values, starting from first batch to equilibrium. Length must match `n_batch`
- enrichment_list: list of enrichment values, starting from first batch to equilibrium. Length must match `n_batch`
- batch_mass: fuel mass per batch in kg
- power_cap: power produced by reactor when operational (units arbitrary)
- cycle_time: operational cycle time of reactor,
- refuel_time: time for reactor to refuel, reactor is not operational during this time.

## Dependencies:
- keras
- numpy
- cyclus
- sklearn
- pickle
