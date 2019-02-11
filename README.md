# ANN LWR

This Cyclus Reactor module is created to perform varying
burnup and enrichment calculations for LWRs using a
trained neural network model to predict UNF composition.

The reactor module will behave similarly to the [Cycamore
batch-recipe reactor](https://github.com/cyclus/cycamore),
but it will deplete fuel with user-input burnup.

The user defines the enrichment and burnup matrix, as a list of strings
separated by spaces, where each entry is a `enrichment_burnup` format.
For example, for a core with 24 assemblies and 8 assemblies per batch,
the input is the following:
```
<enr_bu_matrix>
    <val>2.1_30000 3.1_30000 3.1_30000 3.1_30000 3.1_30000 4.1_30000 4.1_30000 3.1_30000</val>
    <val>3.1_32000 3.1_34000 3.1_40000 3.1_36000 3.1_39000 4.1_32000 3.5_40000 3.2_36000</val>
    <val>2.1_33000 3.5_34000 3.2_43000 2.8_43100 3.1_28000 4.5_42000 3.1_23555 3.1_30000</val>
</enr_bu_matrix>
```
The numbers could also be equations. For example, if the user wanted the
burnup of the equilibrium fuel to increase by 1% every month:
```
<enr_bu_matrix>
    <val>2.1_30000 3.1_30000 3.1_30000 3.1_30000 3.1_30000 4.1_30000 4.1_30000 3.1_30000</val>
    <val>3.1_32000 3.1_34000 3.1_40000 3.1_36000 3.1_39000 4.1_32000 3.5_40000 3.2_36000</val>
    <val>2.1_33000*(1.01)**t 3.5_34000*(1.01)**t 3.2_43000*(1.01)**t 2.8_43100*(1.01)**t 3.1_28000*(1.01)**t 4.5_42000*(1.01)**t 3.1_23555*(1.01)**t 3.1_30000*(1.01)**t</val>
</enr_bu_matrix>
```

Currently, only integer batches are accepted.

When decommissioning, the reactor will asses how long the
fuel has been in the reactor and will reduce the burnup
accordingly.

Also, the user can choose to define the cycle time and refuel
time as a function of **simulation time** by writing the `cycle_time_eq`
and `refuel_time_eq` variable as a function of `t`. For example,
if the user wants the cycle time to linearly increase with time,
```
<cycle_time_eq>18+t/100</cycle_time_eq>
<refuel_time_eq>1+t/100</refuel_time_eq>
```
This input will increase the cycle time and refuel time by 1
every 100 timesteps. Note that the t here is **simulation time**,
not reactor age.

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
- enr_bu_matrix: vector of strings separated by space. Shape must be `n_assem_core / n_assem_batch` X `n_assem_batch`
- assem_size: fuel mass per assembly in kg
- power_cap: power produced by reactor when operational (units arbitrary)
- cycle_time_eq: operational cycle time of reactor equation
- refuel_time_eq: time equation for reactor to refuel, reactor is not operational during this time.

## Dependencies:
- keras
- numpy
- cyclus
- sklearn
- pickle
