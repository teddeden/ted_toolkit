'''tedtoolkit.io.xml - XML import (flattened to list-of-lists) via lxml. No XML *export* is
provided here - only import.

XML's tree shape doesn't map onto a table the way csv/xlsx rows do, so most of this module is a
flattening engine: it turns a repeating "record" element into rows, and turns attributes/nested
elements/repeated children into columns, under a handful of configurable strategies. lxml (not
stdlib xml.etree.ElementTree) was chosen specifically for two things no stdlib parser can do:
`XMLParser(recover=True)` (genuine partial recovery from malformed XML - a strict parser either
parses the whole document or raises, with no partial result) and `iterparse`-based low-memory
streaming. The flattening logic itself is hand-written regardless of parser backend, since no
library flattens arbitrary XML into a table under configurable per-path strategies out of the box.

Guided-function note: xml_import() takes ~20 kwargs (far more than csv_import's ~8 or
xlsx_import's 3). Prompting for every one of them on every call would make the interactive path
unusable, so - consistent with xlsx_import already silently defaulting include_formulas/
override_ro with no prompt at all - only the handful of kwargs that most change what you get
(source, record_path, list_strategy, max_depth, namespace_mode, on_malformed, low_memory,
header_row) are prompted-and-baked; everything else is a silent, fully scriptable kwargs.get()
default. All of it is documented on xml_import()'s docstring either way.
'''

import io
import json
import os
from collections import OrderedDict
from types import SimpleNamespace

import click
from lxml import etree

from tedtoolkit.history import _add_kwarg_to_last_command, _quoted
from tedtoolkit.prompts import ask_yn, _prompt_for_list_arg, _prompt_for_bool_arg
from tedtoolkit.gui.dialogs import g_sel_file, g_sel_folder

# Residual/aggregate serialization formats and list strategies are plain strings by design (kept
# as literal string kwargs, not an enum) so saved scripts read as plain, self-explanatory Python.
RESIDUAL_FORMATS = ('xml', 'json', 'dict')
LIST_STRATEGIES = ('explode', 'aggregate', 'indexed', 'residual')
NAMESPACE_MODES = ('strip', 'prefix', 'keep')
ON_MALFORMED_MODES = ('raise', 'recover', 'skip')
COLUMN_ORDERS = ('discovery', 'alpha', 'stable')

_AUTO_DETECT_SNIFF_LIMIT = 5000  # cap on elements sniffed while auto-detecting record_path


class _FlattenContext:
    '''Accumulates diagnostics across a whole record-set walk: discovered column paths (in
    first-seen order, doubling as column_order='discovery'), paths truncated by max_depth or a
    'residual' list_strategy, and free-text warnings surfaced in the post-import statistics.'''
    def __init__(self):
        self.discovered_paths = OrderedDict()  # used as an ordered set (values unused)
        self.truncated_paths = set()
        self.warnings = []

    def add_warning(self, message):
        '''record a warning and echo it to screen immediately, like every other importer here'''
        self.warnings.append(message)
        print('xml_import(): WARNING: {}'.format(message))


# ---------------------------------------------------------------------------
# Guided wrapper
# ---------------------------------------------------------------------------

def _resolve_flatten_kwargs(kwargs, fn_name):
    '''Resolve every xml-flattening kwarg EXCEPT the source-like kwarg itself (xml_import()'s
    `source`, xml_archive_import()'s `archive_path`) - the curated subset via prompting, the rest
    via silent kwargs.get() defaults (see the module docstring's "Guided-function note" for why
    only a curated subset is prompted at all). Shared between xml_import()'s and
    xml_archive_import()'s wrappers (tedtoolkit/io/archive.py), which differ only in how they
    resolve their one source-like kwarg - everything else about "flatten XML into a table" is
    identical between them, so this is the single place that logic lives.'''
    record_path = kwargs.get('record_path', None)
    if 'record_path' not in kwargs:
        described = record_path if record_path is not None else \
                   'None (auto-detect repeating element)'
        if not ask_yn(default='y', prompt='record_path is set to <{}>. OK?'.format(described)):
            new_val = input('Type new record_path to use (blank for None/auto-detect): >>> ')
            record_path = new_val.strip() or None
        _add_kwarg_to_last_command('record_path',
            _quoted(record_path) if record_path is not None else 'None', fn_name=fn_name)

    list_strategy = kwargs.get('list_strategy', None)
    if list_strategy not in LIST_STRATEGIES:
        list_strategy = _prompt_for_list_arg('list_strategy', list(LIST_STRATEGIES),
                                             default_index=0, fn_name=fn_name)

    max_depth = kwargs.get('max_depth', None)
    if 'max_depth' not in kwargs:
        described = max_depth if max_depth is not None else 'None (unlimited)'
        if not ask_yn(default='y', prompt='max_depth is set to <{}>. OK?'.format(described)):
            new_val = input('Type new max_depth (integer, blank for None/unlimited): >>> ')
            max_depth = int(new_val) if new_val.strip() else None
        _add_kwarg_to_last_command('max_depth', max_depth if max_depth is not None else 'None',
            fn_name=fn_name)

    namespace_mode = kwargs.get('namespace_mode', None)
    if namespace_mode not in NAMESPACE_MODES:
        namespace_mode = _prompt_for_list_arg('namespace_mode', list(NAMESPACE_MODES),
                                              default_index=0, fn_name=fn_name)

    on_malformed = kwargs.get('on_malformed', None)
    if on_malformed not in ON_MALFORMED_MODES:
        on_malformed = _prompt_for_list_arg('on_malformed', list(ON_MALFORMED_MODES),
                                            default_index=0, fn_name=fn_name)

    low_memory = _prompt_for_bool_arg('low_memory', default_val=False, fn_name=fn_name) \
                 if 'low_memory' not in kwargs else kwargs['low_memory']

    header_row = _prompt_for_bool_arg('header_row', default_val=True, fn_name=fn_name) \
                 if 'header_row' not in kwargs else kwargs['header_row']

    return {
        'record_path': record_path,
        'max_depth': max_depth,
        'residual_format': kwargs.get('residual_format', 'xml'),
        'list_strategy': list_strategy,
        'list_strategy_overrides': kwargs.get('list_strategy_overrides', None),
        'aggregate_format': kwargs.get('aggregate_format', 'json'),
        'aggregate_delimiter': kwargs.get('aggregate_delimiter', ' | '),
        'max_indexed_items': kwargs.get('max_indexed_items', 10),
        'force_list': kwargs.get('force_list', None),
        'path_separator': kwargs.get('path_separator', '.'),
        'attribute_prefix': kwargs.get('attribute_prefix', '@'),
        'text_key': kwargs.get('text_key', '#text'),
        'include_attributes': kwargs.get('include_attributes', True),
        'include_text': kwargs.get('include_text', True),
        'namespace_mode': namespace_mode,
        'empty_value': kwargs.get('empty_value', ''),
        'header_row': header_row,
        'column_order': kwargs.get('column_order', 'discovery'),
        'max_columns': kwargs.get('max_columns', 2000),
        'max_rows': kwargs.get('max_rows', None),
        'on_malformed': on_malformed,
        'return_metadata': kwargs.get('return_metadata', False),
        'low_memory': low_memory,
    }


def _parse_xml_args(**kwargs):
    '''Resolve every xml_import() kwarg - taking it as given, or prompting + baking into history
    for the curated subset described in the module docstring. kwargs may include the
    internal-use-only '_caller_fn_name', set by data_import() so prompted-for values are baked
    into the caller's history line, not xml_import's (mirrors _parse_csv_args's contract).'''
    fn_name = kwargs.pop('_caller_fn_name', 'xml_import')

    source = kwargs.get('source', None)
    if source is None:
        if ask_yn(default='n', prompt='Import a folder of XML files instead of a single file?'):
            source = g_sel_folder(title='xml_import(): select folder of XML files')
        else:
            source = g_sel_file(title='xml_import(): select XML file',
                                filetypes=[('XML files', ('*.xml')), ('All files', ('*.*'))])
        if not source:
            print('No source selected: xml_import() cancelled.\n')
            return None
        if 'source' not in kwargs:
            _add_kwarg_to_last_command('source', _quoted(source), fn_name=fn_name)

    resolved = _resolve_flatten_kwargs(kwargs, fn_name)
    resolved['source'] = source
    return resolved


def xml_import(**kwargs):
    '''Import XML file(s), flattened to list-of-lists (records -> rows, attributes/nested/
    repeated elements -> columns). No XML export is provided.
    kwargs:
      source - path/Path/directory/raw XML bytes-or-str/file-like (prompts via GUI if not given;
        a directory processes every *.xml file in it - non-.xml files are skipped with a warning
        - and returns dict[filename] -> table instead of a single table)
      record_path - dotted (path_separator-joined) or simple XPath-like path identifying the
        repeating "record" element, e.g. 'Orders.Order'. None (default) auto-detects the
        shallowest element that recurs more than once under the root (or uses the root itself if
        nothing repeats). Paths in list_strategy_overrides are relative to the record element's
        OWN children - the record's own tag is the row boundary, not a column prefix.
      max_depth - int|None (default None/unlimited): elements deeper than this (0 = the record
        itself) are serialised whole into one residual column (see residual_format) instead of
        being expanded into further columns.
      residual_format - 'xml'|'json'|'dict' (default 'xml'): how a max_depth/'residual'-strategy
        subtree is serialised. Residual column names are the truncated path + '.residual'
        (joined with path_separator, consistent with every other naming rule here).
      list_strategy - 'explode'|'aggregate'|'indexed'|'residual' (default 'explode'): default
        handling for any element that recurs under the same parent. 'explode' produces one row
        per occurrence (parent fields duplicated - when several independent lists occur under
        the same parent, rows are the full cartesian product across them, same as flattening
        nested JSON arrays). 'aggregate' keeps one row, packing every occurrence into one cell
        (aggregate_format). 'indexed' expands into path.0.*, path.1.*, ... columns (capped at
        max_indexed_items). 'residual' serialises the whole occurrence list as one blob.
      list_strategy_overrides - dict[path] -> strategy, overriding list_strategy per path
        (relative to the record element, see record_path above).
      aggregate_format - 'json'|'xml'|'delimited' (default 'json'): used when list_strategy (or
        an override) is 'aggregate'. 'delimited' only applies to a list of pure scalar/text
        values (joined by aggregate_delimiter) - anything with attributes/children falls back to
        aggregate_format's json/xml handling.
      aggregate_delimiter - str (default ' | '): separator for aggregate_format='delimited'.
      max_indexed_items - int (default 10): cap for list_strategy='indexed'; occurrences beyond
        this are dropped with a warning (not silently lost - see return_metadata/warnings).
      force_list - list[str]|None: element local names always treated as a list even when a
        given record has only one occurrence, so a column's shape can't flip between scalar and
        list across records.
      path_separator - str (default '.'): joins path segments into column names.
      attribute_prefix - str (default '@'): prefix distinguishing attribute columns from child-
        element columns, e.g. 'Item.@id'.
      text_key - str (default '#text'): column name used for an element's own text when that
        element ALSO has attributes or children (an element with only text uses its own path as
        the column name directly - text_key is not needed/used in that case).
      include_attributes - bool (default True): if False, XML attributes are ignored entirely.
      include_text - bool (default True): if False, element text content is ignored entirely.
      namespace_mode - 'strip'|'prefix'|'keep' (default 'strip'): how XML namespaces affect
        element/attribute names (and therefore record_path/list_strategy_overrides path syntax).
        'strip' removes prefixes/URIs entirely (simplest columns, paths written without
        namespaces); 'prefix' keeps the namespace prefix if the document declares one (ns:Order);
        'keep' keeps the full {URI}local Clark-notation form.
      empty_value - any (default ''): value used when a discovered column is absent on a
        particular row.
      header_row - bool (default True): if True, row 0 of the returned table is the column
        headers.
      column_order - 'discovery'|'alpha'|'stable' (default 'discovery'): 'discovery' is the
        order columns were first encountered while walking the data (this requires no extra pass
        - the raw XML is parsed exactly once regardless of column_order; a second, cheap,
        in-memory pass just reformats the already-extracted rows into the final table).
        'alpha' sorts columns by full path name. 'stable', in bulk/folder mode ONLY, unifies
        columns across every file in the folder before writing any one file's table (so the same
        column always lands in the same position across files) - this requires a schema-
        discovery pass across the WHOLE folder before any file is materialised, and holds every
        file's extracted rows in memory at once to compute that union; prefer 'discovery'/'alpha'
        for very large multi-file corpora if that memory cost matters, since those two stay
        strictly per-file. Single-file import treats 'stable' the same as 'discovery'.
      max_columns - int|None (default 2000): hard cap on returned columns; extra discovered
        columns beyond this are dropped (not raised) with a warning.
      max_rows - int|None (default None/unlimited): stop after this many output rows (per file,
        in bulk mode) - useful for sampling a large document.
      on_malformed - 'raise'|'recover'|'skip' (default 'raise'): 'recover' uses lxml's tolerant
        parser (XMLParser(recover=True)) to salvage a best-effort tree from a malformed document,
        surfacing whatever it had to skip as warnings; 'skip' treats a document that fails to
        parse at all as skipped (warning, empty result for that document) rather than raising.
        In bulk/folder mode, 'skip' skips just that one file and continues with the rest.
      return_metadata - bool (default False): if True, returns (table, metadata_dict) instead of
        just table - metadata_dict has discovered_paths, record_count, truncated_paths, warnings.
        This only changes the RETURN shape; basic import statistics are always printed to screen
        either way.
      low_memory - bool (default False): stream the source via lxml's iterparse, clearing each
        completed record's subtree immediately after flattening it, so peak memory is
        proportional to the buffered flattened rows rather than the whole XML DOM tree - much
        slower, especially in bulk mode, but avoids memory errors on very large documents.
        Matches records by local tag name (the last segment of record_path, or the auto-detected
        tag) rather than full structural path, so it assumes that tag name is unambiguous in the
        document; use low_memory=False for exact path-based matching on ambiguous schemas.
      _caller_fn_name - [INTERNAL USE] set by data_import() so prompted-for values are baked
        into the caller's history line, not this function's.

    Folder GUI-prompt scope: the "import a folder instead?" Y/N prompt above only fires when
    xml_import() is called directly with no source. A fully blank data_import() call keeps its
    existing single-file-only picker (matching xlsx/csv/txt) - pass file_path=<folder> explicitly
    to data_import() for bulk mode through the unified dispatcher.

    Returns a list-of-lists for a single file/string/bytes/file-like source, or
    dict[filename] -> list-of-lists for a directory source (dict[filename] -> (table, metadata)
    if return_metadata=True).
    '''
    resolved = _parse_xml_args(**kwargs)
    if resolved is None:
        return None
    return _xml_import_core(**resolved)
xml_import.desc = 'Import XML file(s), flattened to list-of-lists'


# ---------------------------------------------------------------------------
# Pure core - no GUI, no prompting, no history side effects
# ---------------------------------------------------------------------------

def _xml_import_core(source, *, record_path=None, max_depth=None, residual_format='xml',
                     list_strategy='explode', list_strategy_overrides=None,
                     aggregate_format='json', aggregate_delimiter=' | ', max_indexed_items=10,
                     force_list=None, path_separator='.', attribute_prefix='@', text_key='#text',
                     include_attributes=True, include_text=True, namespace_mode='strip',
                     empty_value='', header_row=True, column_order='discovery',
                     max_columns=2000, max_rows=None, on_malformed='raise',
                     return_metadata=False, low_memory=False):
    '''Pure XML-import logic. All args already resolved (no prompting/history side effects).
    Dispatches to single-file or bulk-folder handling based on whether source is a directory.'''
    opts = _make_flatten_opts(max_depth=max_depth, residual_format=residual_format,
        list_strategy=list_strategy, list_strategy_overrides=list_strategy_overrides,
        aggregate_format=aggregate_format, aggregate_delimiter=aggregate_delimiter,
        max_indexed_items=max_indexed_items, force_list=force_list,
        path_separator=path_separator, attribute_prefix=attribute_prefix, text_key=text_key,
        include_attributes=include_attributes, include_text=include_text,
        namespace_mode=namespace_mode)

    if isinstance(source, (str, os.PathLike)) and os.path.isdir(source):
        return _xml_import_bulk_core(os.fspath(source), record_path=record_path, opts=opts,
            header_row=header_row, column_order=column_order, max_columns=max_columns,
            max_rows=max_rows, on_malformed=on_malformed, empty_value=empty_value,
            return_metadata=return_metadata, low_memory=low_memory)

    return _xml_import_single_core(source, record_path=record_path, opts=opts,
        header_row=header_row, column_order=column_order, max_columns=max_columns,
        max_rows=max_rows, on_malformed=on_malformed, empty_value=empty_value,
        return_metadata=return_metadata, low_memory=low_memory, label=_source_label(source))


def _source_label(source):
    '''short human-readable label for print statements; avoids dumping raw XML content to screen'''
    if isinstance(source, (str, os.PathLike)) and not _is_raw_xml_text(str(source)):
        return str(source)
    if hasattr(source, 'name'):
        return getattr(source, 'name')
    return '<in-memory XML>'


def _xml_import_single_core(source, *, record_path, opts, header_row, column_order,
                            max_columns, max_rows, on_malformed, empty_value, return_metadata,
                            low_memory, label, column_override=None):
    '''Import one XML source (path/bytes/str/file-like) into a single table.'''
    ctx = _FlattenContext()
    try:
        if low_memory:
            row_dicts = _extract_rows_streaming(source, record_path, opts, ctx, max_rows,
                                                on_malformed)
        else:
            row_dicts = _extract_rows_full(source, record_path, opts, ctx, max_rows, on_malformed)
    except etree.XMLSyntaxError as exc:
        if on_malformed == 'raise':
            raise
        ctx.add_warning('malformed XML in <{}>, document skipped: {}'.format(label, exc))
        row_dicts = []

    table, metadata = _finalize_table(row_dicts, ctx, column_order, max_columns, header_row,
                                      empty_value, column_override)
    _print_import_stats(label, metadata, len(table[0]) if table else 0)
    if return_metadata:
        return table, metadata
    return table


def _xml_import_bulk_core(folder, *, record_path, opts, header_row, column_order, max_columns,
                          max_rows, on_malformed, empty_value, return_metadata, low_memory):
    '''Import every *.xml file in `folder`. Returns dict[filename] -> table (or (table, metadata)
    if return_metadata). Non-.xml files are skipped with a warning.'''
    all_entries = sorted(os.listdir(folder))
    xml_files = [f for f in all_entries if f.lower().endswith('.xml')
                and os.path.isfile(os.path.join(folder, f))]
    skipped = [f for f in all_entries if f not in xml_files
              and os.path.isfile(os.path.join(folder, f))]
    for fname in skipped:
        print('xml_import(): WARNING: skipping non-XML file in folder: {}'.format(fname))

    if not xml_files:
        print('xml_import(): WARNING: no .xml files found in folder <{}>.'.format(folder))
        return {}

    named_sources = [(fname, os.path.join(folder, fname)) for fname in xml_files]
    results = _xml_import_bulk_core_from_sources(named_sources, record_path=record_path,
        opts=opts, header_row=header_row, column_order=column_order, max_columns=max_columns,
        max_rows=max_rows, on_malformed=on_malformed, empty_value=empty_value,
        return_metadata=return_metadata, low_memory=low_memory, item_noun='file')

    print('\nxml_import(): bulk import complete. {} XML file(s) processed, {} non-XML file(s) '
          'skipped.\n'.format(len(xml_files), len(skipped)))
    return results


def _xml_import_bulk_core_from_sources(named_sources, *, record_path, opts, header_row,
                                       column_order, max_columns, max_rows, on_malformed,
                                       empty_value, return_metadata, low_memory,
                                       item_noun='file'):
    '''Shared bulk-import engine: named_sources is a list of (name, source) pairs, where each
    source is anything _as_parse_input() accepts (a path or raw bytes). Returns
    dict[name] -> table (or (table, metadata) if return_metadata) - built once here and reused by
    both xml_import()'s folder-of-files bulk mode (_xml_import_bulk_core above, source = each
    file's path) and xml_archive_import()'s archive-member bulk mode
    (tedtoolkit/io/archive.py, source = each member's raw bytes), so column_order='stable''s
    cross-item column-unification logic is written and tested exactly once. The caller is
    responsible for filtering out non-XML entries and printing skip-warnings/an empty-input
    warning BEFORE calling this - this function only processes what it's given, and does not
    print a final summary line (each caller's summary wording differs - "files" vs "members" -
    see _xml_import_bulk_core above for that pattern).'''
    results = OrderedDict()
    if not named_sources:
        return results

    if column_order == 'stable':
        # Pass 1/2: extract every item's rows and discover its columns, WITHOUT materializing a
        # table yet, so the unified column set can be computed across the whole batch first.
        per_item = OrderedDict()
        unified_columns = OrderedDict()
        with click.progressbar(named_sources, fill_char='*', empty_char=' ',
                               label='Discovering XML schema (pass 1/2)') as items:
            for name, source in items:
                ctx = _FlattenContext()
                try:
                    if low_memory:
                        row_dicts = _extract_rows_streaming(source, record_path, opts, ctx,
                                                            max_rows, on_malformed)
                    else:
                        row_dicts = _extract_rows_full(source, record_path, opts, ctx, max_rows,
                                                       on_malformed)
                except etree.XMLSyntaxError as exc:
                    if on_malformed == 'raise':
                        raise
                    ctx.add_warning('malformed XML in <{}>, document skipped: {}'.format(
                        name, exc))
                    row_dicts = []
                per_item[name] = (row_dicts, ctx)
                unified_columns.update((c, None) for c in ctx.discovered_paths)
        unified_columns, truncated = _apply_max_columns(list(unified_columns), max_columns)

        with click.progressbar(list(per_item.items()), fill_char='*', empty_char=' ',
                               label='Writing tables (pass 2/2)') as items:
            for name, (row_dicts, ctx) in items:
                if truncated:
                    ctx.add_warning('max_columns={} exceeded across the combined {}s; extra '
                                    'columns dropped'.format(max_columns, item_noun))
                table = _materialize_table(row_dicts, unified_columns, header_row, empty_value)
                metadata = _build_metadata(ctx, len(row_dicts))
                _print_import_stats(name, metadata, len(unified_columns))
                results[name] = (table, metadata) if return_metadata else table
    else:
        with click.progressbar(named_sources, fill_char='*', empty_char=' ',
                               label='Importing XML {}s'.format(item_noun)) as items:
            for name, source in items:
                results[name] = _xml_import_single_core(source, record_path=record_path,
                    opts=opts, header_row=header_row, column_order=column_order,
                    max_columns=max_columns, max_rows=max_rows, on_malformed=on_malformed,
                    empty_value=empty_value, return_metadata=return_metadata,
                    low_memory=low_memory, label=name)

    return results


def _finalize_table(row_dicts, ctx, column_order, max_columns, header_row, empty_value,
                    column_override):
    columns = column_override if column_override is not None else \
             _order_columns(list(ctx.discovered_paths), column_order)
    columns, truncated = _apply_max_columns(columns, max_columns)
    if truncated:
        ctx.add_warning('max_columns={} exceeded; extra columns dropped'.format(max_columns))
    table = _materialize_table(row_dicts, columns, header_row, empty_value)
    return table, _build_metadata(ctx, len(row_dicts))


def _build_metadata(ctx, record_count):
    return {
        'discovered_paths': list(ctx.discovered_paths),
        'record_count': record_count,
        'truncated_paths': sorted(ctx.truncated_paths),
        'warnings': list(ctx.warnings),
    }


def _print_import_stats(label, metadata, column_count):
    print('\nxml_import(): finished importing <{}>.'.format(label))
    print('  Records: {}'.format(metadata['record_count']))
    discovered = len(metadata['discovered_paths'])
    if column_count > discovered:
        # bulk column_order='stable': column_count includes columns unified in from OTHER files
        # in the folder, so it can legitimately exceed this file's own discovered-path count.
        print('  Columns: {} ({} discovered in this file; remainder unified in from other files '
              "in the folder, per column_order='stable')".format(column_count, discovered))
    else:
        print('  Columns: {} (of {} discovered)'.format(column_count, discovered))
    if metadata['truncated_paths']:
        print('  Paths truncated by max_depth/residual handling: {}'.format(
            len(metadata['truncated_paths'])))
    for warning in metadata['warnings']:
        print('  WARNING: {}'.format(warning))
    print()


def _order_columns(columns, column_order):
    if column_order not in COLUMN_ORDERS:
        raise ValueError("xml_import(): unknown column_order '{}'".format(column_order))
    if column_order == 'alpha':
        return sorted(columns)
    return list(columns)  # 'discovery' as-is; 'stable' unification happens one level up (bulk)


def _apply_max_columns(columns, max_columns):
    if max_columns is None or len(columns) <= max_columns:
        return columns, False
    return columns[:max_columns], True


def _materialize_table(row_dicts, columns, header_row, empty_value):
    '''Cheap, in-memory-only pass: reformats already-extracted row dicts into the final
    list-of-lists. Never re-parses the source XML - see the module/xml_import docstrings.'''
    table = [list(columns)] if header_row else []
    with click.progressbar(row_dicts, fill_char='*', empty_char=' ',
                           label='Writing table rows') as rows:
        for row in rows:
            table.append([row.get(col, empty_value) for col in columns])
    return table


# ---------------------------------------------------------------------------
# Source normalization
# ---------------------------------------------------------------------------

def _is_raw_xml_text(text):
    stripped = text.lstrip()
    return stripped.startswith('<')


def _as_parse_input(source):
    '''Normalize `source` into something lxml's parse()/iterparse() accept directly: a file path
    string, or a file-like/BytesIO. Raw XML content (str/bytes) is wrapped fresh each call, so
    calling this twice on the same bytes/str/path is always safe and independent.'''
    if hasattr(source, 'read'):
        return source
    if isinstance(source, bytes):
        return io.BytesIO(source)
    if isinstance(source, os.PathLike):
        source = os.fspath(source)
    if isinstance(source, str):
        if _is_raw_xml_text(source):
            return io.BytesIO(source.encode('utf-8'))
        return source  # file path
    raise TypeError('xml_import(): source must be a path, Path, XML bytes/str, or file-like object')


# ---------------------------------------------------------------------------
# Full-parse extraction
# ---------------------------------------------------------------------------

def _extract_rows_full(source, record_path, opts, ctx, max_rows, on_malformed):
    parser = etree.XMLParser(recover=on_malformed == 'recover')
    tree = etree.parse(_as_parse_input(source), parser=parser)
    if on_malformed == 'recover':
        for entry in parser.error_log:
            ctx.add_warning('recovered from XML error: {}'.format(entry))
    root = tree.getroot()
    if opts.namespace_mode == 'strip':
        _strip_namespaces_inplace(root)

    record_elements = _resolve_record_elements(root, record_path, opts)
    row_dicts = []
    with click.progressbar(record_elements, fill_char='*', empty_char=' ',
                           label='Parsing XML records') as records:
        for rec in records:
            ancestor_ctx = _build_ancestor_context(rec, root, opts)
            for row in _flatten_record(rec, ancestor_ctx, opts, ctx):
                row_dicts.append(row)
                if max_rows is not None and len(row_dicts) >= max_rows:
                    return row_dicts
    return row_dicts


def _strip_namespaces_inplace(root):
    '''Standard lxml recipe: rewrite every element's tag to its local name and drop namespaced
    attribute prefixes, then let lxml's cleanup_namespaces() remove now-unused nsmap
    declarations. Applied once, right after parsing, so every later step (record_path resolution
    via findall, column naming) works in plain local-name terms regardless of the document's
    actual namespace usage.'''
    for elem in root.iter():
        if isinstance(elem.tag, str) and elem.tag.startswith('{'):
            elem.tag = etree.QName(elem.tag).localname
        if elem.attrib:
            stripped = {(etree.QName(k).localname if k.startswith('{') else k): v
                        for k, v in elem.attrib.items()}
            elem.attrib.clear()
            elem.attrib.update(stripped)
    etree.cleanup_namespaces(root)


def _resolve_record_elements(root, record_path, opts):
    if record_path:
        segments = [s for s in record_path.split(opts.path_separator) if s]
        # record_path is always written in plain local-name terms, regardless of namespace_mode
        # (namespace_mode only controls COLUMN display naming, not path-matching ergonomics) -
        # matched via XPath's local-name(), so a namespaced document never needs its prefixes
        # spelled out in record_path/list_strategy_overrides.
        root_local = etree.QName(root.tag).localname if isinstance(root.tag, str) else str(root.tag)
        # A leading segment matching the root's own tag is common (e.g. record_path='Orders.Order'
        # for a document whose root IS <Orders>) - strip it so the rest resolves as descendants
        # of root, rather than requiring a second nested <Orders> element inside the root.
        if segments and segments[0] == root_local:
            segments = segments[1:]
        if not segments:
            return [root]
        xpath_expr = './/' + '/'.join("*[local-name()='{}']".format(seg) for seg in segments)
        elements = root.xpath(xpath_expr)
        if not elements:
            raise ValueError("xml_import(): record_path '{}' matched no elements.".format(
                record_path))
        return elements
    detected_tag = _detect_record_tag(_tag_depth_pairs_full(root))
    if detected_tag is None:
        return [root]
    return root.findall('.//' + detected_tag)


def _tag_depth_pairs_full(root):
    for elem in root.iter():
        if elem is root:
            continue
        depth = 0
        parent = elem.getparent()
        while parent is not None:
            depth += 1
            parent = parent.getparent()
        yield elem.tag, depth


def _detect_record_tag(tag_depth_pairs):
    '''Given (tag, depth) pairs for every element below the root, return the tag name of the
    shallowest tag that recurs more than once - the "first repeating element under the root" per
    xml_import's record_path=None contract. Returns None if nothing repeats (caller then treats
    the root itself as the sole record).'''
    counts = {}
    first_depth = {}
    for tag, depth in tag_depth_pairs:
        counts[tag] = counts.get(tag, 0) + 1
        first_depth.setdefault(tag, depth)
    repeated = [tag for tag, count in counts.items() if count > 1]
    if not repeated:
        return None
    return min(repeated, key=lambda tag: (first_depth[tag], tag))


def _build_ancestor_context(record_elem, root, opts):
    '''Everything above the matched record element is copied into every row from that record -
    computed per the record's ACTUAL ancestor chain (not a single global assumption), so the
    same record_path recurring under multiple distinct parent instances gets each instance's own
    ancestor attribute/text values, not the first one seen.'''
    chain = []
    parent = record_elem.getparent()
    while parent is not None and parent is not root:
        chain.append(parent)
        parent = parent.getparent()
    context = OrderedDict()
    for ancestor in reversed(chain):
        name = _display_name(ancestor.tag, ancestor, opts.namespace_mode)
        if opts.include_attributes:
            for key, value in ancestor.attrib.items():
                attr_name = _display_name(key, ancestor, opts.namespace_mode)
                context[name + opts.path_separator + opts.attribute_prefix + attr_name] = value
        if opts.include_text:
            text_val = (ancestor.text or '').strip()
            if text_val:
                context[name] = text_val
    return context


# ---------------------------------------------------------------------------
# Low-memory (iterparse) extraction
# ---------------------------------------------------------------------------

def _extract_rows_streaming(source, record_path, opts, ctx, max_rows, on_malformed):
    '''Standard lxml low-memory idiom: iterparse + elem.clear() (dropping already-processed
    preceding siblings too) immediately after flattening each completed record, so peak memory is
    proportional to buffered flattened rows, not the whole XML DOM. Matches records by local tag
    name via iterparse's per-event tag comparison - if record_path is a multi-segment path, only
    its last segment is used as the match key, since iterparse has no structural path filter;
    ambiguous schemas should use low_memory=False for exact path-based matching.'''
    record_tag = record_path.split(opts.path_separator)[-1] if record_path else None
    if record_tag is None:
        record_tag = _sniff_record_tag_streaming(source)
        if record_tag is None:
            raise ValueError("xml_import(): low_memory=True could not auto-detect a repeating "
                             "record element; pass record_path explicitly.")

    row_dicts = []
    context = etree.iterparse(_as_parse_input(source), events=('end',),
                              recover=on_malformed == 'recover')
    root = None
    for _event, elem in context:
        if root is None:
            root = elem.getroottree().getroot()
        local = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else str(elem.tag)
        if local == record_tag:
            ancestor_ctx = _build_ancestor_context(elem, root, opts)
            for row in _flatten_record(elem, ancestor_ctx, opts, ctx):
                row_dicts.append(row)
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            if max_rows is not None and len(row_dicts) >= max_rows:
                break
    return row_dicts


def _sniff_record_tag_streaming(source):
    '''Bounded (capped) start-event sniff used only to auto-detect record_path under
    low_memory=True, so auto-detection never requires loading the whole document. Path/bytes/str
    sources are trivially re-readable afterward (_as_parse_input re-wraps them fresh); a genuine
    file-like `source` must be seekable, since it's read once here and again for the real parse.'''
    if hasattr(source, 'read'):
        if not (hasattr(source, 'seekable') and source.seekable()):
            raise ValueError("xml_import(): low_memory=True with record_path=None requires a "
                             "seekable source for auto-detection (or pass record_path explicitly).")
        start_pos = source.tell()
    else:
        start_pos = None

    depth = -1
    pairs = []
    context = etree.iterparse(_as_parse_input(source), events=('start', 'end'))
    for event, elem in context:
        if event == 'start':
            depth += 1
            if depth > 0:
                pairs.append((elem.tag, depth))
                if len(pairs) >= _AUTO_DETECT_SNIFF_LIMIT:
                    break
        else:
            depth -= 1
    del context

    if start_pos is not None:
        source.seek(start_pos)

    tag = _detect_record_tag(iter(pairs))
    return etree.QName(tag).localname if tag else None


# ---------------------------------------------------------------------------
# Namespace-aware naming
# ---------------------------------------------------------------------------

def _display_name(raw_tag, elem, namespace_mode):
    '''Resolve raw_tag (an element tag or attribute key, possibly Clark-notation {uri}local) to
    a display name per namespace_mode. Safe to call unconditionally even after
    _strip_namespaces_inplace has already rewritten tags to plain local names.'''
    if not isinstance(raw_tag, str):
        return str(raw_tag)
    if namespace_mode == 'keep':
        return raw_tag
    qname = etree.QName(raw_tag)
    if namespace_mode == 'strip' or qname.namespace is None:
        return qname.localname
    nsmap = getattr(elem, 'nsmap', {}) or {}
    prefix = next((p for p, uri in nsmap.items() if uri == qname.namespace), None)
    return '{}:{}'.format(prefix, qname.localname) if prefix else qname.localname


# ---------------------------------------------------------------------------
# The flattening engine
# ---------------------------------------------------------------------------

def _make_flatten_opts(**kwargs):
    return SimpleNamespace(
        max_depth=kwargs['max_depth'],
        residual_format=kwargs['residual_format'],
        list_strategy=kwargs['list_strategy'],
        list_strategy_overrides=kwargs['list_strategy_overrides'] or {},
        aggregate_format=kwargs['aggregate_format'],
        aggregate_delimiter=kwargs['aggregate_delimiter'],
        max_indexed_items=kwargs['max_indexed_items'],
        force_list=set(kwargs['force_list'] or []),
        path_separator=kwargs['path_separator'],
        attribute_prefix=kwargs['attribute_prefix'],
        text_key=kwargs['text_key'],
        include_attributes=kwargs['include_attributes'],
        include_text=kwargs['include_text'],
        namespace_mode=kwargs['namespace_mode'],
    )


def _join_path(base, name, sep):
    return base + sep + name if base else name


def _cartesian_merge(rows, sub_rows):
    '''Merge sub_rows into rows. This single operation covers both a plain single-occurrence
    child (sub_rows has exactly one dict -> ordinary merge, no row multiplication) and an
    'explode'd repeated child (sub_rows has one dict per occurrence -> true cartesian product) -
    the same mechanism that makes multiple independent exploded lists under one parent multiply
    out correctly when applied once per child-group, in sequence.'''
    if not sub_rows:
        return rows
    if len(rows) == 1 and len(sub_rows) == 1:
        merged = OrderedDict(rows[0])
        merged.update(sub_rows[0])
        return [merged]
    result = []
    for base in rows:
        for extra in sub_rows:
            merged = OrderedDict(base)
            merged.update(extra)
            result.append(merged)
    return result


def _flatten_record(record_elem, ancestor_context, opts, ctx):
    '''Flatten one matched record element into one or more row-dicts, with the per-instance
    ancestor context merged into every one of them.'''
    rows = _flatten_children(record_elem, '', 0, opts, ctx)
    if ancestor_context:
        rows = [OrderedDict(list(ancestor_context.items()) + list(row.items())) for row in rows]
    for row in rows:
        ctx.discovered_paths.update((key, None) for key in row)
    return rows


def _flatten_children(elem, own_path, depth, opts, ctx):
    '''Recursively flatten elem's own attributes/text and all descendants into row-dict(s), with
    column names built from own_path. Returns a list of dicts (length 1 unless a descendant list
    under 'explode' multiplies it out).'''
    if opts.max_depth is not None and depth > opts.max_depth:
        residual_col = _join_path(own_path, 'residual', opts.path_separator)
        ctx.truncated_paths.add(own_path or '<root>')
        return [OrderedDict({residual_col: _serialize_residual(elem, opts.residual_format, opts)})]

    rows = [OrderedDict()]

    if opts.include_attributes:
        for key, value in elem.attrib.items():
            name = _display_name(key, elem, opts.namespace_mode)
            col = _join_path(own_path, opts.attribute_prefix + name, opts.path_separator)
            for row in rows:
                row[col] = value

    has_children = len(elem) > 0
    text_val = (elem.text or '').strip() if opts.include_text else ''
    if text_val:
        has_attrs = opts.include_attributes and len(elem.attrib) > 0
        text_col = own_path if not (has_children or has_attrs) else \
                  _join_path(own_path, opts.text_key, opts.path_separator)
        for row in rows:
            row[text_col] = text_val

    groups = OrderedDict()
    for child in elem:
        name = _display_name(child.tag, child, opts.namespace_mode)
        groups.setdefault(name, []).append(child)

    for name, children in groups.items():
        child_path = _join_path(own_path, name, opts.path_separator)
        is_list = len(children) > 1 or name in opts.force_list
        strategy = opts.list_strategy_overrides.get(child_path, opts.list_strategy) \
                  if is_list else None

        if not is_list:
            sub_rows = _flatten_children(children[0], child_path, depth + 1, opts, ctx)
            rows = _cartesian_merge(rows, sub_rows)
        elif strategy == 'explode':
            sub_rows = []
            for child in children:
                sub_rows.extend(_flatten_children(child, child_path, depth + 1, opts, ctx))
            rows = _cartesian_merge(rows, sub_rows)
        elif strategy == 'aggregate':
            value = _aggregate_children(children, opts)
            for row in rows:
                row[child_path] = value
        elif strategy == 'indexed':
            capped = children[:opts.max_indexed_items]
            if len(children) > opts.max_indexed_items:
                ctx.add_warning('{}: {} item(s) beyond max_indexed_items={} dropped'.format(
                    child_path, len(children) - opts.max_indexed_items, opts.max_indexed_items))
            for index, child in enumerate(capped):
                idx_path = _join_path(child_path, str(index), opts.path_separator)
                sub_rows = _flatten_children(child, idx_path, depth + 1, opts, ctx)
                rows = _cartesian_merge(rows, sub_rows)
        elif strategy == 'residual':
            residual_col = _join_path(child_path, 'residual', opts.path_separator)
            ctx.truncated_paths.add(child_path)
            value = _serialize_residual(children, opts.residual_format, opts)
            for row in rows:
                row[residual_col] = value
        else:
            raise ValueError("xml_import(): unknown list_strategy '{}'".format(strategy))

    return rows


def _element_to_jsonable(elem, opts):
    '''Recursive XML->dict/leaf-text converter used only for residual/aggregate JSON/dict
    serialization (NOT the main column-flattening path above) - reuses attribute_prefix/text_key
    so residual/aggregate blobs stay visually consistent with the flattened columns around them.'''
    result = {}
    if opts.include_attributes:
        for key, value in elem.attrib.items():
            name = _display_name(key, elem, opts.namespace_mode)
            result[opts.attribute_prefix + name] = value
    children_by_name = OrderedDict()
    for child in elem:
        name = _display_name(child.tag, child, opts.namespace_mode)
        children_by_name.setdefault(name, []).append(_element_to_jsonable(child, opts))
    for name, values in children_by_name.items():
        result[name] = values if len(values) > 1 else values[0]
    text = (elem.text or '').strip() if opts.include_text else ''
    if text:
        if result:
            result[opts.text_key] = text
        else:
            return text
    return result


def _serialize_residual(elem_or_list, fmt, opts):
    '''Serialize a truncated subtree (single element, from max_depth) or a whole occurrence list
    (from list_strategy='residual') per residual_format.'''
    if fmt not in RESIDUAL_FORMATS:
        raise ValueError("xml_import(): unknown residual_format '{}'".format(fmt))
    elems = elem_or_list if isinstance(elem_or_list, list) else [elem_or_list]
    if fmt == 'xml':
        return ''.join(etree.tostring(e, encoding='unicode').strip() for e in elems)
    data = [_element_to_jsonable(e, opts) for e in elems]
    if not isinstance(elem_or_list, list):
        data = data[0]
    if fmt == 'json':
        return json.dumps(data, default=str)
    return repr(data)  # 'dict'


def _aggregate_children(children, opts):
    '''Pack every occurrence of a repeated element into one cell, per aggregate_format.'''
    all_scalar = all(len(child) == 0 and (not opts.include_attributes or len(child.attrib) == 0)
                     for child in children)
    if all_scalar and opts.aggregate_format == 'delimited':
        return opts.aggregate_delimiter.join((child.text or '').strip() for child in children)
    if opts.aggregate_format == 'xml':
        return ''.join(etree.tostring(child, encoding='unicode').strip() for child in children)
    # 'json' (also the fallback for 'delimited' on non-scalar occurrences)
    data = [_element_to_jsonable(child, opts) for child in children]
    return json.dumps(data, default=str)
