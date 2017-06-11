Required python packages:
  pandas  >= 0.17.1
  numpy   >= 1.10.4

Description:
The program reads input files and distributes working hours over several
days, such that regulatory constraints are met. These constraints are
defined in the `config.py' file.

Input files are required to contain at least following columns:
  tag   -> day of month for the current row
  von   -> start of of work
  bis   -> end of work
  flags -> a `+'-separated list of keywords that describe the current entry:
            dr - business trip
            lo - start of work (von) is fixed and won't be changed
            up - end of work (bis) is fixed and won't be changed

Optional columns are:
  monat -> month of the current entry (overwrites `-m' command-line option)
  jahr  -> year of the current entry (overwrites `-y' command-line option)

The input files must not contain any colums that start and end with `_'. These
are used for internal calculations. Any other columns may be specified and
remain unchanged (e.g. `notes').

It's not necessary to include weekends or holidays, if no work has been done.
