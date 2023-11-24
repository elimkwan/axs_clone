#!/usr/bin/env python3

""" This entry knows how to download a file from a given URL.

    # create a recipe entry:
            axs work_collection , attached_entry examplepage_recipe , plant url http://example.com/  entry_name examplepage_downloaded  file_name example.html  _parent_entries --,:=AS^IS:^:byname:downloader , save

    # activate the recipe, performing the actual downloading:
            axs byname examplepage_recipe , download

    # get the path to the downloaded file:
            axs byname examplepage_downloaded , get_path

    # clean up:
            axs byname examplepage_downloaded , remove
            axs byname examplepage_recipe , remove

"""

import logging


def get_split_file_path(url=None, file_path=None):
    import os

    if file_path:                           # prefer if given
        if type(file_path) == list:
            return file_path
        else:
            return file_path.split(os.sep)
    else:                                   # infer from url otherwise
        return [ os.path.basename(url) ]


def get_uncompressed_split_file_path(split_file_path, uncompress_format):

    if uncompress_format:
        return split_file_path[0:-1] + [ split_file_path[-1].rsplit('.', 1)[0] ]    # trim one .extension off the last syllable
    else:
        return split_file_path


def download(url, file_name=None, split_file_path=None, md5=None, downloading_tool_entry=None, uncompress_format=None, tags=None, extra_tags=None, entry_name=None, __entry__=None, __record_entry__=None):
    """Create a new entry and download the url into it

Usage examples:
    # Manual downloading into a new entry:
            axs byname downloader , download 'https://example.com/' example.html --tags,=example

    # Replay of the same command at a later time, stored in a different entry:
            axs byquery downloaded,file_path=example.html , get _replay --entry_name=replay_downloading_example.html

    # Resulting entry path (counter-intuitively) :
            axs byquery downloaded,file_path=example.html , get_path ''

    # Downloaded file path:
            axs byquery downloaded,file_path=example.html , get_path

    # Reaching to the original tool used for downloading:
            axs byquery downloaded,file_path=example.html , get downloading_tool_entry , get tool_path

    # Clean up:
            axs byquery downloaded,file_path=example.html , remove

    # Using a generic rule:
            axs byquery downloaded,url=http://example.com,file_path=example.html

    # Downloading from GoogleDrive (needs a specialized tool):
            axs byname downloader , download --downloading_tool_query+=_from_google_drive --url=https://drive.google.com/uc?id=1XRfiA8wtZEo6SekkJppcnfEr4ghQAS4g --file_path=hello2.text
    """

    __record_entry__.pluck( "entry_name" )

    __record_entry__["tags"] = list(set( (tags or []) + extra_tags ))
    __record_entry__.pluck( "extra_tags" )

    __record_entry__.save( entry_name )

    record_entry_path   = __record_entry__.get_path( "" )
    target_path         = __record_entry__.get_path(split_file_path)


    logging.warning(f"The resolved downloading_tool_entry '{downloading_tool_entry.get_name()}' located at '{downloading_tool_entry.get_path()}' uses the shell tool '{downloading_tool_entry['tool_path']}'")
    retval = downloading_tool_entry.call('run', [], {"url": url, "target_path": target_path, "record_entry_path": record_entry_path})
    if retval == 0:
        if md5 is not None:
            md5_tool_entry = __entry__['md5_tool_entry']
            logging.warning(f"The resolved md5_tool_entry '{md5_tool_entry.get_name()}' located at '{md5_tool_entry.get_path()}' uses the shell tool '{md5_tool_entry['tool_path']}'")
            computed_md5 = md5_tool_entry.call('run', [], {"file_path": target_path})
            if computed_md5 != md5:
                logging.error(f"The computed md5 sum '{computed_md5}' is different from the expected '{md5}', bailing out")
                __record_entry__.remove()
                return None
            else:
                __record_entry__['md5_tool_entry'] = md5_tool_entry
                logging.warning(f"The computed md5 sum '{computed_md5}' matched the expected one.")

        if uncompress_format:
            __entry__['uncompress_format'] = uncompress_format  # FIXME: this should not need to be explicitly mentioned, it should be automagically transferred over
            uncompress_tool_entry = __entry__['uncompress_tool_entry']
            __entry__['uncompress_format'] = ""                 # NB: avoid screwing up parallel invocations of the same function in context of its entry
            if uncompress_tool_entry:
                logging.warning(f"Uncompression from {uncompress_format} requested")
                retval = uncompress_tool_entry.call('run', [], {"target_path": target_path, "in_dir": record_entry_path})
                if retval == 0:
                    __record_entry__['uncompress_tool_entry'] = uncompress_tool_entry
                else:
                    logging.error(f"could not uncompress {target_path}, bailing out")
                    __record_entry__.remove()
                    return None
            else:
                __record_entry__['uncompression'] = 'FAILED'
                logging.error(f"Uncompression from {uncompress_format} requested, but failed to detect such tool")
        else:
            logging.warning(f"Uncompression not requested")

        __record_entry__.save()
        return __record_entry__
    else:
        logging.error(f"A problem occured when trying to download '{url}' into '{target_path}', bailing out")
        __record_entry__.remove()
        return None
