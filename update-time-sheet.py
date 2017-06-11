#!/usr/bin/env python
# coding: utf8

import pandas as pd
import numpy as np
import datetime
import calendar
import config


constraints = dict(
  anwesend_max = 10.,
  dienstreise_max = 12.,
  erholung_min = 11.,
  regulaer_anwesend_min = 7.,
  regulaer_anwesend_max = 20.,
)

# Available flags
available_flags = [
  # 'za', # ZeitAusgleich
  # 'ma', # MehrArbeit
  'dr', # DienstReise
  # 'we', # WochenEnde
  # 'sa', # SAmstag
  # 'so', # SOnntag
  # 'ft', # FeierTag
  # 'bt', # BrückenTag
  # 'rt', # Regulärer Tag: Fixiere auf 7.6h und verteile den Rest
  # 'fix', # FIXiere von- und bis-Zeit
  # 'fix-von', # FIXiere Von-Zeit
  # 'fix-bis', # FIXiere Bis-Zeit
  'lo', # Fixiere Von-Zeit (LOwer bounded)
  'up', # Fixiere Bis-Zeit (UPper bounded)
  '',   # Internes Flag
  ]

def readFile(fname, year, month):
  #{{{
  assert fname is not None, 'Missing input file!'
  import os

  ext = os.path.splitext(fname)[1].lower()
  with open(fname, 'r') as f:
    if '.csv' == ext: data = readData(f, year, month, 'csv')
    elif '.xlsx' == ext: data = readData(f, year, month, 'excel')
    else: data = None

  assert data is not None, 'Could not read file `%s\': Unknown file extension!' % os.path.basename(fname)
  return data
  #}}}


def readData(f, year, month, dtype = 'csv'):
  #{{{
  assert f is not None

  if 'csv' == dtype:  data = pd.read_csv(f)
  elif 'excel' == dtype: data = pd.read_excel(f)
  else: data = None
  assert data is not None, 'Invalid data type `%s\'!' % dtype

  # Required columns
  for col in ['von', 'bis', 'tag', 'flags']:
    assert col in data.columns, 'Could not find column `%s\'!' % col

  # Optional columns
  if 'monat' not in data.columns: data['monat'] = month
  if 'jahr' not in data.columns: data['jahr'] = year
  
  # Fill columns with default values
  # 1. Von/Bis
  assert all(data['von'].isnull() == data['bis'].isnull()), 'Incompatible columns `von\' and `bis\'!'
  data['von'] = data['von'].fillna('00:00')
  data['bis'] = data['bis'].fillna('00:00')
  data['monat'] = data['monat'].fillna(month)
  data['jahr'] = data['jahr'].fillna(year)

  # 2. Flags
  data['flags'] = data['flags'].fillna('')
  return data
  #}}}


def normalizeData(data):
  #{{{
  assert data is not None

  def _help_datetime_(x, col):
    str_ts = '%04i-%02i-%02i %s' % (x['jahr'], x['monat'], x['tag'], x[col])
    return datetime.datetime.strptime(str_ts, '%Y-%m-%d %H:%M')

  # Calculate date and time
  data['_from_'] = data.apply(lambda x: _help_datetime_(x, 'von'), axis = 1)
  data['_till_'] = data.apply(lambda x: _help_datetime_(x, 'bis'), axis = 1)
  data.loc[data['_from_'] > data['_till_'], '_till_'] += datetime.timedelta(1)
  # Insert data from previous and following days
  data['_prev_till_'] = data['_till_'].shift(+1)
  data['_next_from_'] = data['_from_'].shift(-1)

  # Calculate weekdays
  data['_wday_'] = data['_from_'].apply(lambda x: calendar.day_abbr[x.weekday()])

  # Split flag-strings into lists of flags (also strip unneeded whitespace)
  data['_flags_'] = data['flags'].apply(lambda x: [f.strip() for f in x.lower().split('+')])
  for index, x in data.iterrows():
    if not all([f in available_flags for f in x['_flags_']]):
      log.warning('There are unknown flags at data index %i!' % index)

  # Derive maximum working hours from flags
  data['_max_'] = data.apply(getMaximumWorkingTime, axis = 1)

  # Check for fixin flags
  data['_fix-lower_'] = data['_flags_'].apply(lambda x: 'lo' in x)
  data['_fix-upper_'] = data['_flags_'].apply(lambda x: 'up' in x)
  return data
  #}}}


def getMaximumWorkingTime(x):
  #{{{
  # Weekday (0: Monday, ..., 6: Sunday)
  # if x['_from_'].weekday() in [5, 6]: # Weekend -> 0 hrs
  #   # days, milli-s., micro-s., sec., min., hour, week
  #   return datetime.timedelta(0, 0, 0, 0, 0, 0, 0)
  # elif 'ft' in x['_flags_']:  # Holiday
  #   return datetime.timedelta(0, 0, 0, 0, 0, 0, 0)
  # elif 'za' in x['_flags_']: # Zeitausleich
  #   return datetime.timedelta(0, 0, 0, 0, 0, 0, 0)
  if 'dr' in x['_flags_']:  # Business trip -> max. 12 hrs
    # return datetime.timedelta(0, 0, 0, 0, 0, 12, 0)
    return config.max_dienstreise
  else: # Regular business day -> max. 10 hrs
    # return datetime.timedelta(0, 0, 0, 0, 0, 10, 0)
    return config.max_anwesenheit
  #}}}


def calculateWorkTimeRegulations(data, prefix = ''):
  #{{{
  assert data is not None

  # Calculate total working time (i.e. difference between start and end of business day)
  data[prefix + '_total_'] = data[prefix + '_till_'] - data[prefix + '_from_']
  # Calculate recreational time (i.e. time since previous end of business day)
  data[prefix + '_break_'] = data[prefix + '_from_'] - data[prefix + '_till_'].shift(1)
  return data
  #}}}


def calculateMinMaxOfWork(data):
  #{{{
  assert data is not None

  # Rows, that're only lower bounded...
  I_lo =  data['_fix-lower_'] & ~data['_fix-upper_']
  if 0 < I_lo.sum():
    data.loc[I_lo, '_min_from_'] = data.loc[I_lo, '_from_']
    data.loc[I_lo, '_max_till_'] = data.loc[I_lo, '_from_'] + data.loc[I_lo, '_max_']

  # Rows, that're only upper bounded...
  I_hi = ~data['_fix-lower_'] &  data['_fix-upper_']
  if 0 < I_hi.sum():
    data.loc[I_hi, '_min_from_'] = data.loc[I_hi, '_till_'] - data.loc[I_hi, '_max_']
    data.loc[I_hi, '_max_till_'] = data.loc[I_hi, '_till_']

  # Rows, that're both lower and upper bounded...
  I_xx =  data['_fix-lower_'] &  data['_fix-upper_']
  if 0 < I_xx.sum():
    data.loc[I_xx, '_min_from_'] = data.loc[I_xx, '_from_']
    data.loc[I_xx, '_max_till_'] = data.loc[I_xx, '_till_']

  # Rows, that're unbounded...
  I_no = ~data['_fix-lower_'] & ~data['_fix-upper_']

  default_min = lambda x: datetime.datetime.combine(x.date(), config.min_von_anwesend)
  default_max = lambda x: datetime.datetime.combine(x.date(), config.max_bis_anwesend)

  # Helper functions for iterating over the datatable...
  def _help_min_from_(x): return max(default_min(x['_from_']), x['_prev_till_'] + config.min_erholung)
  def _help_max_till_(x): return min(default_max(x['_till_']), x['_next_from_'] - config.min_erholung)

  if 0 < I_no.sum():
    data.loc[I_no, '_min_from_'] = data[I_no].apply(_help_min_from_, axis = 1)
    data.loc[I_no, '_max_till_'] = data[I_no].apply(_help_max_till_, axis = 1)
  return data
  #}}}


def checkSolvability(data):
  #{{{
  def _help_avail_(x):
    hrs = x['_max_till_'] - x['_min_from_']
    if x['_fix-lower_'] and x['_fix-upper_']:
      return hrs
    else: return min(x['_max_'], hrs)

  data['_avail_'] = data.apply(_help_avail_, axis = 1)
  data['_excess_'] = data.apply(lambda x: max(datetime.timedelta(0), x['_total_'] - x['_avail_']), axis = 1)
  data['_cappa_'] = data.apply(lambda x: max(datetime.timedelta(0), x['_avail_'] - x['_total_']), axis = 1)
  data['_adjust_'] = datetime.timedelta(0)
  return data['_avail_'].sum() >= data['_total_'].sum()
  #}}}


def adjustTimesToRegulations(data, prefix = '_new', in_prefix = ''):
  #{{{
  assert data is not None

  excess = data['_excess_'].sum()

  while datetime.timedelta(0) < excess:
    for index, x in data.iterrows():
      if x['_cappa_'] > datetime.timedelta(0):
        data.loc[index, '_adjust_'] = min(x['_cappa_'], excess)
        data.loc[index, '_cappa_'] -= x['_adjust_']
        excess -= data.loc[index, '_adjust_']
      else: continue #data.loc[index, '_adjust_'] = -x['_excess_']

  data[prefix + '_total_'] = data['_total_'] + data['_adjust_'] - data['_excess_']

  for index, x in data.iterrows():
    if x['_fix-lower_'] and x['_fix-upper_']:
      data.loc[index, prefix + '_from_'] = x['_min_from_']
      data.loc[index, prefix + '_till_'] = x['_max_till_']
    elif  x['_fix-lower_'] and ~x['_fix-upper_']:
      data.loc[index, prefix + '_from_'] = x['_min_from_']
      data.loc[index, prefix + '_till_'] = x['_min_from_'] + x[prefix + '_total_']
    elif ~x['_fix-lower_'] and  x['_fix-upper_']:
      data.loc[index, prefix + '_from_'] = x['_max_till_'] - x[prefix + '_total_']
      data.loc[index, prefix + '_till_'] = x['_max_till_']
    else:
      # Calculate earliest and latest start and end of work to hold new total hours
      new_tl = x[prefix + '_total_'] / 2
      min_lo = data.loc[index, '_min_from_'] + new_tl
      max_up = data.loc[index, '_max_till_'] - new_tl
      # Calculate pari-time for old schedule
      old_cc = data.loc[index, '_from_'] + x['_total_'] / 2
      # Determine new pari-time that is closest to the old one
      new_cc = np.clip(old_cc, min_lo, max_up)
      # Update start nd end of day according to the working hours
      data.loc[index, prefix + '_from_'] = new_cc - new_tl
      data.loc[index, prefix + '_till_'] = new_cc + new_tl
      # Deprecated:
      # if x['i.O.'] and x['_adjust_'] == datetime.timedelta(0):
      #   data.loc[index, prefix + '_from_'] = x['_from_']
      #   data.loc[index, prefix + '_till_'] = x['_till_']
      # else:
      #   data.loc[index, prefix + '_from_'] = x['_min_from_'] + (x['_avail_'] - x[prefix + '_total_']) / 2
      #   data.loc[index, prefix + '_till_'] = x['_min_from_'] + (x['_avail_'] + x[prefix + '_total_']) / 2

  return data
  #}}}


def checkWorkingTimes(data, prefix = ''):
  #{{{
  # Maximum working hours exceeded
  I_maxWorkExcess = data[prefix + '_total_'] > data['_max_']
  
  # Minimum break between working days
  I_minBreakShort = data[prefix + '_break_'] < config.min_erholung
  
  I_fixedWorkTime = data['_fix-lower_'] & data['_fix-upper_']
  
  I_days_niO = ( I_maxWorkExcess |  I_minBreakShort) & ~I_fixedWorkTime
  I_days_iO  = ((~I_maxWorkExcess & ~I_minBreakShort) |  I_fixedWorkTime)
  
  return I_days_iO, I_days_niO, I_maxWorkExcess, I_minBreakShort, I_fixedWorkTime
  #}}}


def formatColumns(data):
  #{{{
  data['_new_from_'] = data['_new_from_'].dt.strftime('%H:%M')
  data['_new_till_'] = data['_new_till_'].dt.strftime('%H:%M')
  return data
  #}}}


def flags2str(flags, fmt = 'short', extra = []):
  #{{{
  if 'short' == fmt:
    s = ''
    s += 'd' if 'dr' in flags else '-'
    s += 'l' if 'lo' in flags else '-'
    s += 'u' if 'up' in flags else '-'
    s += ''.join(extra)
  elif 'list' == fmt:
    s = ' + '.join(sorted(flags + extra))
  else: raise ValueError('Invalid format: %s' % fmt)
  return s
  #}}}


if '__main__' == __name__:
  #{{{
  import getopt, sys, os
  import logging as log

  opts, args = getopt.getopt(sys.argv[1:], 'hm:y:o:v')
  full_table = False
  verbose = False
  outfile = None

  # Initialisiere Monat und Jahr von aktuellem Datum
  today = datetime.datetime.today().date()
  monat = today.month
  jahr = today.year
  log.debug('Set default date: %02i/%04i' % (monat, jahr))

  # Parse command-line options
  #{{{
  for opt, val in opts:
    if '-m' == opt: monat = int(val)
    elif '-y' == opt: jahr = int(val)
    elif '-v' == opt: verbose = True
    elif '-o' == opt: outfile = val
    elif '-f' == opt: full_table = True
    elif '-h' == opt:
      print '''Usage: %s [OPT] FILE

Available flags for OPT:
  -m NUM  Initialize default month with NUM.
  -y NUM  Initialize default year with NUM.
  -o FILE Write reults into FILE.
  -v      Print verbose optimization summary.
  -h      Print this message and terminate.
''' % os.path.basename(sys.argv[0])
      sys.exit(0)
  #}}}

  if 1 != len(args):
    log.error('Invalid usage! See `%s -h\' for help.' % os.path.basename(sys.argv[0]))
    sys.exit(-1)
  else: fname = args[0]

  if verbose: log.getLogger().setLevel(log.INFO)
  # log.getLogger().setName(fname)

  log.info('regulatory constraints:')
  log.info('  max-total(-dr): %s' % config.max_anwesenheit)
  log.info('  max-total(+dr): %s' % config.max_dienstreise)
  log.info('  min-break: %s' % config.min_erholung)
  log.info('  min-from: %s' % config.min_von_anwesend)
  log.info('  max-till: %s' % config.max_bis_anwesend)

  data = readFile(fname, jahr, monat)
  normalizeData(data)
  calculateWorkTimeRegulations(data)
  data['i.O.'] = checkWorkingTimes(data)[0]
  calculateMinMaxOfWork(data)
  
  is_solvable = checkSolvability(data)
  log.info('summary:')
  log.info('  flexi-time -> available: %s, required: %s' % (data['_cappa_'].sum(), data['_excess_'].sum()))
  assert is_solvable, 'Cannot find solution within current constraints!'

  adjustTimesToRegulations(data)
  calculateWorkTimeRegulations(data, '_new')
  formatColumns(data)
    
  data['_new_i.O._'] = checkWorkingTimes(data, '_new')[0]
  log.info('  old -> total: %s, #i.O.: %i' % (data['_total_'].sum(), data['i.O.'].sum()))
  log.info('  new -> total: %s, #i.O.: %i' % (data['_new_total_'].sum(), data['_new_i.O._'].sum()))
  log.info('Rows that initially were `n.i.O.\' are marked with `x\'.')
  assert data['_new_i.O._'].sum() == len(data), 'There are some rows remaining `n.i.O.\'!'

  if outfile is not None:
    if full_table: columns = data.columns
    else: columns = ['_wday_', 'tag', 'monat', 'jahr', '_new_from_', '_new_till_', 'flags']
    log.info('Writing results into to file `%s\'...' % outfile)
    data[columns].to_csv(outfile, index = False)
  else:
    for index, x in data.iterrows():
      if not verbose: info = ''
      else: info = '(total: %s, break: %s, adjust: %s)' % (x['_new_total_'], x['_new_break_'], x['_adjust_'])

      print ' [%s] %s %02i.%02i.%04i   %s -- %s %s' % (
        # ' ' if x['i.O.'] else '>',
        flags2str(x['_flags_'], extra = [
          'w' if x['_from_'].weekday() in [5,6] else '-',
          '-' if x['i.O.'] else 'x',
          'b' if x['_break_'] < config.min_erholung else '-',
          'e' if x['_total_'] > x['_max_'] else '-'
          ]),
        x['_wday_'],
        x['tag'], x['monat'], x['jahr'],
        x['_new_from_'], x['_new_till_'],
        info
        )
  assert data['_total_'].sum() == data['_new_total_'].sum(), 'Invalid solution: Total sums do not match!'
  sys.exit(0)
  #}}}
