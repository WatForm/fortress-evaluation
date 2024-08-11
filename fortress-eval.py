"""
    Using the testrunner evaluation script to call
    the 'fortress' command with multiple values for the options iterating through filenames
    listed in an input file.
    Output is tallied to a CSV file.

    The steps are:
    1) Set a bunch of options, including how to interpret regular and timeout outputs
    2) Create a CSVTestRunner and execute its .run method.
"""

import logging
import subprocess
import psutil
import shutil

import testrunner.testrunner as tr
import testrunner.util as util

# --- main options that change

# Timeout in seconds
TIMEOUT: int = 1 * 60  # 5 mins

# how many times do we want to run each command?
ITERATIONS = 1

filename_suffix = "-datatypes-cvc5-z3-nday-mac"

# The command to run
# You may want a java command to set memory appropriately
# I chose a large timeout so the test harness checks the timeout, not Fortress
# the options that will be filled in with values are {compiler} and {model}
def command(fortress_bin):
    return f'{fortress_bin} -t 999999 --solver {{solver}} --compiler {{compiler}} {{model}}'

compiler: tr.Option = tr.Option('compiler', [
    "Standard",
    "DatatypeWithRangeEUF",
    "DatatypeNoRangeEUF",
    "DatatypeWithRangeNoEUF",
    "DatatypeNoRangeNoEUF",
])

solver: tr.Option = tr.Option('solver', [
    "Z3NonIncCli",
    "CVC5Cli"
])


# ------ below this line is unlikely to change

# Location of fortress binary
FORTRESS="../fortress/cli/target/universal/stage/bin/fortress"

# Values to fill in for the {model} option
# In this case, we will read the filenames for all .smttc models in the smttc directory
model: tr.Option = tr.FilesOption('model', "smttc", file_filter=lambda fname: fname.endswith(".smttc"))

# The file to write output to
def output_file_name(filename_suffix): 
    return f'{util.now_string()}{filename_suffix}-results.csv'

# To resume in the middle of an execution
SKIP = 0  # number of iterations to skip

FORCE_HEADER = False # rewrite the csv header



# These are the string names of the fields that we want to determine the values
# of from the results of the command
# not needed?
# result_fields = ['return_code', 'time_elapsed', 'satisfiability']

# Fill in result fields when the process completes
# opts are the options we outlined above
# result is what the subprocess sends back
# time_elapsed comes from the timer
# returns a dictionary with values for results_fields above
def result_values(opts: tr.OptionDict, result: subprocess.CompletedProcess, time_elapsed: float) -> tr.OptionDict:
    # when the result has an error, put something special in the logging output
    if result.returncode != 0:
        logging.error('------OUTPUT------\n' + result.stdout + '------STDERR-----\n' + result.stderr +"------------")

    # interpret the satisfiability output
    # this is standard stuff so it's in a util function
    satisfiability: str = util.satisfiability_of_output(result.stdout)
    
    results: tr.OptionDict = {
        # dictionary keys must match result_fields above?
        'return_code': result.returncode,
        'time_elapsed': time_elapsed,
        'satisfiability': satisfiability
    }

    # Ensure no active child processes
    util.kill_solvers()
    return results

# Fill in result fields when the process times out
# same arguments as above except for timeout
# returns a dictionary with values for results_fields above
def timeout_values(opts: tr.OptionDict, result: subprocess.TimeoutExpired) -> tr.OptionDict:
    logging.info('Timed out.')
    results: tr.OptionDict = {
        'return_code': 999,
        'time_elapsed': -1,  # the actual value for the timeout limit was an option input
        'satisfiability': 'UNKNOWN',
    }
    # Ensure no active child processes; Z3 does not always quit when
    # parent process timeouts
    util.kill_solvers()
    return results

result_fields = ['return_code', 'time_elapsed', 'satisfiability']
ignore_fields = []

# option with only one value, but it gets it printed in the output
# it is not used in the command
timeout: tr.Option = tr.Option('timeout', [TIMEOUT])

# Level of debug
util.setup_logging_debug(filename_suffix)
# or:
#util.setup_logging_default()

# This is the call to the CSVTestRunner to execute the runs
# Remember to list the options here
with open(output_file_name(filename_suffix), 'w') as output_file:
    runner = tr.CSVTestRunner(
        command(FORTRESS),  # command string with blanks to fill in
        model, # option
        compiler, # option
        solver, # option
        timeout, # unused option but gets it included in a table of the output
        timeout=TIMEOUT,
        output_file=output_file,
        fields_from_result=result_values, # how to interpret results of run
        fields_from_timeout=timeout_values,   # how to interpret timeouts
        # output CSV file contains all non_ignored fields
        result_fields = result_fields,
        ignore_fields=ignore_fields,
    )  
    runner.run(ITERATIONS, SKIP, FORCE_HEADER)
