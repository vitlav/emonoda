import sys
import os
import itertools
import operator
import argparse
import datetime

from ..core import tfile
from ..core import cli
from ..core import fmt

from ..plugins.clients import NoSuchTorrentError

from . import init
from . import get_configured_client


# =====
def format_size_pretty(torrent):
    return fmt.format_size(torrent.get_size())


def format_announce(torrent):
    return (torrent.get_announce() or "")


def format_announce_list(torrent):
    return list(itertools.chain.from_iterable(torrent.get_announce_list()))


def format_announce_list_pretty(torrent):
    return " ".join(format_announce_list(torrent))


def format_creation_date(torrent):
    return (torrent.get_creation_date() or "")


def format_creation_date_pretty(torrent):
    date = torrent.get_creation_date()
    return str(datetime.datetime.utcfromtimestamp(date) if date is not None else "")


def format_created_by(torrent):
    return (torrent.get_created_by() or "")


def format_provides(torrent):
    return sorted(torrent.get_files())


def format_is_private(torrent):
    return str(int(torrent.is_private()))


def format_is_private_pretty(torrent):
    return ("yes" if torrent.is_private() else "no")


def format_comment(torrent):
    return (torrent.get_comment() or "")


def _format_client_method(torrent, client, method_name):
    assert client is not None, "Required a client"
    try:
        return getattr(client, method_name)(torrent)
    except NoSuchTorrentError:
        return ""


def format_client_path(torrent, client):
    return _format_client_method(torrent, client, "get_full_path")


def format_client_prefix(torrent, client):
    return _format_client_method(torrent, client, "get_data_prefix")


def _make_formatted_tree(files, depth=0, prefix="    "):
    text = ""
    for (name, sub) in sorted(files.items(), key=operator.itemgetter(0)):
        text += prefix + "*   " * depth + name + "\n"
        text += _make_formatted_tree(sub, depth + 1)
    return text


def format_files_tree(torrent):
    tree = {}
    for path in torrent.get_files():
        parts = os.path.normpath(path).split(os.path.sep)
        local = tree
        for (index, part) in enumerate(parts):
            if index != 0 and len(part) == 0:
                continue
            local.setdefault(part, {})
            local = local[part]
    return _make_formatted_tree(tree)


def print_pretty_meta(torrent, client, log):
    log.print("{blue}Path:{reset}          %s" % (torrent.get_path()))
    log.print("{blue}Name:{reset}          %s" % (torrent.get_name()))
    log.print("{blue}Hash:{reset}          %s" % (torrent.get_hash()))
    log.print("{blue}Size:{reset}          %s" % (format_size_pretty(torrent)))
    log.print("{blue}Announce:{reset}      %s" % (format_announce(torrent)))
    log.print("{blue}Announce list:{reset} %s" % (format_announce_list_pretty(torrent)))
    log.print("{blue}Creation date:{reset} %s" % (format_creation_date_pretty(torrent)))
    log.print("{blue}Created by:{reset}    %s" % (format_created_by(torrent)))
    log.print("{blue}Private:{reset}       %s" % (format_is_private_pretty(torrent)))
    log.print("{blue}Comment:{reset}       %s" % (format_comment(torrent)))
    if client is not None:
        log.print("{blue}Client path:{reset}   %s" % (format_client_path(torrent, client)))
    if torrent.is_single_file():
        log.print("{blue}Provides:{reset}      %s" % (tuple(torrent.get_files())[0]))
    else:
        log.print("{blue}Provides:{reset}\n%s" % (format_files_tree(torrent)))


# ===== Main =====
def main():  # pylint: disable=too-many-locals
    actions = [
        (option, option[2:].replace("-", "_"), method)
        for (option, method) in (
            ("--path",                 tfile.Torrent.get_path),
            ("--name",                 tfile.Torrent.get_name),
            ("--hash",                 tfile.Torrent.get_hash),
            ("--comment",              format_comment),
            ("--size",                 tfile.Torrent.get_size),
            ("--size-pretty",          format_size_pretty),
            ("--announce",             format_announce),
            ("--announce-list",        format_announce_list),
            ("--announce-list-pretty", format_announce_list_pretty),
            ("--creation-date",        format_creation_date),
            ("--creation-date-pretty", format_creation_date_pretty),
            ("--created-by",           format_created_by),
            ("--provides",             format_provides),
            ("--is-private",           format_is_private),
            ("--is-private-pretty",    format_is_private_pretty),
            ("--client-path",          lambda torrent: format_client_path(torrent, client)),
            ("--client-prefix",        lambda torrent: format_client_prefix(torrent, client)),
            ("--make-magnet",          lambda torrent: torrent.make_magnet(options.magnet_fields)),
        )
    ]

    (parent_parser, argv, config) = init()
    args_parser = argparse.ArgumentParser(
        prog="rtfile",
        description="Show the metadata of torrent file",
        parents=[parent_parser],
    )
    for (option, dest, _) in actions:
        args_parser.add_argument(option, dest=dest, action="store_true")
    args_parser.add_argument("--without-headers", action="store_true")
    args_parser.add_argument("--magnet-fields", nargs="+", default=(),  metavar="<fields>", choices=tfile.ALL_MAGNET_FIELDS)
    args_parser.add_argument("torrents", type=(lambda path: tfile.Torrent(path=path)), nargs="+", metavar="<path>")
    options = args_parser.parse_args(argv[1:])

    client = get_configured_client(config)
    log = cli.Log(config.core.use_colors, config.core.force_colors, sys.stdout)

    to_print = [
        (option[2:], method)
        for (option, dest, method) in actions
        if getattr(options, dest)
    ]

    for torrent in options.torrents:
        if len(to_print) == 0:
            print_pretty_meta(torrent, client, log)
        else:
            for (header, method) in to_print:
                prefix = ("" if options.without_headers else "{blue}%s:{reset} " % (header))
                retval = method(torrent)
                if isinstance(retval, (list, tuple)):
                    for item in retval:
                        log.print(prefix + str(item))
                else:
                    log.print(prefix + str(retval))
        if len(options.torrents) > 1:
            log.print()


if __name__ == "__main__":
    main()
