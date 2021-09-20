#!/usr/bin/env python3

""" This entry knows how to make other entries.
"""

import logging
import os

def walk(__entry__):
    """An internal recursive generator not to be called directly
    """

    ak = __entry__.get_kernel()
    assert ak != None, "__entry__'s kernel should be defined"
    collection_own_name = __entry__.get_name()


    logging.debug(f"collection({collection_own_name}): yielding the collection itself")
    yield __entry__

    logging.debug(f"collection({collection_own_name}): walking contained_entries:")
    contained_entries = __entry__.get('contained_entries', {})
    for entry_name in contained_entries:
        relative_entry_path = contained_entries[entry_name]
        logging.debug(f"collection({collection_own_name}): mapping {entry_name} to relative_entry_path={relative_entry_path}")

        contained_entry = ak.bypath(path=__entry__.get_path(relative_entry_path), name=entry_name, container=__entry__)

        # Have to resort to duck typing to avoid triggering dependencies by testing if contained_entry.can('walk'):
        if 'contained_entries' in contained_entry.own_data():
            logging.debug(f"collection({collection_own_name}): recursively walking collection {entry_name}...")
            yield from walk(contained_entry)
        else:
            logging.debug(f"collection({collection_own_name}): yielding non-collection {entry_name}")
            yield contained_entry


def new(name, __entry__):
    """Create a new entry with the given name and attach it to this collection

Usage examples :
                axs work_collection , new unique_entry_name , plant hello world , save
    """

    new_entry = __entry__.get_kernel().bypath( __entry__.get_path( name ), name=name ).attach( __entry__ ).save()

    return new_entry


def byname(entry_name, __entry__):
    """Fetch an entry by name
    """

    for candidate_entry in walk(__entry__):
        if candidate_entry.get_name() == entry_name:
            return candidate_entry
    return None


def byquery(query, failover_pipeline=None, parent_recursion=False, __entry__=None):
    """Fetch an entry by query.
        If the query returns nothing on the first pass, but failover_pipeline or matching producer_rules are defined,
        run the failover_pipeline or the matching producer_rule and return its output.

Usage examples :
                axs byquery python_package,package_name=numpy , get_path
                axs byquery python_package,package_name=numpy,package_version=1.16.4 , get_metadata --header_name=Version
    """
    assert __entry__ != None, "__entry__ should be defined"

    def create_filter(key_path, fun, against=None):
        """ Finally, a useful real-life example of closures:
            captures both *fun* and *against* in the internal function.
        """
        split_key_path = key_path.split('.')    # computed only once during closure creation

        def filter_closure(entry):
            return fun(entry.dig(split_key_path, safe=True, parent_recursion=parent_recursion), against)    # computed every time during filter application

        return filter_closure


    import re
    from function_access import to_num_or_not_to_num

    conditions      = query.split(',')
    filter_list     = []
    posi_tag_set    = set()
    posi_val_dict   = {}

    # parsing the query:
    for condition in conditions:
        binary_op_match = re.match('([\w\.]*\w)(=|==|!=|<>|<|>|<=|>=|:|!:)(-?[\w\.]+)$', condition)
        if binary_op_match:
            key_path    = binary_op_match.group(1)
            binary_op   = binary_op_match.group(2)
            test_val    = to_num_or_not_to_num(binary_op_match.group(3))
            if binary_op in ('=', '=='):
                posi_val_dict[key_path] = test_val
                filter_list.append( create_filter(key_path, lambda x, y : x==y, test_val) )
            elif binary_op in ('!=', '<>'):
                filter_list.append( create_filter(key_path, lambda x, y : x!=y, test_val) )
            elif binary_op=='<':
                filter_list.append( create_filter(key_path, lambda x, y : x!=None and x<y, test_val) )
            elif binary_op=='>':
                filter_list.append( create_filter(key_path, lambda x, y : x!=None and x>y, test_val) )
            elif binary_op=='<=':
                filter_list.append( create_filter(key_path, lambda x, y : x!=None and x<=y, test_val) )
            elif binary_op=='>=':
                filter_list.append( create_filter(key_path, lambda x, y : x!=None and x>=y, test_val) )
            elif binary_op==':':
                filter_list.append( create_filter(key_path, lambda x, y : type(x)==list and y in x, test_val) )
            elif binary_op=='!:':
                filter_list.append( create_filter(key_path, lambda x, y : type(x)==list and y not in x, test_val) )
        else:
            unary_op_match = re.match('([\w\.]*\w)(\.|\?|\+|-)$', condition)
            if unary_op_match:
                key_path    = unary_op_match.group(1)
                unary_op    = unary_op_match.group(2)
                if unary_op=='.':               # path exists
                    filter_list.append( create_filter(key_path, lambda x, y: x!=None) )
                elif unary_op in ('?', '+'):    # computes to True
                    filter_list.append( create_filter(key_path, lambda x, y: bool(x)) )
                elif unary_op=='-':             # computes to False
                    filter_list.append( create_filter(key_path, lambda x, y: not bool(x)) )
            else:
                tag_match = re.match('([!^-])?(\w+)$', condition)
                if tag_match:
                    key_path    = 'tags'
                    test_val    = tag_match.group(2)
                    if tag_match.group(1):
                        filter_list.append( create_filter(key_path, lambda x, y : type(x)!=list or y not in x, test_val) )
                    else:
                        filter_list.append( create_filter(key_path, lambda x, y : type(x)==list and y in x, test_val) )
                        posi_tag_set.add( test_val )
                else:
                    raise(SyntaxError("Could not parse the condition '{}'".format(condition)))


    # applying the query as a filter:
    for candidate_entry in walk(__entry__):
        candidate_still_ok = True
        for filter_function in filter_list:
            if not filter_function(candidate_entry):
                candidate_still_ok = False
                break
        if candidate_still_ok:
            return candidate_entry


    if failover_pipeline:
        logging.debug(f"[{__entry__.get_name()}] byquery({query}) did not find anything, trying to install {failover_pipeline}")
        return __entry__.execute(failover_pipeline)
    elif len(posi_tag_set):
        logging.debug(f"[{__entry__.get_name()}] byquery({query}) did not find anything, but there are tags: {posi_tag_set} , trying to find a producer...")

        for candidate_producer_entry in walk(__entry__):
            producer_rules = candidate_producer_entry.get('producer_rules', {})
            for producer_method in producer_rules.keys():
                producer_tags_set = set(producer_rules[producer_method])
                if producer_tags_set.issubset(posi_tag_set):
                    print(f"Producer entry {candidate_producer_entry.get_name()} advertises method {producer_method} with matching tags {producer_tags_set} that may work with {posi_val_dict}")
                    new_entry = candidate_producer_entry.call(producer_method, [], posi_val_dict)
                    if new_entry:
                        print("It worked!")
                        return new_entry
                    else:
                        print("It didn't work, but maybe there is another method...")

    else:
        logging.debug(f"[{__entry__.get_name()}] byquery({query}) did not find anything, and no failover_pipeline defined => returning None")
        return None


def add_entry_path(new_entry_path, new_entry_name=None, __entry__=None):
    """Add a new entry to the collection given the path
    """
    assert __entry__ != None, "__entry__ should be defined"

    trimmed_new_entry_path  = __entry__.trim_path( new_entry_path )
    new_entry_name          = new_entry_name or os.path.basename( trimmed_new_entry_path )
    existing_path           = __entry__.dig(['contained_entries', new_entry_name], safe=True)

    if existing_path:
        raise(KeyError(f"There was already another entry named {new_entry_name} with path {existing_path}, remove it first"))
    else:
        __entry__.plant(['contained_entries', new_entry_name], trimmed_new_entry_path)
        return __entry__.save()


def remove_entry_name(old_entry_name, __entry__):

    contained_entries       = __entry__.pluck(['contained_entries', old_entry_name])
    return __entry__.save()



if __name__ == '__main__':

    print("Unfortunately this entry cannot be tested separately from the framework")

