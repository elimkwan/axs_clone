#!/usr/bin/env python3

import logging
import re

import function_access
from param_source import ParamSource
from copy import copy

class Runnable(ParamSource):
    """An object of Runnable class is a non-persistent container of parameters (inherited) and code (own)
        that may optionally also have a parent object of the same class.

        It can run an own or inherited action using own or inherited parameters.
    """

    def __init__(self, own_functions=None, kernel=None, **kwargs):
        "Accept setting own_functions and kernel in addition to parent's parameters"

        self.own_functions_cache    = own_functions
        self.kernel                 = kernel
        super().__init__(**kwargs)
        logging.debug(f"[{self.get_name()}] Initializing the Runnable with {self.list_own_functions() if self.own_functions_cache else 'no'} pre-loaded functions and kernel={self.kernel}")


    def get_kernel(self):
        return self.kernel


    def own_functions(self):
        """Placeholder for lazy-loading code in subclasses that support it.

            Note the convention:
                stored None means "not loaded yet", as in "cached value missing"
                whereas stored False means "this object has no code to load", "nothing to see here".
        """

        return self.own_functions_cache or False


    def list_own_functions(self):
        """A lightweight method to list all own methods of an entry

Usage examples :
                axs byname be_like , list_own_functions
                axs byname shell , list_own_functions
        """
        own_functions = self.own_functions()
        return function_access.list_function_names(own_functions) if own_functions else []


    def reach_function(self, function_name, _ancestry_path):
        "Recursively find a Runnable's function - either its own or belonging to the nearest parent."

        _ancestry_path.append( self.get_name() )

        own_functions   = self.own_functions()

        if hasattr(own_functions, function_name):
            return getattr(own_functions, function_name)
        else:
            found_function = None
            for parent_object in self.parents_loaded():
                found_function = parent_object.reach_function(function_name, _ancestry_path)
                if found_function:
                    break
                else:
                    _ancestry_path.pop()

            return found_function


    def reach_action(self, action_name, _ancestry_path=None):
        "First try to reach for a Runnable's function (externally loaded code), if unavailable - try Runnable's method instead."

        logging.debug(f"[{self.get_name()}] reach_action({action_name}) ...")
        if _ancestry_path == None:  # if we have to initialize it internally, the value will be lost to the caller
            _ancestry_path = []

        function_object = self.reach_function( action_name, _ancestry_path )
        if function_object:
            logging.debug(f"[{self.get_name()}] reach_action({action_name}) was found as a function")

            return function_object
        elif hasattr(self, action_name):
            logging.debug(f"[{self.get_name()}] reach_action({action_name}) was found as a class method")

            _ancestry_path.clear()  # empty the specific list given to us - a form of feedback
            return getattr(self, action_name)
        else:
            raise NameError( "could not find the action '{}' neither along the ancestry path '{}' nor in the {} class".
                              format(action_name, ' --> '.join(_ancestry_path),  self.__class__.__name__) )


    def can(self, action_name):
        "Returns whether object has such an action or not (a boolean)"

        try:
            self.reach_action(action_name)
            return True
        except NameError:
            return False


    def help(self, action_name=None):
        """Reach for a Runnable's function or method and examine its DocString and calling signature.

Usage examples :
                axs help
                axs help help
                axs help substitute
                axs byname be_like , help
                axs byname dont_be_like , help meme
                axs byname dont_be_like , help get
        """

        help_buffer = []
        common_format = "{:15s}: {}"
        entry_class = self.__class__

        help_buffer.append( common_format.format( entry_class.__name__+' class', entry_class.__doc__ ))
        help_buffer.append( common_format.format( 'Class methods', function_access.list_function_names(entry_class) ))

        help_buffer.append('')
        help_buffer.append( common_format.format( 'Specific '+entry_class.__name__, self.get_name() ))

        if action_name:
            try:
                ancestry_path   = []
                action_object   = self.reach_action(action_name, _ancestry_path=ancestry_path)

                required_arg_names, optional_arg_names, action_defaults, varargs, varkw = function_access.expected_call_structure( action_object )

                if varargs:
                    required_arg_names.append( '*'+varargs )

                signature = ', '.join(required_arg_names + [optional_arg_names[i]+'='+str(action_defaults[i]) for i in range(len(optional_arg_names))] )

                if varkw:
                    help_buffer.append( """NB: this action cannot be called via our calling mechanism,
                              because it makes use of variable keywords (**)""" )

                if ancestry_path:
                    help_buffer.append( common_format.format('Function', action_name ))
                    help_buffer.append( common_format.format('Ancestry path', ' --> '.join(ancestry_path) ))
                else:
                    help_buffer.append( common_format.format( 'Method', action_name ))
                    help_buffer.append( common_format.format( 'Declared in', action_object.__module__+'.py' ))

                help_buffer.append( common_format.format( 'Signature', action_name+'('+signature+')' ))
                help_buffer.append( common_format.format( 'DocString', action_object.__doc__ ))
            except Exception as e:
                logging.error( str(e) )
        else:
            own_functions   = self.own_functions()     # the entry may not contain any code...
            if own_functions:
                doc_string      = own_functions.__doc__     # the module may not contain any DocString...
                help_buffer.append( common_format.format('Description', doc_string))
                help_buffer.append( common_format.format('OwnFunctions', self.list_own_functions()))
            else:
                parents_names   = self.get_parents_names()
                parents_may_know = ", but you may want to check its parents: "+parents_names if parents_names else ""
                help_buffer.append("This Runnable has no loadable functions" + parents_may_know)

        return '\n'.join(help_buffer)


    def call(self, action_name, pos_params=None, override_dict=None, pos_preps=None):
        """Call a given function or method of a given entry and feed it
            with arguments from the current object optionally overridden by a given dictionary.

            The action can have a mix of positional args and named args with optional defaults.
        """

        logging.debug(f'[{self.get_name()}]  calling action {action_name} with "{pos_params}" ...')

        if override_dict:
            self.own_data().update( override_dict )

        pos_params = pos_params or []

        if type(pos_params)!=list:      # simplifies syntax for single positional parameter actions
            pos_params = [ pos_params ]

        if pos_preps:
            for idx in range(len(pos_params)):
                pos_params[idx] = self.dispatch_call( pos_preps[idx], pos_params[idx])      # NB: dispatched calls do not have override_dict

        action_object   = self.reach_action(action_name)
        result          = function_access.feed(action_object, pos_params, self)

        logging.debug(f'[{self.get_name()}]  called action {action_name} with "{pos_params}", got "{result}"')

        return result


    def dispatch_call(self, action_name, pos_params=None):
        """Preprocess args by running a specific action over them
        """

        if not action_name:
            return pos_params
        else:
            action_name = action_name[1:]
            if action_name[0]=='^':
                return self.call(action_name[1:], pos_params)
            else:
                return self.get_kernel().call(action_name, pos_params)


    def calls_over_struct(self, input_structure):
        """Walk the structure and perform all nested calls in it.
        """

        def scalar_call(scalar_input):
            if scalar_input.startswith('^'):
                matched = re.match(r'^(\^{1,2}\w+)(([:,\ /;=]).*)?$', scalar_input)
                if matched:
                    delimiter   = matched.group(3)
                    action_name = matched.group(1)
                    pos_params  = [ function_access.to_num_or_not_to_num(el) for el in matched.group(2).split(delimiter)[1:] ] if delimiter else []
                    return self.dispatch_call(action_name, pos_params)

            return scalar_input

        # Structural recursion:
        if type(input_structure)==list:
            return [self.calls_over_struct(e) for e in input_structure]                         # all list elements are substituted
        elif type(input_structure)==dict:
            return { k : self.calls_over_struct(input_structure[k]) for k in input_structure }  # only values are substituted
        elif type(input_structure)==str:
            return scalar_call(input_structure)                                                 # ground step
        else:
            return input_structure                                                              # basement step


    def execute(self, pipeline):
        """Execute a parsed pipeline (a chain of calls that starts from the kernel object).
            Whenever a result returned by a function is NOT an Runnable, the execution resets back to the kernel object.

Usage examples :
                axs si: byname sysinfo , os: dig si.osname , ar: dig si.arch , substitute '#{os}#--#{ar}#'
                axs si: byname sysinfo , os: dig si.osname , ar: dig si.arch , runtime_entry , pluck si , save
        """

        ak = self.get_kernel()

        from stored_entry import Entry  # FIXME: unwanted circular reference!
        runtime_entry = Entry(entry_path='runtime_entry', own_data={})

        result = None
        for i, call_params in enumerate(pipeline):
            entry = result if hasattr(result, 'call') else ak

            entry.runtime_entry( runtime_entry )

            label = call_params.pop(4) if len(call_params)>4 else None

            result = entry.call(*call_params)
            entry.runtime_entry()

            if label:
                runtime_entry[label] = result
        return result


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(funcName)s %(message)s")

    print('-'*40 + ' Creating a hierarchy of Runnables: ' + '-'*40)

    from argparse import Namespace

    def plus_one(number):
        "Adds 1 to the argument"
        return number+1

    def trice(number):
        "Multiplies the argument by 3"
        return number*3

    granddad    = Runnable(name='granddad', own_functions=Namespace( add_one=plus_one, subtract_one=(lambda x: x-1)         ) )
    dad         = Runnable(name='dad',      own_functions=Namespace( double=(lambda x: x*2), triple=trice                   ), parent_objects=[granddad])
    mum         = Runnable(name='mum',      own_functions=Namespace( cube=(lambda x: x*x*x)                                 ) )
    child       = Runnable(name='child',    own_functions=Namespace( square=(lambda x: x*x)                                 ), parent_objects=[dad, mum])

    assert sorted(granddad.list_own_functions())==['add_one', 'subtract_one'], "granddad's own functions"
    assert sorted(dad.list_own_functions())==['double', 'triple'], "dad's own functions"

    print('-'*40 + ' Testing reach_action(): ' + '-'*40)

    assert sorted(mum.reach_action('list_own_functions')())==['cube'], "mum's own functions listed via reach_action"
    assert sorted(child.reach_action('list_own_functions')())==['square'], "child's own functionss listed via reach_action"

    input_arg = 12
    func_applied_to_input_arg = {
        "square": ("child", 144),
        "add_one": ("granddad", 13),
        "double": ("dad", 24),
        "cube": ("mum", 1728)
    }
    for func_name in func_applied_to_input_arg:
        owner_entry_name, func_value = func_applied_to_input_arg[func_name]
        path_to_function = []
        assert child.reach_action(func_name, path_to_function)(input_arg)==func_value, f"{owner_entry_name}'s function '{func_name}'"

    print('-'*40 + ' Testing help(): ' + '-'*40)

    child.help('triple')
    print("")
    child.help('add_one')

    print('-'*40 + ' Testing call(): ' + '-'*40)

    assert child.call('double', [20])==40, "call() for dad's function, positional args"
    assert child.call('triple', override_dict={'number': 11})==33, "call() for dad's function, named args"

    dad['x']=100

    assert child.call('subtract_one')==99, "call() for granddad's function, inherit arg from dad"
    assert child.call('square')==10000, "call() for child's function, inherit arg from dad"
    assert child.call('get', ['x'])==100, "call() for class method, inherit arg from dad"

    try:
        print(f"child.call('nonexistent')={child.call('nonexistent')}\n")
    except NameError as e:
        assert str(e)=="could not find the action 'nonexistent' neither along the ancestry path 'child' nor in the Runnable class"
