#!/usr/bin/env python3

""" A simple CommandLine API for this framework.
"""

import json
import logging
import re
import sys

from function_access import to_num_or_not_to_num

def cli_parse(arglist):
    """Parse the command pipeline representing a chain of calls

    The expected format is:
        [<label>:] <action_name> [<pos_param>]* [<opt_param>]* [, <action_name> [<pos_param>]* [<opt_param>]*]*

        Positional parameters can have the following formats:
            ---='{"hello": "world"}'        # parsed JSON
            --,=abc,123,def                 # comma-separated list ["abc", 123, "def"]
            --,                             # empty list
            free_word                       # string or number

        Optional parameters can have the following formats:
            --alpha                         # boolean True
            --beta-                         # boolean False
            --gamma=                        # scalar empty string
            --delta=1234                    # scalar number
            --epsilon=hello                 # scalar string
            --zeta,=tag1,tag2,tag3          # list (can be split on a comma, a colon: or a space )
            --eta.theta                     # dictionary boolean True value
            --iota.kappa-                   # dictionary boolean False value
            --lambda.mu=                    # dictionary empty string value
            --nu.xi=omicron                 # dictionary scalar value (number or string)
            --pi.rho,=tag1,tag2,tag3        # dictionary that contains a list
            ---xyz='[{"pq":"rs"},123]'      # parsed JSON
    """


    pipeline = []
    i = 0

    while i<len(arglist):

        if arglist[i]==',':     # just skip the pipeline link separator
            i += 1

        call_params     = {}
        call_pos_params = []
        curr_link = [ None, call_pos_params, call_params ]
        pipeline.append( curr_link )

        ## Going through the arguments
        while i<len(arglist) and not arglist[i].startswith(','):
            if not arglist[i].startswith('--'):
                matched = re.match(r'^(\^{1,2})(\w+)(([:,\ /;=]).*)?$', arglist[i])   # a nested action
                if matched:
                    delimiter = matched.group(4)
                    call_pos_params.append( [ matched.group(1), matched.group(2), [to_num_or_not_to_num(el) for el in matched.group(3).split(delimiter)[1:] ] if delimiter else [] ] )

                    if curr_link[0]==None:          # no action has been parsed yet
                        curr_link[0] = 'noop'
                elif curr_link[0]==None and len(curr_link)<5 and re.match(r'^(\w*):(?:(\w*):)?$', arglist[i]):  # input and/or output label(s)
                    matched = re.match(r'^(\w*):(?:(\w*):)?$', arglist[i])
                    curr_link.extend( [ matched.group(1), matched.group(2) ] )
                elif curr_link[0]==None and re.match(r'^\w+$', arglist[i]):                             # a normal action
                    curr_link[0] = arglist[i]
                elif curr_link[0]:                                                                      # a positional argument
                    call_pos_params.append( to_num_or_not_to_num(arglist[i]) )
                else:
                    raise(Exception("Parsing error - cannot understand non-option '{}' before an action".format(arglist[i])))

            else:
                matched = re.match(r'^---(([\w\.]*)((\^{1,2})(\w+))?)=(.*)$', arglist[i])               # verbatim JSON value
                if matched:
                    call_param_json     = matched.group(6)
                    call_param_value    = json.loads( call_param_json )
                else:
                    matched = re.match(r'^--(([\w\.]*)((\^{1,2})(\w+))?)([\ ,;:/]{0,2})=(.*)$', arglist[i])     # list or scalar value
                    if matched:
                        delimiters          = list(matched.group(6))
                        call_param_value    = matched.group(7)

                        if len(delimiters)==2:
                            call_param_value    = [ [ to_num_or_not_to_num(elem) for elem in group.split(delimiters[1]) ] for group in call_param_value.split(delimiters[0]) ]
                        elif len(delimiters)==1:
                            call_param_value    =   [ to_num_or_not_to_num(elem) for elem in call_param_value.split(delimiters[0]) ]
                        else:
                            call_param_value    =     to_num_or_not_to_num(call_param_value)
                    else:
                        matched = re.match(r'^--(([\w\.]*)((\^{1,2})(\w+))?)([,+-]?)$', arglist[i])     # empty list or bool value
                        if matched:
                            if matched.group(6) == ',':
                                call_param_value    = []                        # the way to express an empty list
                            else:
                                call_param_value    = matched.group(6) != '-'   # boolean True or False

                if matched:
                    if matched.group(3):    # if there was a nested action
                        call_param_value = [ matched.group(4), matched.group(5), call_param_value ]

                    if matched.group(2):    # if option name was present
                        call_params[matched.group(2)] = call_param_value
                    else:
                        call_pos_params.append( call_param_value )

                else:
                    raise(Exception("Parsing error - cannot understand option '{}'".format(arglist[i])))
            i += 1

    return pipeline


def main():
    #logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(funcName)s %(message)s")   # put this BEFORE IMPORTING the kernel to see logging from the kernel

    from kernel import default_kernel as ak

    pipeline = cli_parse(sys.argv[1:])
    return ak.execute(pipeline)

if __name__ == '__main__':
    print(main())
